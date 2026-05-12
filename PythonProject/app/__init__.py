import os
import logging
from logging.handlers import RotatingFileHandler
from collections import defaultdict, deque
from flask import Flask
from app.config import Config
from app.extensions import db, login_manager, mail
from app.models import User
from sqlalchemy import text


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Crear carpeta de uploads
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Crear carpeta instance
    os.makedirs(os.path.join(app.root_path, '..', 'instance'), exist_ok=True)

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Registrar blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.employees import employees_bp
    from app.routes.clients import clients_bp
    from app.routes.documents import documents_bp
    from app.routes.document_types import document_types_bp
    from app.routes.reports import reports_bp
    from app.routes.notifications import notifications_bp
    from app.routes.file_manager import file_manager_bp
    from app.routes.integrations import integrations_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(document_types_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(file_manager_bp)
    app.register_blueprint(integrations_bp)

    # Crear tablas si no existen
    with app.app_context():
        db.create_all()

        # Migracion ligera de columnas nuevas en users
        try:
            cols = [row[1] for row in db.session.execute(text("PRAGMA table_info(users)"))]
            if 'dni' not in cols:
                db.session.execute(text("ALTER TABLE users ADD COLUMN dni VARCHAR(20)"))
            if 'telefono' not in cols:
                db.session.execute(text("ALTER TABLE users ADD COLUMN telefono VARCHAR(20)"))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Aviso: no se pudo actualizar la tabla users: {e}")

    # Configurar el scheduler de notificaciones
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()

        def job_notificaciones():
            with app.app_context():
                from app.services import check_and_send_notifications
                check_and_send_notifications()

        from app.utils.settings import get_alert_interval_hours

        # Ejecutar con intervalo configurable
        default_interval = int(app.config.get('ALERT_CHECK_INTERVAL_HOURS', 24))
        interval_hours = get_alert_interval_hours(default_interval)
        if interval_hours < 1:
            interval_hours = 1
        scheduler.add_job(
            func=job_notificaciones,
            trigger='interval',
            hours=interval_hours,
            id='check_notifications',
            replace_existing=True
        )

        scheduler.start()
        app.scheduler = scheduler
    except Exception as e:
        print(f"⚠️ No se pudo iniciar el scheduler de notificaciones: {e}")

    # Filtros de Jinja2 personalizados
    @app.template_filter('fecha')
    def fecha_filter(value, formato='%d/%m/%Y'):
        if value is None:
            return 'Sin fecha'
        return value.strftime(formato)

    @app.template_filter('fecha_hora')
    def fecha_hora_filter(value, formato='%d/%m/%Y %H:%M'):
        if value is None:
            return 'Sin fecha'
        return value.strftime(formato)

    from flask import session, redirect, url_for, request
    from flask_login import current_user, logout_user
    from urllib.parse import urlparse
    import time

    def _normalize_target(value):
        parsed = urlparse(value)
        if parsed.scheme or parsed.netloc:
            return None
        path = parsed.path or '/'
        if parsed.query:
            path += f"?{parsed.query}"
        return path

    @app.after_request
    def allow_redirect_target(response):
        if request.method in ('POST', 'PUT', 'DELETE') and response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get('Location')
            if location:
                target = _normalize_target(location)
                if target:
                    session['nav_target'] = target
                    session['nav_ts'] = int(time.time())
        return response

    @app.before_request
    def enforce_strict_navigation():
        if request.method != 'GET':
            return None
        if request.endpoint is None:
            return None
        if request.endpoint.startswith('static'):
            return None

        public_endpoints = {
            'auth.login',
            'auth.register',
            'auth.verify_email',
            'auth.logout',
            'dashboard.index',
        }
        if request.endpoint in public_endpoints:
            return None

        nav_target = session.get('nav_target')
        nav_ts = session.get('nav_ts')
        requested = _normalize_target(request.full_path.rstrip('?'))
        now_ts = int(time.time())

        if nav_target and nav_ts and requested == nav_target:
            if (now_ts - int(nav_ts)) <= 10:
                session.pop('nav_target', None)
                session.pop('nav_ts', None)
                session['last_allowed'] = requested
                session['last_allowed_ts'] = now_ts
                return None

        last_allowed = session.get('last_allowed')
        last_allowed_ts = session.get('last_allowed_ts')
        if last_allowed and last_allowed_ts and requested == last_allowed:
            if (now_ts - int(last_allowed_ts)) <= 30:
                return None

        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))

    @app.before_request
    def check_session_timeout():
        if current_user.is_authenticated:
            session.permanent = False
            now_ts = int(time.time())
            last_active = session.get('last_active')
            if last_active:
                diff = now_ts - int(last_active)
                if diff > 900:  # 15 minutes (900 seconds)
                    logout_user()
                    session.clear()
                    return redirect(url_for('auth.login', timeout='true'))
            session['last_active'] = now_ts

            sid = session.get('sid')
            if sid:
                last_seen = app.heartbeat.get(sid)
                timeout_sec = app.config.get('HEARTBEAT_TIMEOUT_SEC', 20)
                if last_seen and (now_ts - int(last_seen)) > timeout_sec:
                    logout_user()
                    session.clear()
                    app.heartbeat.pop(sid, None)
                    return redirect(url_for('auth.login'))

    # Logging basico de seguridad
    log_path = app.config.get('SECURITY_LOG_PATH')
    if log_path:
        log_dir = os.path.dirname(log_path)
        os.makedirs(log_dir, exist_ok=True)
        handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=5)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
        handler.setFormatter(formatter)
        if not app.logger.handlers:
            app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)

    # Rate limiting en memoria (local)
    app.rate_buckets = {
        'global': defaultdict(deque),
        'login': defaultdict(deque),
        'register': defaultdict(deque),
        'verify': defaultdict(deque)
    }

    # Heartbeat por sesion
    app.heartbeat = {}

    def _get_client_ip():
        forwarded = request.headers.get('X-Forwarded-For', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.remote_addr or 'unknown'

    def _check_limit(bucket_name, key, limit, window_sec):
        now = time.time()
        bucket = app.rate_buckets[bucket_name][key]
        while bucket and (now - bucket[0]) > window_sec:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True

    @app.before_request
    def rate_limit_guard():
        ip = _get_client_ip()
        window_sec = app.config.get('RATE_LIMIT_WINDOW_SEC', 60)
        global_limit = app.config.get('RATE_LIMIT_MAX', 300)
        if not _check_limit('global', ip, global_limit, window_sec):
            app.logger.warning('Rate limit global excedido desde %s', ip)
            return ('Demasiadas solicitudes. Intenta de nuevo en unos segundos.', 429)

        if request.method == 'POST':
            if request.endpoint == 'auth.login':
                limit = app.config.get('RATE_LIMIT_LOGIN_MAX', 10)
                if not _check_limit('login', ip, limit, window_sec):
                    app.logger.warning('Rate limit login excedido desde %s', ip)
                    return ('Demasiadas solicitudes de login. Espera y reintenta.', 429)
            elif request.endpoint == 'auth.register':
                limit = app.config.get('RATE_LIMIT_REGISTER_MAX', 5)
                if not _check_limit('register', ip, limit, window_sec):
                    app.logger.warning('Rate limit registro excedido desde %s', ip)
                    return ('Demasiadas solicitudes de registro. Espera y reintenta.', 429)
            elif request.endpoint == 'auth.verify_email':
                limit = app.config.get('RATE_LIMIT_VERIFY_MAX', 10)
                if not _check_limit('verify', ip, limit, window_sec):
                    app.logger.warning('Rate limit verificacion excedido desde %s', ip)
                    return ('Demasiadas solicitudes de verificacion. Espera y reintenta.', 429)

    @app.after_request
    def security_headers(response):
        if app.config.get('SECURITY_HEADERS_ENABLED', True):
            response.headers.setdefault('X-Content-Type-Options', 'nosniff')
            response.headers.setdefault('X-Frame-Options', 'DENY')
            response.headers.setdefault('Referrer-Policy', 'no-referrer')
            response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        return response

    return app

