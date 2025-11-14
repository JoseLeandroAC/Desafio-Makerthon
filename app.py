import os
import json
import base64
import psycopg  # psycopg v3
from datetime import datetime
from flask import Flask, request, jsonify, render_template, flash, redirect, url_for
from flask_cors import CORS
from io import BytesIO
from dotenv import load_dotenv
from shutil import copy2, rmtree
from pathlib import Path

# DeepFace local
from deepface import DeepFace
import cv2
import numpy as np

# Agendador (opcional)
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from pytz import timezone
except Exception:
    BackgroundScheduler = None

# módulo de envio (se existir)
try:
    import email_ausentes
except Exception:
    email_ausentes = None

load_dotenv()

# Arquivos / pastas
ARQUIVO_MAPA = "alunos_tokens.json"
PASTA_ALUNOS = "alunos"                 # pasta com fotos para cadastro (origem)
PASTA_IMAGENS_CONHECIDAS = "imagens_conhecidas"  # pasta usada pelo DeepFace (destino)
os.makedirs(PASTA_ALUNOS, exist_ok=True)
os.makedirs(PASTA_IMAGENS_CONHECIDAS, exist_ok=True)

# DB
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'dbname': os.getenv('DB_NAME', 'presenca_alunos'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '123456'),
    'port': int(os.getenv('DB_PORT', 5432))
}

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET", "troque-esta-chave")

alunos_tokens = {}  # map face_token/path -> nome (opcional, mantido para compatibilidade)


# ---------------- Helpers ----------------
def salvar_tokens():
    with open(ARQUIVO_MAPA, "w", encoding="utf-8") as f:
        json.dump(alunos_tokens, f, ensure_ascii=False)


def carregar_tokens():
    global alunos_tokens
    if os.path.exists(ARQUIVO_MAPA):
        with open(ARQUIVO_MAPA, "r", encoding="utf-8") as f:
            alunos_tokens = json.load(f)
    else:
        alunos_tokens = {}


def get_db_connection():
    try:
        return psycopg.connect(**DB_CONFIG)
    except Exception as e:
        print(f"Erro ao conectar ao banco: {e}")
        return None


def init_database():
    conn = get_db_connection()
    if conn:
        try:
            with conn, conn.cursor() as cur:
                # alunos
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS alunos (
                        id SERIAL PRIMARY KEY,
                        nome VARCHAR(100) NOT NULL,
                        face_token VARCHAR(255) UNIQUE NOT NULL,
                        data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        email_responsavel TEXT
                    );
                """)
                cur.execute("ALTER TABLE alunos ADD COLUMN IF NOT EXISTS email_responsavel TEXT;")

                # presencas
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS presencas (
                        id SERIAL PRIMARY KEY,
                        aluno_id INTEGER REFERENCES alunos(id),
                        data_presenca DATE DEFAULT CURRENT_DATE,
                        horario_presenca TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        presente BOOLEAN DEFAULT TRUE,
                        confianca DECIMAL(5,2),
                        UNIQUE(aluno_id, data_presenca)
                    );
                """)
        except Exception as e:
            print(f"Erro ao criar/ajustar tabelas: {e}")
        finally:
            conn.close()


def registrar_presenca(nome_aluno, confianca):
    conn = get_db_connection()
    if conn:
        try:
            with conn, conn.cursor() as cur:
                # já tem hoje?
                cur.execute("""
                    SELECT p.id FROM presencas p
                    JOIN alunos a ON p.aluno_id = a.id
                    WHERE a.nome = %s AND p.data_presenca = CURRENT_DATE
                """, (nome_aluno,))
                row = cur.fetchone()
                if row:
                    cur.execute("DELETE FROM presencas WHERE id = %s", (row[0],))
                    return "apagada"
                # insere
                cur.execute("""
                    INSERT INTO presencas (aluno_id, presente, confianca)
                    SELECT id, TRUE, %s FROM alunos WHERE nome = %s
                """, (confianca, nome_aluno))
                # verifica se inseriu (se não existir aluno com esse nome, nada será inserido)
                if cur.rowcount == 0:
                    return False
                return True
        except Exception as e:
            print(f"Erro ao registrar presença: {e}")
            return False
        finally:
            conn.close()


