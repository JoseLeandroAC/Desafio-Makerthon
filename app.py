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
import pandas as pd # Importado para compatibilidade do DeepFace

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
    timezone = None

# módulo de envio (se existir)
try:
    import email_ausentes
except Exception:
    email_ausentes = None

load_dotenv()

# Arquivos / pastas
ARQUIVO_MAPA = "alunos_tokens.json"
ARQUIVO_MAPA_BAK = "alunos_tokens.bak.json"
PASTA_ALUNOS = "alunos"  # pasta com fotos para cadastro (origem)
PASTA_IMAGENS_CONHECIDAS = "imagens_conhecidas"  # pasta usada pelo DeepFace (destino)
os.makedirs(PASTA_ALUNOS, exist_ok=True)
os.makedirs(PASTA_IMAGENS_CONHECIDAS, exist_ok=True)

# DB
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'dbname': os.getenv('DB_NAME', 'alunossesi'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '123456'),
    'port': int(os.getenv('DB_PORT', 5432))
}

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET", "troque-esta-chave")

alunos_tokens = {}  # map face_token/path -> nome (opcional, mantido para compatibilidade)

# Configurações DeepFace via variáveis de ambiente
DEEPFACE_ENFORCE_DETECTION = os.getenv("DEEPFACE_ENFORCE_DETECTION", "True").lower() in ("1", "true", "yes")
try:
    DEEPFACE_CONFIDENCE_THRESHOLD = float(os.getenv("DEEPFACE_CONFIDENCE_THRESHOLD", "60"))
except Exception:
    DEEPFACE_CONFIDENCE_THRESHOLD = 60.0

# ---------------- Helpers ----------------
def salvar_tokens():
    if os.path.exists(ARQUIVO_MAPA):
        # Cria backup antes de sobrescrever
        copy2(ARQUIVO_MAPA, ARQUIVO_MAPA_BAK)
    with open(ARQUIVO_MAPA, "w", encoding="utf-8") as f:
        json.dump(alunos_tokens, f, ensure_ascii=False)

def carregar_tokens():
    global alunos_tokens
    if os.path.exists(ARQUIVO_MAPA):
        try:
            if os.path.getsize(ARQUIVO_MAPA) == 0 and os.path.exists(ARQUIVO_MAPA_BAK):
                # Tenta backup se o principal estiver vazio
                with open(ARQUIVO_MAPA_BAK, "r", encoding="utf-8-sig") as f:
                    alunos_tokens = json.load(f) or {}
                return
                
            with open(ARQUIVO_MAPA, "r", encoding="utf-8-sig") as f:
                alunos_tokens = json.load(f) or {}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Aviso: arquivo {ARQUIVO_MAPA} corrompido ou erro de carregamento: {e}. Usando vazio.")
            alunos_tokens = {}
        except Exception as e:
            print(f"Erro ao carregar tokens: {e}")
            alunos_tokens = {}
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
                # Tabela alunos
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

                # Tabela presencas
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
    """
    CORREÇÃO DE DB: Busca o ID do aluno primeiro e usa para DELETE/INSERT.
    Toggle:
        - Se já tem presença hoje -> apaga (retorna "apagada")
        - Se não tem -> insere (retorna True)
        - Se falha -> False
    """
    conn = get_db_connection()
    if conn:
        try:
            with conn, conn.cursor() as cur:
                # 1. Obter o ID do aluno
                cur.execute("SELECT id FROM alunos WHERE nome = %s", (nome_aluno,))
                aluno_row = cur.fetchone()
                if not aluno_row:
                    print(f"Aviso: Aluno '{nome_aluno}' não encontrado no DB para registro.")
                    return False

                aluno_id = aluno_row[0]

                # 2. Verificar se já existe presença hoje
                cur.execute("""
                    SELECT id FROM presencas
                    WHERE aluno_id = %s AND data_presenca = CURRENT_DATE
                """, (aluno_id,))
                row = cur.fetchone()

                if row:
                    # Se já tem presença hoje -> apaga
                    presenca_id = row[0]
                    cur.execute("DELETE FROM presencas WHERE id = %s", (presenca_id,))
                    return "apagada"

                # 3. Se não existe presença, insere nova entrada
                cur.execute("""
                    INSERT INTO presencas (aluno_id, data_presenca, confianca)
                    VALUES (%s, CURRENT_DATE, %s)
                """, (aluno_id, confianca))
                
                return True

        except Exception as e:
            print("Erro registrar_presenca:", e)
            return False

    return False


# ---------------- Util DeepFace local (Baseado na Versão B) ----------------
DB_PATH = PASTA_IMAGENS_CONHECIDAS

