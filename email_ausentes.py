import os
from string import Template
from datetime import datetime
import smtplib
from email.message import EmailMessage

# Configurações do Gmail (vai usar .env depois)
GMAIL_USER = os.getenv("GMAIL_USER", "seuemail@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "senha_app")

# ===========================
# Funções para processar ausentes
# ===========================

def get_absent_students():
    """
    Aqui será feita a conexão com o PostgreSQL depois.
    Por enquanto, retorna lista de teste.
    Cada item: (nome_aluno, email_responsavel)
    """
    # EXEMPLO DE TESTE:
    return [
        ("João Silva", "pai_joao@gmail.com"),
        ("Maria Oliveira", "mae_maria@gmail.com")
    ]

# ===========================
# Funções para e-mail
# ===========================

def load_template():
    """Carrega template do arquivo email_template.txt"""
    try:
        with open("email_template.txt", "r", encoding="utf-8") as f:
            return Template(f.read())
    except FileNotFoundError:
        # Template de fallback se não existir arquivo
        template_str = (
            "Olá,\n\n"
            "Informamos que {{aluno_nome}} esteve ausente na escola no dia {{data}}.\n\n"
            "Atenciosamente,\nEquipe Escolar"
        )
        return Template(template_str.replace("{{aluno_nome}}", "${aluno_nome}").replace("{{data}}", "${data}"))

def send_email(to_email, aluno_nome):
    """Envia e-mail usando template e SMTP do Gmail"""
    template = load_template()
    corpo = template.substitute(
        aluno_nome=aluno_nome,
        data=datetime.today().strftime("%d/%m/%Y")
    )

    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = f"Aviso de ausência - {aluno_nome}"
    msg.set_content(corpo)

    # Envio real via Gmail
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)
    print(f"[OK] E-mail enviado para {aluno_nome} -> {to_email}")

# ===========================
# Função principal
# ===========================

def main():
    ausentes = get_absent_students()
    if not ausentes:
        print("Nenhum aluno ausente hoje.")
        return

    for nome, email in ausentes:
        if not email:
            print(f"Atenção: {nome} não tem e-mail do responsável cadastrado.")
            continue
        try:
            send_email(email, nome)
        except Exception as e:
            print(f"[ERRO] Falha ao enviar para {nome} ({email}): {e}")

# ===========================
# Executar script direto
# ===========================

if __name__ == "__main__":
    main()
