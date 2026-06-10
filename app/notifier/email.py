import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import AppConfig
from app.notifier.base import NotificationChannel


class EmailNotifier(NotificationChannel):
    name = "email"

    def __init__(self, config: AppConfig):
        self.config = config

    @property
    def enabled(self):
        return self.config.email_enabled

    def notify(self, subject, body):
        if not self.enabled:
            return None

        message = MIMEMultipart()
        message["From"] = self.config.sender_email
        message["To"] = self.config.receiver_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain", "utf-8"))

        try:
            if self.config.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.config.smtp_server, self.config.smtp_port)
            else:
                server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
                server.starttls()

            server.login(self.config.smtp_username, self.config.smtp_password)
            server.send_message(message)
            server.quit()
            return {"ok": True, "channel": self.name}
        except Exception as exc:
            print(f"Failed to send email: {exc}")
            return {"ok": False, "channel": self.name, "error": str(exc)}


def send_email(config: AppConfig, subject, body):
    return EmailNotifier(config).notify(subject, body)