def deepface_find_on_frame(frame_rgb):
    """
    Recebe frame RGB (numpy) e retorna (status, best_row_dict, distance_col_name)
    status: 'ok' or 'none' or 'error'
    best_row_dict: dict com dados do melhor match (ou None)
    """
    try:
        resultados = DeepFace.find(
            img_path=frame_rgb,
            db_path=DB_PATH,
            model_name="VGG-Face",
            enforce_detection=DEEPFACE_ENFORCE_DETECTION,
            detector_backend="retinaface",
            silent=True
        )
    except Exception as e:
        return ("error", str(e), None)

    if not resultados or len(resultados) == 0 or resultados[0].empty:
        return ("none", None, None)

    df = resultados[0].copy()

    # localizar coluna de distância de forma robusta
    distance_col = None
    for c in df.columns:
        name = c.lower()
        if name in ["distance", "vgg-face_cosine"] or "cosine" in name or "euclidean" in name:
            distance_col = c
            break

    if distance_col is None or df[distance_col].isna().all():
        return ("none", None, None)

    # ordena pelo menor valor (melhor match)
    df_valid = df[df[distance_col].notna()].sort_values(by=distance_col, ascending=True).reset_index(drop=True)
    if df_valid.empty:
        return ("none", None, None)

    best = df_valid.iloc[0]
    # transforma em dict seguro
    best_dict = {col: (best[col] if col in best.index else None) for col in df_valid.columns}
    return ("ok", best_dict, distance_col)

