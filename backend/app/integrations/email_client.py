import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from uuid import uuid4

from app.core.config import settings


class EmailClient:
    def send(self, receiver: str, subject: str, message: str, html_message: str | None = None) -> dict:
        missing_settings = [
            name
            for name, value in (
                ("SMTP_HOST", settings.SMTP_HOST),
                ("SMTP_USER", settings.SMTP_USER),
                ("SMTP_PASSWORD", settings.SMTP_PASSWORD),
            )
            if not value
        ]
        if missing_settings:
            return {
                "receiver": receiver,
                "status": "failed",
                "message_id": None,
                "error": f"SMTP chưa được cấu hình: thiếu {', '.join(missing_settings)}",
            }

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.FROM_EMAIL or settings.SMTP_USER
            msg["To"] = receiver
            msg.attach(MIMEText(message, "plain", "utf-8"))
            if html_message:
                msg.attach(MIMEText(html_message, "html", "utf-8"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], receiver, msg.as_string())
            return {"receiver": receiver, "status": "sent", "message_id": f"smtp-{uuid4()}", "error": None}
        except Exception as exc:
            return {"receiver": receiver, "status": "failed", "message_id": None, "error": str(exc)}


email_client = EmailClient()
