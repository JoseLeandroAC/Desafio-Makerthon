# setup_db.py  — versão limpa
import os
import psycopg
from psycopg.rows import tuple_row
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "123456")
DB_NAME = os.getenv("DB_NAME", "presenca_alunos")

def create_database_if_needed():
    """Conecta no BD padrão (postgres) e cria DB_NAME se ainda não existir."""
    dsn_admin = {
        "host": DB_HOST, "port": DB_PORT,
        "user": DB_USER, "password": DB_PASS,
        "dbname": "postgres",
        "connect_timeout": 5,
    }
    try:
        with psycopg.connect(**dsn_admin) as conn:
            conn.execute("SET client_encoding TO 'UTF8';")
            with conn.cursor(row_factory=tuple_row) as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (DB_NAME,))
                exists = cur.fetchone()
                if not exists:
                    cur.execute(f'CREATE DATABASE "{DB_NAME}";')
                    print(f"✅ Banco {DB_NAME} criado.")
                else:
                    print(f"ℹ️  Banco {DB_NAME} já existe.")
    except Exception as e:
        print(f"❌ Erro ao criar/verificar banco: {e}")
        raise

def create_tables():
    """Conecta no DB_NAME e cria/ajusta as tabelas necessárias."""
    dsn_app = {
        "host": DB_HOST, "port": DB_PORT,
        "user": DB_USER, "password": DB_PASS,
        "dbname": DB_NAME,
        "connect_timeout": 5,
    }
    try:
        with psycopg.connect(**dsn_app) as conn:
            with conn.cursor() as cur:
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
                # garante coluna se tabela for antiga
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
            conn.commit()
            print("✅ Tabelas criadas/ajustadas com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")
        raise

def main():
    create_database_if_needed()
    create_tables()

if __name__ == "_main_":
    main()