def distance_to_confidence(distance):
    if distance is None:
        return 0.0
    try:
        # Padrão: 1 - distance * 100
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
            presente_bool = bool(presente)
            horario_str = horario.strftime('%H:%M:%S') if isinstance(horario, datetime) else None
            try:
                confianca_val = float(conf) if conf is not None else None
            except:
                confianca_val = None
            dados_formatados.append({
                "id": aluno_id,
                "nome": nome,
                "email_responsavel": email_resp or "",
                "presente": presente_bool,
                "horario": horario_str,
                "confianca": confianca_val
            })

        data_hoje = datetime.now().strftime('%d/%m/%Y')
        return render_template("admin.html",
                               dados=dados_formatados,
                               total_alunos=(stats[0] if stats else 0),
                               presentes_hoje=(stats[1] if stats else 0),
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


#aqui é onde elecadastra os alunos.

@app.route('/cadastrar_alunos', methods=['GET'])
def cadastrar_alunos():
    carregar_tokens()
    pasta = os.path.join(os.path.dirname(__file__), PASTA_ALUNOS)
    if not os.path.exists(pasta):
        return jsonify({"status": "error", "message": "❌ Pasta 'alunos' não encontrada."}), 404
    arquivos = [f for f in os.listdir(pasta) if not f.startswith('.')]
    if not arquivos:
        return jsonify({"status": "warning", "message": "⚠️ Nenhuma foto encontrada na pasta 'alunos'."}), 200
    log_messages = []
    #pega os arquivos da pasta alunos e verifica se exitem
    
    for foto in arquivos:
        nome = os.path.splitext(foto)[0]
        caminho_origem = os.path.join(pasta, foto)
        destino_dir = os.path.join(PASTA_IMAGENS_CONHECIDAS, nome)
        os.makedirs(destino_dir, exist_ok=True)
        destino_path = os.path.join(destino_dir, foto)
        #pega cada arquivo e copia para a pasta imagens_conhecidas/nome_do_aluno/foto.jpg
        
        try:
            copy2(caminho_origem, destino_path)
        except Exception as e:
            log_messages.append(f"❌ Erro ao copiar {foto}: {e}")
            continue
        
        face_token = os.path.relpath(destino_path, start=os.path.dirname(__file__))
        conn = get_db_connection()
        
        if not conn:
            log_messages.append(f"❌ Erro de conexão ao salvar {nome}.")
            continue
        #tenta salvar no banco
        try:
            with conn, conn.cursor() as cur:
                # 1. Tenta encontrar pelo nome
                cur.execute("SELECT id FROM alunos WHERE nome = %s", (nome,))
                existe = cur.fetchone()
                
                if existe:
                    # Aluno existe → apenas atualizar face_token
                    cur.execute("""
                        UPDATE alunos 
                        SET face_token = %s 
                        WHERE id = %s
                    """, (face_token, existe[0]))
                    log_messages.append(f"🔄 Aluno '{nome}' atualizado com novo face_token.")
                else:
                    # Não existe → criar novo aluno
                    cur.execute("""
                        INSERT INTO alunos (nome, face_token)
                        VALUES (%s, %s)
                        RETURNING id
                    """, (nome, face_token))
                    log_messages.append(f"✅ Aluno '{nome}' cadastrado com sucesso!")
                
                conn.commit()
        
        except Exception as e:
            log_messages.append(f"❌ Erro ao salvar '{nome}' no banco: {e}")
        finally:
            conn.close()

        # Atualiza mapa local
        alunos_tokens[nome] = face_token

    # Salvar tokens no JSON
    salvar_tokens()

    return jsonify({
        "status": "success",
        "message": "Cadastro concluído.",
        "log": log_messages
    }), 200


# Rota principal usada pelo seu front (converte, busca e registra)
@app.route('/chamada_webcam', methods=['POST'])
def chamada_webcam():
    try:
        data = request.get_json(silent=True)
        if not data or "image_data" not in data:
            return jsonify({"status": "erro", "message": "Imagem não recebida"}), 400

        raw = data["image_data"]
        
        # Trata prefixo data:image/jpeg;base64,
        if isinstance(raw, str) and ',' in raw:
            image_base64 = raw.split(',', 1)[1]
        else:
            image_base64 = raw

        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception:
            return jsonify({"status": "erro", "message": "Base64 inválido"}), 400

        np_arr = np.frombuffer(image_bytes, np.uint8)
        frame_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame_bgr is None:
            return jsonify({"status": "erro", "message": "Falha ao decodificar imagem (cv2)"}), 400

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        status, best, distance_col = deepface_find_on_frame(frame_rgb)
        
        if status == "error":
            return jsonify({"status": "erro", "message": f"DeepFace erro: {best}"}), 500
        if status == "none":
            return jsonify({"status": "nao_identificado", "aluno": None, "confidence": 0}), 200

        identity = best.get("identity") if isinstance(best.get("identity"), str) else None
        aluno_nome = None
        if identity:
            # Pega o nome da subpasta (esperado que seja o nome do aluno)
            aluno_nome = os.path.basename(os.path.dirname(identity))

        try:
            dist_val = float(best.get(distance_col))
            # Converte distância (0=melhor) para confiança (100=melhor)
            confidence = distance_to_confidence(dist_val)
        except Exception:
            confidence = 0.0

        # Usa o limite de confiança configurado
        if confidence < DEEPFACE_CONFIDENCE_THRESHOLD or not aluno_nome:
            return jsonify({"status": "nao_identificado", "aluno": None, "confidence": confidence}), 200

        try:
            # Chama a função de registro **corrigida**
            registro = registrar_presenca(aluno_nome, confidence)
        except Exception as e:
            return jsonify({"status": "erro", "message": f"Erro ao registrar presença: {e}"}), 500

        # Normaliza retorno para front
        if registro == "apagada":
            return jsonify({"status": "apagada", "nome": aluno_nome, "confidence": confidence}), 200
        elif registro is True:
            return jsonify({"status": "presente", "nome": aluno_nome, "confidence": confidence}), 200
        else:
            # Falha no DB (ex: aluno_nome não encontrado, mas não deveria acontecer se o DeepFace achou)
            return jsonify({"status": "erro", "message": "Falha ao registrar presença (DB)"}), 500

    except Exception as e:
        return jsonify({"status": "erro", "message": f"Erro geral: {str(e)}"}), 500

# Rota alternativa /reconhecer (compatibilidade)
@app.route('/reconhecer', methods=['POST'])
def reconhecer():
    # Esta rota é idêntica à chamada_webcam no fluxo de reconhecimento/registro
    return chamada_webcam()

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

# Scheduler (opcional)
def start_scheduler():
    if not email_ausentes or BackgroundScheduler is None or timezone is None:
        return
    tzname = os.getenv("TIMEZONE", "America/Sao_Paulo")
    try:
        tz = timezone(tzname)
        hour = int(os.getenv("EMAIL_SCHEDULE_HOUR", "18"))
        minute = int(os.getenv("EMAIL_SCHEDULE_MINUTE", "0"))
        sched = BackgroundScheduler(timezone=tz)
        sched.add_job(email_ausentes.main, "cron", hour=hour, minute=minute, id="avisos_diarios")
        sched.start()
        print(f"[SCHEDULER] Avisos diários agendados para {hour:02d}:{minute:02d} ({tzname})")
    except Exception as e:
        print(f"[SCHEDULER] Erro ao iniciar agendador: {e}")

if __name__ == '__main__':
    init_database()
    # garante pastas
    os.makedirs(PASTA_ALUNOS, exist_ok=True)
    os.makedirs(PASTA_IMAGENS_CONHECIDAS, exist_ok=True)
    # start_scheduler() # Descomente para iniciar o agendador
    print("🚀 Sistema iniciado (modo 100% local)!")
    print("- Interface: http://localhost:5000")
    print("- Admin: http://localhost:5000/admin")
    print("- API: POST http://localhost:5000/chamada_webcam (ou /reconhecer com campo 'imagem')")
    app.run(host='0.0.0.0', port=5000, debug=False)