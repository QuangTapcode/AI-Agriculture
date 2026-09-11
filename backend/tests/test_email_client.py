from app.core.config import settings
from app.integrations.email_client import EmailClient


def test_email_client_reports_each_missing_smtp_setting(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")

    result = EmailClient().send("farmer@example.com", "AgriAI", "Test")

    assert result["status"] == "failed"
    assert result["error"] == "SMTP chưa được cấu hình: thiếu SMTP_USER, SMTP_PASSWORD"


def test_email_client_sends_through_configured_starttls_server(monkeypatch):
    class FakeSMTP:
        instance = None

        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.started_tls = False
            self.credentials = None
            self.sent = None
            FakeSMTP.instance = self

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self):
            self.started_tls = True

        def login(self, user, password):
            self.credentials = (user, password)

        def sendmail(self, sender, receiver, message):
            self.sent = (sender, receiver, message)

    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USER", "sender@example.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "app-password")
    monkeypatch.setattr(settings, "FROM_EMAIL", "AgriAI <sender@example.com>")
    monkeypatch.setattr("app.integrations.email_client.smtplib.SMTP", FakeSMTP)

    result = EmailClient().send("farmer@example.com", "AgriAI", "Nội dung")

    smtp = FakeSMTP.instance
    assert result["status"] == "sent"
    assert smtp.started_tls is True
    assert smtp.credentials == ("sender@example.com", "app-password")
    assert smtp.sent[0:2] == ("AgriAI <sender@example.com>", "farmer@example.com")
