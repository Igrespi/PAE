import os
from dotenv import load_dotenv

load_dotenv()


def _parse_alert_days(value):
    if not value:
        return [30, 15, 7, 1]
    parts = [p.strip() for p in value.split(',')]
    days = []
    for part in parts:
        if part.isdigit():
            days.append(int(part))
    return days or [30, 15, 7, 1]


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'clave-secreta-por-defecto')
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, '..', 'instance', 'prl.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    from datetime import timedelta
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=15)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1', 'yes')

    RATE_LIMIT_WINDOW_SEC = int(os.environ.get('RATE_LIMIT_WINDOW_SEC', 60))
    RATE_LIMIT_MAX = int(os.environ.get('RATE_LIMIT_MAX', 300))
    RATE_LIMIT_LOGIN_MAX = int(os.environ.get('RATE_LIMIT_LOGIN_MAX', 10))
    RATE_LIMIT_REGISTER_MAX = int(os.environ.get('RATE_LIMIT_REGISTER_MAX', 5))
    RATE_LIMIT_VERIFY_MAX = int(os.environ.get('RATE_LIMIT_VERIFY_MAX', 10))

    SECURITY_HEADERS_ENABLED = os.environ.get('SECURITY_HEADERS_ENABLED', 'True').lower() in ('true', '1', 'yes')
    SECURITY_LOG_PATH = os.environ.get(
        'SECURITY_LOG_PATH',
        os.path.join(BASE_DIR, '..', 'logs', 'app.log')
    )

    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max

    # Configuración de correo
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '')

    # Días antes de caducidad para alertas
    ALERT_DAYS = _parse_alert_days(os.environ.get('ALERT_DAYS'))
    ALERT_CHECK_INTERVAL_HOURS = int(os.environ.get('ALERT_CHECK_INTERVAL_HOURS', 24))

    HEARTBEAT_TIMEOUT_SEC = int(os.environ.get('HEARTBEAT_TIMEOUT_SEC', 20))

    N8N_API_KEY = os.environ.get('N8N_API_KEY', '')
    N8N_ALLOWED_IPS = [ip.strip() for ip in os.environ.get('N8N_ALLOWED_IPS', '127.0.0.1,::1').split(',') if ip.strip()]
