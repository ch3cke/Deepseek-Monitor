import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import AppConfig


def send_email(config: AppConfig, subject, body):
    if not config.email_enabled:
        return None

    message = MIMEMultipart()
    message["From"] = config.sender_email
    message["To"] = config.receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain", "utf-8"))

    try:
        if config.smtp_port == 465:
            server = smtplib.SMTP_SSL(config.smtp_server, config.smtp_port)
        else:
            server = smtplib.SMTP(config.smtp_server, config.smtp_port)
            server.starttls()

        server.login(config.smtp_username, config.smtp_password)
        server.send_message(message)
        server.quit()
        return {"ok": True}
    except Exception as exc:
        print(f"Failed to send email: {exc}")
        return {"ok": False, "error": str(exc)}
