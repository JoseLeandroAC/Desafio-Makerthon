import psycopg
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
    'port': int(os.getenv('DB_PORT', 5432))
}

DB_NAME = os.getenv('DB_NAME', 'presenca_alunos')

def setup_database():
    try:
<<<<<<< HEAD
        # Conecta ao PostgreSQL (banco padrão postgres)
=======
        # Conecta ao PostgreSQL
>>>>>>> 8cb13ead408bcab59a326599052920c6f779d789
        conn = psycopg.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Verifica se o banco já existe, se não, cria
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"✅ Banco '{DB_NAME}' criado!")
        else:
            print(f"ℹ️ Banco '{DB_NAME}' já existe.")
        
        cur.close()
        conn.close()
        
        # Conecta ao banco específico e cria as tabelas
        db_config_with_db = DB_CONFIG.copy()
        db_config_with_db['dbname'] = DB_NAME
        
        conn = psycopg.connect(**db_config_with_db)
        cur = conn.cursor()
        
        # Cria as tabelas
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alunos (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                face_token VARCHAR(255) UNIQUE NOT NULL,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email_responsavel TEXT,
                turno VARCHAR(10) DEFAULT 'manhã'
            );
            
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
        
        # Adiciona coluna turno se não existir (migração)
        cur.execute("""
            ALTER TABLE alunos 
            ADD COLUMN IF NOT EXISTS turno VARCHAR(10) DEFAULT 'manhã'
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        
        print("✅ Tabelas criadas!")
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Configurando PostgreSQL...")
    setup_database()

def aluno_ausente(aluno_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT presenca, email_responsavel, nome
        FROM alunos
        WHERE id = %s
    """, (aluno_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None  # aluno não encontrado
    presenca, email_responsavel, nome = row
    return {
        "ausente": not presenca,  # True se presenca for False
        "email": email_responsavel,
        "nome": nome
    }

