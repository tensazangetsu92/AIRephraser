# app/email_utils.py
import smtplib
import logging
import ssl
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import (
    SMTP_HOST, SMTP_PORT, SMTP_USE_SSL, SMTP_USERNAME,
    SMTP_PASSWORD, SMTP_FROM_EMAIL, SMTP_FROM_NAME
)
import random
import string
import secrets

# Хранилище кодов подтверждения (в production используйте Redis или БД)
verification_codes = {}
logger = logging.getLogger("uvicorn.error")


class VerificationEmailDeliveryError(RuntimeError):
    """Raised when the verification email could not be handed to SMTP."""


def _open_smtp_connection():
    """Open an encrypted SMTP connection using implicit SSL or STARTTLS."""
    tls_context = ssl.create_default_context()
    if SMTP_USE_SSL:
        return smtplib.SMTP_SSL(
            SMTP_HOST,
            SMTP_PORT,
            timeout=20,
            context=tls_context,
        )

    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
    server.ehlo()
    server.starttls(context=tls_context)
    server.ehlo()
    return server


def _send_message_via_smtp(message: MIMEMultipart) -> None:
    server = _open_smtp_connection()
    try:
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(message)
    finally:
        server.quit()


def generate_verification_code(length: int = 6) -> str:
    """Генерирует 6-значный код подтверждения"""
    return ''.join(random.choices(string.digits, k=length))


def generate_password_reset_code(length: int = 6) -> str:
    """Generate a cryptographically secure numeric password-reset code."""
    return ''.join(secrets.choice(string.digits) for _ in range(length))


def send_email_login_code(email: str, code: str) -> bool:
    """Send a passwordless sign-in code without exposing it in logs."""
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg['To'] = email
        msg['Subject'] = "Код входа в Humary"
        msg['Auto-Submitted'] = 'auto-generated'
        msg['X-Auto-Response-Suppress'] = 'OOF, DR, RN, NRN'

        html_body = f"""
        <!DOCTYPE html>
        <html lang="ru">
        <body style="margin:0;padding:24px;background:#1f1f1e;color:#dfded8;font-family:Arial,sans-serif;">
            <div style="max-width:480px;margin:0 auto;padding:28px;background:#292a31;border:1px solid #444552;border-radius:16px;">
                <h2 style="margin:0 0 14px;color:#f3f3f8;">Вход в Humary</h2>
                <p style="margin:0 0 18px;line-height:1.5;">Введите этот код на странице Humary. Если аккаунта ещё нет, он будет создан после подтверждения.</p>
                <div style="padding:15px;text-align:center;color:#f3f3f8;font-size:30px;font-weight:700;letter-spacing:6px;background:#25262d;border-radius:10px;">{code}</div>
                <p style="margin:18px 0 0;color:#c0c1ca;line-height:1.5;">Код действует 10 минут. Если вы не запрашивали вход, просто проигнорируйте это письмо.</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_body, 'html'))

        _send_message_via_smtp(msg)
        logger.info("Passwordless sign-in code email delivered")
        return True
    except Exception as error:
        logger.warning("Passwordless sign-in code email delivery failed: %s", error)
        return False


def send_password_reset_email(email: str, code: str) -> bool:
    """Send a one-time password reset code without exposing it in logs."""
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg['To'] = email
        msg['Subject'] = "Восстановление пароля в Humary"
        msg['Auto-Submitted'] = 'auto-generated'
        msg['X-Auto-Response-Suppress'] = 'OOF, DR, RN, NRN'

        html_body = f"""
        <!DOCTYPE html>
        <html lang="ru">
        <body style="margin:0;padding:24px;background:#1f1f1e;color:#dfded8;font-family:Arial,sans-serif;">
            <div style="max-width:480px;margin:0 auto;padding:28px;background:#292a31;border:1px solid #444552;border-radius:16px;">
                <h2 style="margin:0 0 14px;color:#f3f3f8;">Восстановление пароля</h2>
                <p style="margin:0 0 18px;line-height:1.5;">Введите этот код на странице Humary, чтобы задать новый пароль:</p>
                <div style="padding:15px;text-align:center;color:#f3f3f8;font-size:30px;font-weight:700;letter-spacing:6px;background:#25262d;border-radius:10px;">{code}</div>
                <p style="margin:18px 0 0;color:#c0c1ca;line-height:1.5;">Код действует 10 минут. Если вы не запрашивали смену пароля, просто проигнорируйте это письмо.</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_body, 'html'))

        _send_message_via_smtp(msg)
        return True
    except Exception as error:
        logger.warning("Password-reset email delivery failed: %s", error)
        return False


def send_verification_email(email: str, code: str) -> bool:
    """Отправляет код подтверждения на email через Mailtrap"""
    try:
        # Создаем письмо
        msg = MIMEMultipart()
        msg['From'] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg['To'] = email
        msg['Subject'] = "Подтверждение регистрации в Humary"

        msg['X-Priority'] = '3'  # Обычный приоритет
        msg['Importance'] = 'Normal'  # Нормальная важность
        msg['X-Mailer'] = 'Humary/1.0'  # Идентификация приложения
        msg['Auto-Submitted'] = 'auto-generated'  # Автоматическое письмо
        msg['X-Auto-Response-Suppress'] = 'OOF, DR, RN, NRN'  # Не отвечать автоматически
        msg['Precedence'] = 'bulk'  # Массовая рассылка

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
        _send_message_via_smtp(msg)

        logger.info("Verification email delivered")
        return True
    except Exception as e:
        logger.warning("Verification email delivery failed: %s", e)
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
