import os
import time
import smtplib
import psycopg2
from email.message import EmailMessage
from string import Template
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

# ---------------- DB / E-mail config ----------------
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

# ---------------- Template helpers ----------------
def load_text_template():
    """Carrega corpo do e-mail texto a partir de template_gmail.txt (opcional)."""
    path = "template_gmail.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return Template(f.read())
    # fallback
    fallback = (
        "Olá,\n\n"
        "Informamos que ${aluno_nome} esteve ausente na escola no dia ${data}.\n\n"
        "Pedimos atenção e acompanhamento para que ele(a) não perca o conteúdo.\n\n"
        "Atenciosamente,\nEquipe Escolar"
    )
    return Template(fallback)

def load_html_template():
    """Opcional: se existir template_gmail.html, envia multipart/alternative."""
    path = "template_gmail.html"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return Template(f.read())
    return None

# ---------------- Query ausentes ----------------
def get_absent_students(run_date: date | None = None):
    """
    Retorna [(nome, email_responsavel)] para alunos:
      - sem registro na data (LEFT JOIN NULL), ou
      - com registro presente = FALSE
    """
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
            rows = cur.fetchall()
    return rows  # [(nome, email), ...]

# ---------------- Envio ----------------
def send_absence_email(to_emails, aluno_nome, run_date: date | None = None):
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    recipients = [e.strip() for e in to_emails if e and "@" in e]
    if not recipients:
        print(f"[AVISO] {aluno_nome}: sem e-mail de responsável válido.")
        return

    if not (GMAIL_USER and GMAIL_APP_PASSWORD):
        raise RuntimeError("Defina GMAIL_USER e GMAIL_APP_PASSWORD no .env")

    run_date = run_date or date.today()
    data_fmt = run_date.strftime("%d/%m/%Y")

    text_tpl = load_text_template()
    text_body = text_tpl.substitute(aluno_nome=aluno_nome, data=data_fmt)

    html_tpl = load_html_template()

    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = f"Aviso de ausência - {aluno_nome}"

    # texto sempre
    msg.set_content(text_body)

    # html opcional
    if html_tpl:
        html_body = html_tpl.substitute(aluno_nome=aluno_nome, data=data_fmt)
        msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)

# ---------------- Main ----------------
def main(run_date: date | None = None, dry_run: bool = False):
    run_date = run_date or date.today()
    ausentes = get_absent_students(run_date)
    if not ausentes:
        print(f"[INFO] Nenhum ausente em {run_date.isoformat()}.")
        return

    print(f"[INFO] Ausentes em {run_date.isoformat()}: {len(ausentes)}")

    for nome, email_resp in ausentes:
        if dry_run:
            print(f"[DRY-RUN] Enviaria para {nome} -> {email_resp}")
            continue
        try:
            send_absence_email(email_resp, nome, run_date)
            print(f"[OK] Enviado -> {nome} ({email_resp})")
            time.sleep(DELAY_SECONDS)  # delay de 1s entre e-mails
        except Exception as e:
            print(f"[ERRO] {nome} ({email_resp}): {e}")

if __name__ == "__main__":
    # permite passar data via env (YYYY-MM-DD) e modo dry-run
    date_env = os.getenv("EMAIL_RUN_DATE")  # ex: 2025-09-15
    dry = os.getenv("EMAIL_DRY_RUN", "false").lower() in {"1", "true", "yes"}

    run_dt = None
    if date_env:
        try:
            run_dt = datetime.strptime(date_env, "%Y-%m-%d").date()
        except ValueError:
            print(f"[AVISO] EMAIL_RUN_DATE inválido: {date_env} (use YYYY-MM-DD)")

    main(run_dt, dry_run=dry)