# ---------------- Util DeepFace local ----------------

# pasta usada como banco para o DeepFace (cada subpasta é o nome da pessoa):
DB_PATH = PASTA_IMAGENS_CONHECIDAS

def deepface_search_frame(frame):
    """
    Recebe um frame (BGR OpenCV) e retorna resultados do DeepFace.find.
    Retorna: dict com keys: 'found'(bool), 'nome', 'distance'(float) se aplicável, 'raw' (DataFrame convertido)
    """
    try:
        resultados = DeepFace.find(
            img_path=frame,
            db_path=DB_PATH,
            model_name="VGG-Face",
            enforce_detection=True,
            detector_backend="opencv",
            silent=True
        )
        if resultados and not resultados[0].empty:
            df = resultados[0]
            caminho = df["identity"][0]
            distancia = float(df["distance"][0]) if "distance" in df.columns else None
            nome = caminho.split(os.path.sep)[-2]
            return {"found": True, "nome": nome, "distance": distancia, "raw": df.to_dict(orient="records")}
        else:
            return {"found": False}
    except ValueError:
        # sem rosto detectado
        return {"found": False, "error": "Nenhum rosto detectado"}
    except Exception as e:
        return {"found": False, "error": str(e)}


def distance_to_confidence(distance):
    """
    Converte a distância retornada pelo DeepFace para um valor de confiança [0,100].
    Heurística simples: confidence = 100 - distance*100
    Ajuste se necessário.
    """
    if distance is None:
        return 0.0
    try:
        conf = 100.0 - (float(distance) * 100.0)
        conf = max(0.0, min(100.0, conf))
        return round(conf, 2)
    except Exception:
        return 0.0


# ---------------- Rotas ----------------
@app.route('/')
def index():
    return render_template("index.html")


@app.route('/admin')
def admin_panel():
    conn = get_db_connection()
    if not conn:
        return "Erro de conexão com banco"
    try:
        with conn, conn.cursor() as cur:
            # lista
            cur.execute("""
                SELECT a.id, a.nome,
                       a.email_responsavel,
                       COALESCE(p.presente, FALSE) as presente,
                       p.horario_presenca,
                       p.confianca
                FROM alunos a
                LEFT JOIN presencas p ON a.id = p.aluno_id
                 AND p.data_presenca = CURRENT_DATE
                ORDER BY a.nome
            """)
            dados = cur.fetchall()

            # stats
            cur.execute("""
                SELECT COUNT(DISTINCT a.id) as total_alunos,
                       COUNT(CASE WHEN p.presente = TRUE THEN 1 END) as presentes_hoje
                FROM alunos a
                LEFT JOIN presencas p ON a.id = p.aluno_id
                 AND p.data_presenca = CURRENT_DATE
            """)
            stats = cur.fetchone()

        dados_formatados = []
        for row in dados:
            aluno_id, nome, email_resp, presente, horario, conf = row
            dados_formatados.append({
                'id': aluno_id,
                'nome': nome,
                'email_responsavel': email_resp,
                'presente': bool(presente),
                'horario': horario.strftime('%H:%M:%S') if horario else None,
                'confianca': float(conf) if conf is not None else None,
            })
        data_hoje = datetime.now().strftime('%d/%m/%Y')
        return render_template("admin.html",
                               dados=dados_formatados,
                               total_alunos=stats[0],
                               presentes_hoje=stats[1],
                               data_hoje=data_hoje)
    except Exception as e:
        return f"Erro: {e}"
    finally:
        conn.close()


