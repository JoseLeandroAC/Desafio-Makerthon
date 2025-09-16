import psycopg

try:
    # Conecta ao banco
    conn = psycopg.connect(
        host="localhost",
        dbname="alunossesi",
        user="postgres",
        password="1234",
        port=5432
    )
    print("Conexão com PostgreSQL bem-sucedida!")

    # Criar cursor e testar consulta
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM alunos;")
        rows = cur.fetchall()
        for row in rows:
            print(row)

    conn.close()
except Exception as e:
    print("Erro ao conectar:", e)
