import psycopg2
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': 'BancodadosOF'  # Nome do seu banco existente
}

def get_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return None

# Exemplo: Consultar todos os alunos
def listar_alunos():
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT id, nome, arm, presenca, horario, responsavel FROM alunos;")
        alunos = cur.fetchall()
        cur.close()
        conn.close()
        return alunos
    return []

if __name__ == "__main__":
    alunos = listar_alunos()
    for aluno in alunos:
        print(aluno)
