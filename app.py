import os
import json
import base64
import requests
import psycopg2
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from io import BytesIO
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurações Face++
API_KEY = "OUTmMmgnd1NZh3QIDYvqAZvD3Rv4cJjS"
API_SECRET = "TTvZC61AT3b71riYHtspWvU7CrYaNo7k"
FACESET_ID = "ChamadaAlunos"
ARQUIVO_MAPA = "alunos_tokens.json"

# Configurações PostgreSQL
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'presenca_alunos'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '123456'),
    'port': int(os.getenv('DB_PORT', 5432))
}

# Arquivo JSON com e-mails dos responsáveis
ARQUIVO_EMAILS = "alunos_emails.json"

app = Flask(__name__)
CORS(app)

alunos_tokens = {}

# ---------------- Funções auxiliares ----------------
def salvar_tokens():
    with open(ARQUIVO_MAPA, "w") as f:
        json.dump(alunos_tokens, f)

def carregar_tokens():
    global alunos_tokens
    if os.path.exists(ARQUIVO_MAPA):
        with open(ARQUIVO_MAPA, "r") as f:
            alunos_tokens = json.load(f)
    else:
        alunos_tokens = {}

def get_db_connection():
    """Conecta ao PostgreSQL"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco: {e}")
        return None

def init_database():
    """Cria/ajusta as tabelas necessárias"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            # Criação da tabela alunos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alunos (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(100) NOT NULL,
                    face_token VARCHAR(255) UNIQUE NOT NULL,
                    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    email_responsavel TEXT
                );
            """)

            # Garante a coluna email_responsavel mesmo se a tabela já existia
            cur.execute("""
                ALTER TABLE alunos
                ADD COLUMN IF NOT EXISTS email_responsavel TEXT;
            """)

            # Criação da tabela presencas
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

            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Erro ao criar/ajustar tabelas: {e}")

def registrar_presenca(nome_aluno, confianca):
    """Registra presença no banco - se já houver, apaga; caso contrário, insere"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            # Verifica se já existe presença hoje
            cur.execute("""
                SELECT p.id FROM presencas p
                JOIN alunos a ON p.aluno_id = a.id
                WHERE a.nome = %s AND p.data_presenca = CURRENT_DATE
            """, (nome_aluno,))

            resultado = cur.fetchone()

            if resultado:
                # Se já existe, apaga a presença
                presenca_id = resultado[0]
                cur.execute("DELETE FROM presencas WHERE id = %s", (presenca_id,))
                conn.commit()
                cur.close()
                conn.close()
                return "apagada"

            # Se não existe, insere nova presença
            cur.execute("""
                INSERT INTO presencas (aluno_id, presente, confianca) 
                SELECT id, TRUE, %s FROM alunos WHERE nome = %s
            """, (confianca, nome_aluno))
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Erro ao registrar presença: {e}")
            return False

def request_json_safe(method, url, **kwargs):
    """Faz requisição e garante retorno JSON seguro"""
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

# ---------------- Rotas ----------------
@app.route('/')
def index():
    return render_template("index.html")

