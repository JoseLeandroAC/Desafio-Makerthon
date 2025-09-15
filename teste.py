import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

def send_test_email():
    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = "dede61727@gmail.com"  # Coloque seu e-mail de teste
    msg["Subject"] = "📩 Teste de envio com Python"
    msg.set_content("Olá!\n\nEste é um teste de envio de e-mail com Python + Gmail.\n\nSe você recebeu, está tudo funcionando! ✅")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        print("[OK] E-mail enviado com sucesso!")
    except Exception as e:
        print("[ERRO] Não foi possível enviar o e-mail:", e)

if __name__ == "__main__":
    send_test_email()
