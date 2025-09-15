import psycopg2
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
        # Conecta ao PostgreSQL
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()
        
        
        cur.close()
        conn.close()
        
        # Conecta ao banco específico e cria as tabelas
        db_config_with_db = DB_CONFIG.copy()
        db_config_with_db['database'] = DB_NAME
        
        conn = psycopg2.connect(**db_config_with_db)
        cur = conn.cursor()
        
        # Cria as tabelas
        cur.execute("""
            CREATE TABLE alunos (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                face_token VARCHAR(255) UNIQUE NOT NULL,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE presencas (
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
        
        print("✅ Tabelas criadas!")
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Configurando PostgreSQL...")
    setup_database()