@app.route('/admin')
def admin_panel():
    """Painel administrativo com relatório de presenças"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Buscar todas as presenças do dia atual
            cur.execute("""
                SELECT a.nome, 
                       COALESCE(p.presente, FALSE) as presente,
                       p.horario_presenca,
                       p.confianca
                FROM alunos a
                LEFT JOIN presencas p ON a.id = p.aluno_id 
                    AND p.data_presenca = CURRENT_DATE
                ORDER BY a.nome
            """)
            dados = cur.fetchall()

            # Buscar estatísticas gerais
            cur.execute("""
                SELECT 
                    COUNT(DISTINCT a.id) as total_alunos,
                    COUNT(CASE WHEN p.presente = TRUE THEN 1 END) as presentes_hoje
                FROM alunos a
                LEFT JOIN presencas p ON a.id = p.aluno_id 
                    AND p.data_presenca = CURRENT_DATE
            """)
            stats = cur.fetchone()

            cur.close()
            conn.close()

            # Formatar dados para o template
            dados_formatados = []
            for row in dados:
                dados_formatados.append({
                    'nome': row[0],
                    'presente': row[1],
                    'horario': row[2].strftime('%H:%M:%S') if row[2] else None,
                    'confianca': float(row[3]) if row[3] else None
                })

            data_hoje = datetime.now().strftime('%d/%m/%Y')

            return render_template("admin.html", 
                                   dados=dados_formatados, 
                                   total_alunos=stats[0], 
                                   presentes_hoje=stats[1],
                                   data_hoje=data_hoje)
        except Exception as e:
            return f"Erro: {e}"
    return "Erro de conexão com banco"

@app.route('/cadastrar_alunos', methods=['GET'])
def cadastrar_alunos():
    carregar_tokens()
    pasta = os.path.join(os.path.dirname(__file__), "alunos")

    # Carrega o arquivo JSON com emails
    if not os.path.exists(ARQUIVO_EMAILS):
        return jsonify({"status": "error", "message": f"❌ Arquivo {ARQUIVO_EMAILS} não encontrado."}), 404

    with open(ARQUIVO_EMAILS, "r", encoding="utf-8") as f:
        emails_map = json.load(f)

    if not os.path.exists(pasta):
        return jsonify({"status": "error", "message": "❌ Pasta 'alunos' não encontrada."}), 404

    arquivos = os.listdir(pasta)
    if not arquivos:
        return jsonify({"status": "warning", "message": "⚠️ Nenhuma foto encontrada na pasta 'alunos'."}), 200

    log_messages = []

    for foto in arquivos:
        nome = os.path.splitext(foto)[0]
        caminho = os.path.join(pasta, foto)

        # Detectar rosto usando Face++
        with open(caminho, "rb") as f_img:
            detect_url = "https://api-us.faceplusplus.com/facepp/v3/detect"
            detect_response = request_json_safe(
                "POST",
                detect_url,
                files={"image_file": f_img},
                data={"api_key": API_KEY, "api_secret": API_SECRET}
            )

        if detect_response.get("faces"):
            face_token = detect_response["faces"][0]["face_token"]
            alunos_tokens[face_token] = nome

            # Pega o e-mail do responsável a partir do JSON
            email_resp = emails_map.get(nome)
            if not email_resp:
                log_messages.append(f"⚠️ {nome} sem e-mail no arquivo JSON. Pulando cadastro.")
                continue

            # Salvar no PostgreSQL, evitando duplicados
            conn = get_db_connection()
            if conn:
                try:
                    cur = conn.cursor()
                    # Verifica se já existe aluno com o mesmo nome ou face_token
                    cur.execute("SELECT id FROM alunos WHERE nome = %s OR face_token = %s", (nome, face_token))
                    existente = cur.fetchone()

                    if existente:
                        log_messages.append(f"⚠️ {nome} já está cadastrado.")
                    else:
                        # Inserir novo aluno com email do responsável
                        cur.execute("""
                            INSERT INTO alunos (nome, face_token, email_responsavel) 
                            VALUES (%s, %s, %s)
                        """, (nome, face_token, email_resp))
                        conn.commit()
                        log_messages.append(f"✅ {nome} cadastrado com sucesso. E-mail do responsável: {email_resp}")

                        # Adicionar ao Face++ Faceset
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

                    cur.close()
                    conn.close()
                except Exception as e:
                    log_messages.append(f"❌ Erro ao salvar aluno {nome}: {e}")
        else:
            erro = detect_response.get("error", "Nenhum rosto detectado")
            log_messages.append(f"❌ {nome}: {erro}")

    salvar_tokens()
    return jsonify({"status": "success", "message": "Cadastro concluído.", "log": log_messages}), 200

@app.route('/chamada_webcam', methods=['POST'])
def chamada_webcam():
    carregar_tokens()
    data = request.get_json()

    if not data or "image_data" not in data:
        return jsonify({"status": "error", "message": "Nenhuma imagem recebida."}), 400

    image_data_base64 = data.get('image_data').split(',')[1]
    image_data_bytes = base64.b64decode(image_data_base64)
    image_stream = BytesIO(image_data_bytes)

    search_url = "https://api-us.faceplusplus.com/facepp/v3/search"
    response = request_json_safe(
        "POST",
        search_url,
        files={"image_file": image_stream},
        data={"api_key": API_KEY, "api_secret": API_SECRET, "outer_id": FACESET_ID}
    )

    if response.get("results"):
        aluno = response["results"][0]
        if aluno["confidence"] > 80:
            token = aluno["face_token"]
            nome = alunos_tokens.get(token, "Desconhecido")
            
            # Registra presença no PostgreSQL
            resultado = registrar_presenca(nome, aluno["confidence"])
            
            if resultado == "ja_presente":
                return jsonify({"status": "ja_presente", "nome": nome, "message": f"{nome} já está presente hoje!"})
            elif resultado:
                return jsonify({"status": "presente", "nome": nome, "confidence": aluno["confidence"]})
            else:
                return jsonify({"status": "error", "message": "Erro ao registrar presença no banco."})
        else:
            return jsonify({"status": "nao_identificado", "message": "Rosto detectado, mas não corresponde a nenhum aluno."})
    else:
        erro = response.get("error", "Nenhum rosto detectado")
        return jsonify({"status": "nao_detectado", "message": erro})

@app.route('/presencas')
def ver_presencas():
    """Mostra todas as presenças registradas em JSON"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT a.nome, p.data_presenca, p.horario_presenca, p.presente, p.confianca
                FROM presencas p
                JOIN alunos a ON p.aluno_id = a.id
                WHERE p.presente = TRUE
                ORDER BY p.data_presenca DESC, p.horario_presenca DESC
            """)
            presencas = cur.fetchall()
            cur.close()
            conn.close()
            
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
            return jsonify({"error": f"Erro ao consultar presenças: {e}"})
    return jsonify({"error": "Erro de conexão com banco"})

if __name__ == '__main__':
    # Inicializar banco de dados
    init_database()
    
    # Criar pasta de alunos se não existir
    if not os.path.exists("alunos"):
        os.makedirs("alunos")
    
    print("🚀 Sistema iniciado!")
    print("- Interface: http://localhost:5000")
    print("- Admin: http://localhost:5000/admin")
    print("- API: http://localhost:5000/presencas")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
