import os
import time
import smtplib
import psycopg2
from email.message import EmailMessage
from string import Template
from datetime import date
from dotenv import load_dotenv

load_dotenv()

PG_CONN = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "presenca_alunos"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

GMAIL_USER = os.getenv("GMAIL_USER", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()
DELAY_SECONDS = float(os.getenv("EMAIL_DELAY_SECONDS", "1"))

def load_text_template():
    path = "template_gmail.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return Template(f.read())
    # fallback se não achou template
    return Template(
        "Olá,\n\n"
        "Informamos que ${aluno_nome} esteve ausente na escola no dia ${data}.\n\n"
        "Atenciosamente,\nEquipe Escolar"
    )

def get_absent_students(run_date=None):
    run_date = run_date or date.today()
    sql = """
        SELECT a.nome, a.email_responsavel
          FROM alunos a
     LEFT JOIN presencas p
            ON p.aluno_id = a.id
           AND p.data_presenca = %s
         WHERE p.id IS NULL OR p.presente = FALSE
         ORDER BY a.nome;
    """
    with psycopg2.connect(**PG_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (run_date,))
            return cur.fetchall()

def send_absence_email(to_email, aluno_nome, run_date=None):
    if not to_email or "@" not in to_email:
        print(f"[AVISO] {aluno_nome}: e-mail do responsável inválido ou não definido.")
        return

    if not (GMAIL_USER and GMAIL_APP_PASSWORD):
        raise RuntimeError("GMAIL_USER ou GMAIL_APP_PASSWORD não definidos no .env")

    run_date = run_date or date.today()
    data_fmt = run_date.strftime("%d/%m/%Y")

    tpl = load_text_template()
    corpo = tpl.substitute(aluno_nome=aluno_nome, data=data_fmt)

    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = f"Aviso de ausência - {aluno_nome}"
    msg.set_content(corpo)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)

def main(run_date=None, dry_run=False):
    run_date = run_date or date.today()
    ausentes = get_absent_students(run_date)
    if not ausentes:
        print(f"[INFO] Nenhum aluno ausente em {run_date.isoformat()}.")
        return

    for nome, email_resp in ausentes:
        if dry_run:
            print(f"[DRY-RUN] Enviaria para {nome} -> {email_resp}")
        else:
            try:
                send_absence_email(email_resp, nome, run_date)
                print(f"[OK] Enviado -> {nome} ({email_resp})")
                time.sleep(DELAY_SECONDS)
            except Exception as e:
                print(f"[ERRO] {nome} ({email_resp}): {e}")

if __name__ == "__main__":
    main()
