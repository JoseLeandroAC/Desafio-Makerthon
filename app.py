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
PASTA_ALUNOS = "alunos"
PASTA_IMAGENS_CONHECIDAS = "imagens_conhecidas"
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

alunos_tokens = {}


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
            print(f"Erro ao criar tabelas: {e}")
        finally:
            conn.close()


def registrar_presenca(nome_aluno, confianca):
    conn = get_db_connection()
    if conn:
        try:
            with conn, conn.cursor() as cur:
                cur.execute("""
                    SELECT p.id FROM presencas p
                    JOIN alunos a ON p.aluno_id = a.id
                    WHERE a.nome = %s AND p.data_presenca = CURRENT_DATE
                """, (nome_aluno,))
                row = cur.fetchone()
                if row:
                    cur.execute("DELETE FROM presencas WHERE id = %s", (row[0],))
                    return "apagada"

                cur.execute("""
                    INSERT INTO presencas (aluno_id, presente, confianca)
                    SELECT id, TRUE, %s FROM alunos WHERE nome = %s
                """, (confianca, nome_aluno))

                if cur.rowcount == 0:
                    return False
                return True
        except Exception as e:
            print(f"Erro registrar presença: {e}")
            return False
        finally:
            conn.close()


# ---------------- DeepFace local ----------------

DB_PATH = PASTA_IMAGENS_CONHECIDAS


def deepface_search_frame(frame):
    """Busca rosto localmente usando DeepFace."""
    try:
        resultados = DeepFace.find(
            img_path=frame,
            db_path=DB_PATH,
            model_name="VGG-Face",
            detector_backend="opencv",
            enforce_detection=True,
            silent=True
        )

        if resultados and not resultados[0].empty:
            df = resultados[0]
            caminho = df.iloc[0]["identity"]
            distancia = float(df.iloc[0]["distance"])
            nome = caminho.split(os.path.sep)[-2]
            return {"found": True, "nome": nome, "distance": distancia}
        else:
            return {"found": False}

    except ValueError:
        return {"found": False, "error": "Nenhum rosto detectado"}
    except Exception as e:
        return {"found": False, "error": str(e)}


def distance_to_confidence(distance):
    if distance is None:
        return 0.0
    conf = 100 - (distance * 100)
    return round(max(0, min(100, conf)), 2)


# ---------------- Rotas ----------------

@app.route('/')
def index():
    return render_template("index.html")


@app.route('/admin')
def admin_panel():
    conn = get_db_connection()
    if not conn:
        return "Erro de banco"

    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                SELECT a.id, a.nome,
                       a.email_responsavel,
                       COALESCE(p.presente, FALSE),
                       p.horario_presenca,
                       p.confianca
                FROM alunos a
                LEFT JOIN presencas p ON a.id = p.aluno_id
                 AND p.data_presenca = CURRENT_DATE
                ORDER BY a.nome
            """)
            dados = cur.fetchall()

            cur.execute("""
                SELECT COUNT(DISTINCT a.id),
                       COUNT(CASE WHEN p.presente = TRUE THEN 1 END)
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
                'confianca': float(conf) if conf else None
            })

        return render_template("admin.html",
                               dados=dados_formatados,
                               total_alunos=stats[0],
                               presentes_hoje=stats[1],
                               data_hoje=datetime.now().strftime('%d/%m/%Y'))
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
        flash("Erro de banco.", "danger")
        return redirect(url_for("admin_panel"))

    try:
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE alunos SET email_responsavel = %s WHERE id = %s",
                        (novo_email, aluno_id))
        flash("E-mail atualizado.", "success")
    except Exception as e:
        flash(f"Erro: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("admin_panel"))


@app.route('/cadastrar_alunos')
def cadastrar_alunos():
    carregar_tokens()

    pasta = os.path.join(os.path.dirname(__file__), PASTA_ALUNOS)
    arquivos = [f for f in os.listdir(pasta) if not f.startswith('.')]

    logs = []

    for foto in arquivos:
        nome = os.path.splitext(foto)[0]
        origem = os.path.join(pasta, foto)

        destino_dir = os.path.join(DB_PATH, nome)
        os.makedirs(destino_dir, exist_ok=True)
        destino = os.path.join(destino_dir, foto)
        copy2(origem, destino)

        face_token = os.path.relpath(destino)
        alunos_tokens[face_token] = nome

        conn = get_db_connection()
        if conn:
            try:
                with conn, conn.cursor() as cur:
                    cur.execute("SELECT id FROM alunos WHERE nome = %s", (nome,))
                    if cur.fetchone():
                        logs.append(f"{nome} já cadastrado.")
                    else:
                        cur.execute("INSERT INTO alunos (nome, face_token) VALUES (%s, %s)",
                                    (nome, face_token))
                        logs.append(f"{nome} cadastrado.")
            finally:
                conn.close()

    salvar_tokens()
    return jsonify({"status": "ok", "log": logs})


# ------------------- CHAMADA WEBCAM -------------------

@app.route('/chamada_webcam', methods=['POST'])
def chamada_webcam():
    carregar_tokens()

    data = request.get_json(silent=True)
    if not data or "image_data" not in data:
        return jsonify({"status": "error", "message": "Nenhuma imagem recebida."}), 400

    raw = data["image_data"]
    if "," in raw:
        raw = raw.split(",")[1]

    try:
        img_bytes = base64.b64decode(raw)
    except Exception:
        return jsonify({"status": "error", "message": "Base64 inválido."}), 400

    np_arr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({"status": "error", "message": "Imagem inválida."}), 400

    resultado = deepface_search_frame(frame)

    if resultado.get("found"):
        nome = resultado["nome"]
        conf = distance_to_confidence(resultado["distance"])

        if conf > 80:
            reg = registrar_presenca(nome, conf)

            if reg == "apagada":
                return jsonify({"status": "apagada", "nome": nome})

            return jsonify({"status": "presente", "nome": nome, "confidence": conf})

        else:
            return jsonify({"status": "nao_identificado",
                            "message": "Confiança baixa",
                            "confidence": conf})

    else:
        return jsonify({"status": "nao_detectado"}), 200


# ---------------- Presenças ----------------

@app.route('/presencas')
def ver_presencas():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Banco indisponível"})
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                SELECT a.nome, p.data_presenca, p.horario_presenca,
                       p.presente, p.confianca
                FROM presencas p
                JOIN alunos a ON p.aluno_id = a.id
                WHERE p.presente = TRUE
                ORDER BY p.data_presenca DESC, p.horario_presenca DESC
            """)
            dados = cur.fetchall()

        lista = []
        for nome, data_p, hora, pres, conf in dados:
            lista.append({
                "nome": nome,
                "data": data_p.strftime('%d/%m/%Y'),
                "horario": hora.strftime('%H:%M:%S'),
                "confianca": float(conf)
            })

        return jsonify({"presencas": lista})
    finally:
        conn.close()


# ---------------- Scheduler ----------------

def start_scheduler():
    pass  # opcional


# ---------------- MAIN ----------------

if __name__ == '__main__':
    init_database()
    print("\n🚀 Sistema LOCAL iniciado!")
    print("📌 Abra: http://localhost:5000\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
