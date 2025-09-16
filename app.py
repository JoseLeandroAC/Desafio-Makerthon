import os
import json
import base64
import requests
import psycopg  # psycopg v3
from datetime import datetime
from flask import Flask, request, jsonify, render_template, flash, redirect, url_for
from flask_cors import CORS
from io import BytesIO
from dotenv import load_dotenv

# Agendador
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

# módulo de envio
import email_ausentes

load_dotenv()

# Face++
API_KEY="8AJlG2cfflJOYShZZWl7VexpQ4JqXQgr"
API_SECRET="n-NGSPXVh5ppsfyIvm4--V97jfUHqq-_"
FACESET_ID = "ChamadaAlunos"
ARQUIVO_MAPA = "alunos_tokens.json"

# DB
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'dbname': os.getenv('DB_NAME', 'presenca_alunos'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '123456'),
    'port': int(os.getenv('DB_PORT', 5432))
}

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)
app.secret_key = os.getenv("FLASK_SECRET", "troque-esta-chave")
app.config['MAX_CONTENT_LENGTH'] = 3 * 1024 * 1024  # limite 3MB

alunos_tokens = {}

@app.after_request
def add_permissions_policy(resp):
    resp.headers['Permissions-Policy'] = "camera=(self), microphone=(self)"
    return resp

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
            print(f"Erro ao criar/ajustar tabelas: {e}")
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
                return True
        except Exception as e:
            print(f"Erro ao registrar presença: {e}")
            return False
        finally:
            conn.close()

def request_json_safe(method, url, **kwargs):
    try:
        resp = requests.request(method, url, timeout=15, **kwargs)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}", "content": resp.text[:200]}
        try:
            return resp.json()
        except ValueError:
            return {"error": "Resposta não é JSON", "content": resp.text[:200]}
    except requests.exceptions.RequestException as e:
        return {"error": "Falha de requisição", "detalhes": str(e)}

def _extract_image_stream(req):
    """Aceita JSON 'image_data' (dataURL/base64) ou multipart 'image_file'"""
    if req.is_json:
        payload = req.get_json(silent=True) or {}
        img = (payload.get("image_data") or "").strip()
        if img:
            try:
                b64 = img.split(",", 1)[1] if "," in img else img
                return BytesIO(base64.b64decode(b64))
            except Exception as e:
                raise ValueError(f"image_data inválido (base64): {e}")
    if "image_file" in req.files:
        f = req.files["image_file"]
        if not f or f.filename == "":
            raise ValueError("image_file vazio.")
        return BytesIO(f.read())
    raise ValueError("Nenhuma imagem recebida. Envie JSON 'image_data' ou form-data 'image_file'.")

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

@app.route('/admin/enviar_avisos')
def enviar_avisos():
    try:
        enviados = email_ausentes.main()
        if enviados:
            flash(f"Avisos enviados: {enviados}", "success")
        else:
            flash("Nenhum ausente hoje ou ninguém com e-mail cadastrado.", "info")
    except Exception as e:
        flash(f"Erro ao enviar avisos: {e}", "danger")
    return redirect(url_for("admin_panel"))

@app.route('/cadastrar_alunos', methods=['GET'])
def cadastrar_alunos():
    carregar_tokens()
    pasta = os.path.join(os.path.dirname(__file__), "alunos")
    if not os.path.exists(pasta):
        return jsonify({"status": "error", "message": "❌ Pasta 'alunos' não encontrada."}), 404
    arquivos = os.listdir(pasta)
    if not arquivos:
        return jsonify({"status": "warning", "message": "⚠️ Nenhuma foto encontrada na pasta 'alunos'."}), 200

    log_messages = []
    for foto in arquivos:
        nome = os.path.splitext(foto)[0]
        caminho = os.path.join(pasta, foto)
        with open(caminho, "rb") as f:
            detect_url = "https://api-us.faceplusplus.com/facepp/v3/detect"
            detect_response = request_json_safe(
                "POST",
                detect_url,
                files={"image_file": f},
                data={"api_key": API_KEY, "api_secret": API_SECRET}
            )
        if detect_response.get("faces"):
            face_token = detect_response["faces"][0]["face_token"]
            alunos_tokens[face_token] = nome
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
                            log_messages.append(f"✅ {nome} cadastrado com sucesso.")
                            addface_url = "https://api-us.faceplusplus.com/facepp/v3/faceset/addface"
                            request_json_safe(
                                "POST",
                                addface_url,
                                data={
                                    "api_key": API_KEY,
                                    "api_secret": API_SECRET,
                                    "outer_id": FACESET_ID,
                                    "face_tokens": face_token
                                }
                            )
                except Exception as e:
                    log_messages.append(f"❌ Erro ao salvar aluno {nome}: {e}")
                finally:
                    conn.close()
        else:
            erro = detect_response.get("error", "Nenhum rosto detectado")
            log_messages.append(f"❌ {nome}: {erro}")
    salvar_tokens()
    return jsonify({"status": "success", "message": "Cadastro concluído.", "log": log_messages}), 200

@app.route('/chamada_webcam', methods=['POST'])
def chamada_webcam():
    carregar_tokens()
    try:
        image_stream = _extract_image_stream(request)
    except ValueError as ve:
        return jsonify({"status": "error", "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Falha ao processar imagem: {e}"}), 400

    search_url = "https://api-us.faceplusplus.com/facepp/v3/search"
    response = request_json_safe(
        "POST",
        search_url,
        files={"image_file": image_stream},
        data={"api_key": API_KEY, "api_secret": API_SECRET, "outer_id": FACESET_ID}
    )

    if response.get("results"):
        aluno = response["results"][0]
        try:
            conf = float(aluno.get("confidence", 0))
        except Exception:
            conf = 0.0
        if conf > 80:
            token = aluno.get("face_token")
            nome = alunos_tokens.get(token, "Desconhecido")
            resultado = registrar_presenca(nome, conf)
            if resultado == "ja_presente":
                return jsonify({"status": "ja_presente", "nome": nome, "message": f"{nome} já está presente hoje!"})
            elif resultado:
                return jsonify({"status": "presente", "nome": nome, "confidence": conf})
            else:
                return jsonify({"status": "error", "message": "Erro ao registrar presença no banco."}), 500
        else:
            return jsonify({"status": "nao_identificado", "message": "Rosto detectado, mas não corresponde a nenhum aluno."}), 200

    if "error" in response:
        return jsonify({
            "status": "error",
            "message": f"Face++: {response.get('error')}",
            "raw": response.get("content")
        }), 502

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

# -------------- Scheduler --------------
def start_scheduler():
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
    if not os.path.exists("alunos"):
        os.makedirs("alunos")
    start_scheduler()
    print("🚀 Sistema iniciado!")
    print("- Interface: http://localhost:5000")
    print("- Admin: http://localhost:5000/admin")
    print("- API: http://localhost:5000/presencas")
    app.run(host='0.0.0.0', port=5000, debug=False)
