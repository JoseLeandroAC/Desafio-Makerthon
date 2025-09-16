import os
import time
import smtplib
import psycopg  # psycopg v3
from email.message import EmailMessage
from string import Template
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

PG_CONN = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "alunossesi"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "1234"),
}

GMAIL_USER = os.getenv("GMAIL_USER", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()
DELAY_SECONDS = float(os.getenv("EMAIL_DELAY_SECONDS", "1"))

def load_text_template():
    path = "template_gmail.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return Template(f.read())
    return Template(
        "Olá,\n\n"
        "Informamos que ${aluno_nome} esteve ausente na escola no dia ${data}.\n\n"
        "Atenciosamente,\nEquipe Escolar"
    )

def get_absent_students(run_date: date | None = None, turno_filter: str | None = None):
    run_date = run_date or date.today()
    
    if turno_filter:
        sql = """
            SELECT a.nome, a.email_responsavel, a.turno
              FROM alunos a
         LEFT JOIN presencas p
                ON p.aluno_id = a.id
               AND p.data_presenca = %s
             WHERE (p.id IS NULL OR p.presente = FALSE)
               AND a.email_responsavel IS NOT NULL
               AND a.email_responsavel <> ''
               AND a.turno = %s
             ORDER BY a.nome;
        """
        with psycopg.connect(**PG_CONN) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (run_date, turno_filter))
                return cur.fetchall()
    else:
        sql = """
            SELECT a.nome, a.email_responsavel, a.turno
              FROM alunos a
         LEFT JOIN presencas p
                ON p.aluno_id = a.id
               AND p.data_presenca = %s
             WHERE (p.id IS NULL OR p.presente = FALSE)
               AND a.email_responsavel IS NOT NULL
               AND a.email_responsavel <> ''
             ORDER BY a.nome;
        """
        with psycopg.connect(**PG_CONN) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (run_date,))
                return cur.fetchall()

def send_absence_email(to_email: str, aluno_nome: str, turno: str, run_date: date | None = None):
    if not to_email or "@" not in to_email:
        print(f"[AVISO] {aluno_nome}: e-mail do responsável inválido/ausente ({to_email}).")
        return
    if not (GMAIL_USER and GMAIL_APP_PASSWORD):
        raise RuntimeError("Defina GMAIL_USER e GMAIL_APP_PASSWORD no .env")

    run_date = run_date or date.today()
    data_fmt = run_date.strftime("%d/%m/%Y")

    tpl = load_text_template()
    corpo = tpl.substitute(aluno_nome=aluno_nome, data=data_fmt, turno=turno)

    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = f"Aviso de ausência - {aluno_nome} ({turno})"
    msg.set_content(corpo)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)

def main(run_date: date | None = None, dry_run: bool = False, turno_filter: str | None = None):
    run_date = run_date or date.today()
    ausentes = get_absent_students(run_date, turno_filter)
    if not ausentes:
        turno_msg = f" ({turno_filter})" if turno_filter else ""
        print(f"[INFO] Nenhum ausente em {run_date.isoformat()}{turno_msg}.")
        return 0

    enviados = 0
    for nome, email_resp, turno in ausentes:
        if dry_run:
            print(f"[DRY-RUN] Enviaria para {nome} ({turno}) -> {email_resp}")
            continue
        try:
            send_absence_email(email_resp, nome, turno, run_date)
            enviados += 1
            print(f"[OK] Enviado -> {nome} ({turno}) -> {email_resp}")
            time.sleep(DELAY_SECONDS)  # 1s (ajustável via .env)
        except Exception as e:
            print(f"[ERRO] {nome} ({email_resp}): {e}")
    return enviados

if __name__ == "__main__":
    date_env = os.getenv("EMAIL_RUN_DATE")  # opcional: YYYY-MM-DD
    dry = os.getenv("EMAIL_DRY_RUN", "false").lower() in {"1", "true", "yes"}

    run_dt = None
    if date_env:
        try:
            run_dt = datetime.strptime(date_env, "%Y-%m-%d").date()
        except ValueError:
            print(f"[AVISO] EMAIL_RUN_DATE inválido: {date_env} (use YYYY-MM-DD)")

    main(run_dt, dry_run=dry)
