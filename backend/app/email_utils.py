# app/email_utils.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import (
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME,
    SMTP_PASSWORD, SMTP_FROM_EMAIL, SMTP_FROM_NAME
)
import random
import string

# Хранилище кодов подтверждения (в production используйте Redis или БД)
verification_codes = {}


def generate_verification_code(length: int = 6) -> str:
    """Генерирует 6-значный код подтверждения"""
    return ''.join(random.choices(string.digits, k=length))


def send_verification_email(email: str, code: str) -> bool:
    """Отправляет код подтверждения на email через Mailtrap"""
    try:
        # Создаем письмо
        msg = MIMEMultipart()
        msg['From'] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg['To'] = email
        msg['Subject'] = "Подтверждение регистрации в Humary"

        # HTML содержимое письма
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f4;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 500px;
                    margin: 50px auto;
                    background: white;
                    border-radius: 12px;
                    padding: 30px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                }}
                .code {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #6366f1;
                    text-align: center;
                    padding: 20px;
                    letter-spacing: 5px;
                }}
                .footer {{
                    text-align: center;
                    color: #888;
                    font-size: 12px;
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 style="color: #333; text-align: center;">Добро пожаловать в Humary!</h2>
                <p style="color: #555; text-align: center;">Ваш код подтверждения для регистрации:</p>
                <div class="code">{code}</div>
                <p style="color: #555; text-align: center;">Код действителен в течение 10 минут.</p>
                <p style="color: #555; font-size: 14px;">Если вы не регистрировались в Humary, просто проигнорируйте это письмо.</p>
                <div class="footer">
                    <p>© 2026 Humary. Все права защищены.</p>
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(html_body, 'html'))

        # Подключаемся к SMTP серверу (Mailtrap)
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()

        print(f"✅ Email sent to {email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


def store_verification_code(email: str, code: str):
    """Сохраняет код подтверждения"""
    verification_codes[email] = {
        "code": code,
        "expires_at": datetime.now() + timedelta(minutes=10)
    }


def verify_code(email: str, code: str) -> bool:
    """Проверяет код подтверждения"""
    from datetime import datetime

    if email not in verification_codes:
        return False

    stored = verification_codes[email]
    if datetime.now() > stored["expires_at"]:
        # Код истек
        del verification_codes[email]
        return False

    if stored["code"] == code:
        del verification_codes[email]
        return True

    return False