@app.route('/alunos/<int:aluno_id>/email', methods=['POST'])
def atualizar_email_responsavel(aluno_id):
    novo_email = request.form.get("email_responsavel", "").strip()
    if not novo_email or "@" not in novo_email:
        flash("E-mail inválido.", "warning")
        return redirect(url_for("admin_panel"))
    conn = get_db_connection()
    if not conn:
        flash("Erro de conexão com banco.", "danger")
        return redirect(url_for("admin_panel"))
    try:
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE alunos SET email_responsavel = %s WHERE id = %s",
                        (novo_email, aluno_id))
        flash("E-mail do responsável atualizado.", "success")
    except Exception as e:
        flash(f"Erro ao atualizar e-mail: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for("admin_panel"))


@app.route('/cadastrar_alunos', methods=['GET'])
def cadastrar_alunos():
    """
    Lê imagens da pasta 'alunos', para cada arquivo:
     - cria pasta imagens_conhecidas/<nome> e copia a imagem para lá
     - insere o aluno na tabela 'alunos' com face_token = caminho relativo
    Observação: o nome do arquivo (sem extensão) será usado como nome do aluno.
    """
    carregar_tokens()
    pasta = os.path.join(os.path.dirname(__file__), PASTA_ALUNOS)
    if not os.path.exists(pasta):
        return jsonify({"status": "error", "message": "❌ Pasta 'alunos' não encontrada."}), 404

    arquivos = [f for f in os.listdir(pasta) if not f.startswith('.')]
    if not arquivos:
        return jsonify({"status": "warning", "message": "⚠️ Nenhuma foto encontrada na pasta 'alunos'."}), 200

    log_messages = []

    for foto in arquivos:
        nome = os.path.splitext(foto)[0]
        caminho_origem = os.path.join(pasta, foto)

        # cria subpasta em imagens_conhecidas com o nome do aluno
        destino_dir = os.path.join(os.path.dirname(__file__), DB_PATH, nome)
        os.makedirs(destino_dir, exist_ok=True)

        # copiar arquivo (mantém o mesmo nome)
        destino_path = os.path.join(destino_dir, foto)
        try:
            copy2(caminho_origem, destino_path)
        except Exception as e:
            log_messages.append(f"❌ Erro ao copiar {foto}: {e}")
            continue

        # registrar no banco (usar caminho relativo como token)
        face_token = os.path.relpath(destino_path)

        conn = get_db_connection()
        if conn:
            try:
                with conn, conn.cursor() as cur:
                    cur.execute("SELECT id FROM alunos WHERE nome = %s OR face_token = %s",
                                (nome, face_token))
                    existente = cur.fetchone()
                    if existente:
                        log_messages.append(f"⚠️ {nome} já está cadastrado.")
                    else:
                        cur.execute("""
                            INSERT INTO alunos (nome, face_token)
                            VALUES (%s, %s)
                        """, (nome, face_token))
                        log_messages.append(f"✅ {nome} cadastrado no banco.")
                        alunos_tokens[face_token] = nome
            except Exception as e:
                log_messages.append(f"❌ Erro ao salvar aluno {nome}: {e}")
            finally:
                conn.close()
        else:
            log_messages.append(f"❌ Erro de conexão ao salvar {nome}.")

    salvar_tokens()
    # retornar logs
    return jsonify({"status": "success", "message": "Cadastro concluído.", "log": log_messages}), 200


@app.route('/chamada_webcam', methods=['POST'])
def chamada_webcam():
    """Recebe frame base64, usa DeepFace.find local (imagens_conhecidas) e marca presença."""
    carregar_tokens()
    data = request.get_json(silent=True)

    if not data or "image_data" not in data:
        return jsonify({"status": "error", "message": "Nenhuma imagem recebida."}), 400

    try:
        # extrai base64 (suporta 'data:image/jpeg;base64,...' ou só o base64)
        raw = data.get('image_data')
        if ',' in raw:
            image_data_base64 = raw.split(',')[1]
        else:
            image_data_base64 = raw
    except Exception:
        return jsonify({"status": "error", "message": "Formato de imagem inválido."}), 400

    try:
        image_data_bytes = base64.b64decode(image_data_base64)
    except Exception:
        return jsonify({"status": "error", "message": "Base64 inválido."}), 400

    # converte para frame OpenCV BGR
    np_arr = np.frombuffer(image_data_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({"status": "error", "message": "Imagem inválida ou incompativel."}), 400

    # Faz a busca local com DeepFace
    resultado = deepface_search_frame(frame)

    if resultado.get("found"):
        nome = resultado.get("nome", "Desconhecido")
        distancia = resultado.get("distance")
        confidence = distance_to_confidence(distancia)  # 0..100

        # threshold: considerar presente se confidence > 80 (mesmo critério que você usava anteriormente)
        if confidence > 80:
            registro = registrar_presenca(nome, confidence)
            if registro == "apagada":
                return jsonify({"status": "apagada", "nome": nome, "message": f"Presença de {nome} foi removida (toggle)."})
            elif registro:
                # Mantemos a chave 'confidence' para compatibilidade com frontend
                return jsonify({"status": "presente", "nome": nome, "confidence": confidence})
            else:
                return jsonify({"status": "error", "message": "Erro ao registrar presença no banco."}), 500
        else:
            return jsonify({"status": "nao_identificado", "message": "Rosto detectado, mas sem confiança suficiente.", "confidence": confidence}), 200
    else:
        # Se DeepFace retornou erro
        if "error" in resultado:
            return jsonify({"status": "error", "message": resultado.get("error")}), 400
        return jsonify({"status": "nao_detectado", "message": "Nenhum rosto detectado."}), 200


@app.route('/presencas')
def ver_presencas():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Erro de conexão com banco"})
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                SELECT a.nome, p.data_presenca, p.horario_presenca, p.presente, p.confianca
                FROM presencas p
                JOIN alunos a ON p.aluno_id = a.id
                WHERE p.presente = TRUE
                ORDER BY p.data_presenca DESC, p.horario_presenca DESC
            """)
            presencas = cur.fetchall()
        presencas_list = []
        for p in presencas:
            presencas_list.append({
                'nome': p[0],
                'data': p[1].strftime('%d/%m/%Y'),
                'horario': p[2].strftime('%H:%M:%S'),
                'presente': p[3],
                'confianca': float(p[4]) if p[4] else 0
            })
        return jsonify({"presencas": presencas_list})
    except Exception as e:
        return jsonify({"error": f"Erro ao consultar presenças: {e}"}), 500
    finally:
        conn.close()


# -------------- Scheduler (opcional) --------------
def start_scheduler():
    if not email_ausentes or BackgroundScheduler is None:
        return
    tzname = os.getenv("TIMEZONE", "America/Sao_Paulo")
    tz = timezone(tzname)
    hour = int(os.getenv("EMAIL_SCHEDULE_HOUR", "18"))
    minute = int(os.getenv("EMAIL_SCHEDULE_MINUTE", "0"))
    sched = BackgroundScheduler(timezone=tz)
    sched.add_job(email_ausentes.main, "cron", hour=hour, minute=minute, id="avisos_diarios")
    sched.start()
    print(f"[SCHEDULER] Avisos diários agendados para {hour:02d}:{minute:02d} ({tzname})")


if __name__ == '__main__':
    init_database()
    # garante pastas
    os.makedirs(PASTA_ALUNOS, exist_ok=True)
    os.makedirs(PASTA_IMAGENS_CONHECIDAS, exist_ok=True)

    print("🚀 Sistema iniciado (modo 100% local)!")
    print("- Interface: http://localhost:5000")
    print("- Admin: http://localhost:5000/admin")
    print("- API: POST http://localhost:5000/chamada_webcam")
    app.run(host='0.0.0.0', port=5000, debug=False)
