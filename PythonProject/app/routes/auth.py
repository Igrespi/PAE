from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app, abort
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from app.models import User
from app.extensions import db, mail
import random
import re
import time
import uuid
from urllib.parse import urlparse

auth_bp = Blueprint('auth', __name__)

LOGIN_2FA_TTL_SEC = 300


def _clear_login_2fa_session():
    session.pop('login_2fa_user_id', None)
    session.pop('login_2fa_code', None)
    session.pop('login_2fa_ts', None)


def _send_login_2fa_code(user):
    code = str(random.randint(100000, 999999))
    session['login_2fa_user_id'] = user.id
    session['login_2fa_code'] = code
    session['login_2fa_ts'] = int(time.time())

    msg = Message("Codigo de acceso - Gestion PRL", recipients=[user.email])
    msg.body = (
        "Hola,\n\n"
        f"Tu codigo de acceso para iniciar sesion es: {code}\n\n"
        "Este codigo caduca en 5 minutos. Si no has solicitado este acceso, ignoralo."
    )
    mail.send(msg)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    _clear_login_2fa_session()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password) and user.is_admin:
            if user.username == 'admin':
                login_user(user, remember=False)
                session.permanent = False
                session.modified = True
                session['sid'] = uuid.uuid4().hex
                session['nav_target'] = url_for('dashboard.index')
                session['nav_ts'] = int(time.time())
                flash('Sesion iniciada correctamente.', 'success')
                return redirect(url_for('dashboard.index'))
            if not user.email:
                flash('Tu cuenta no tiene correo asignado. Contacta con soporte.', 'danger')
                return render_template('auth/login.html')
            try:
                _send_login_2fa_code(user)
                flash(f'Hemos enviado un codigo de acceso a tu correo ({user.email}).', 'info')
                return redirect(url_for('auth.login_verify'))
            except Exception as e:
                _clear_login_2fa_session()
                flash(f'Error al enviar el correo. Por favor contacta con soporte. ({str(e)})', 'danger')
                return render_template('auth/login.html')
        else:
            if user and not user.is_admin:
                current_app.logger.warning('Intento de login no admin usuario=%s ip=%s', username, request.remote_addr)
                flash('Acceso restringido a administradores.', 'danger')
            else:
                current_app.logger.warning('Login fallido para usuario=%s ip=%s', username, request.remote_addr)
                flash('Usuario o contrasena incorrectos.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/login/verify', methods=['GET', 'POST'])
def login_verify():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    user_id = session.get('login_2fa_user_id')
    code = session.get('login_2fa_code')
    ts = session.get('login_2fa_ts')

    if not user_id or not code or not ts:
        flash('No hay ningun inicio de sesion en proceso.', 'warning')
        return redirect(url_for('auth.login'))

    now_ts = int(time.time())
    if now_ts - int(ts) > LOGIN_2FA_TTL_SEC:
        _clear_login_2fa_session()
        flash('El codigo ha caducado. Inicia sesion de nuevo.', 'warning')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code_input = request.form.get('code', '').strip()
        if int(time.time()) - int(ts) > LOGIN_2FA_TTL_SEC:
            _clear_login_2fa_session()
            flash('El codigo ha caducado. Inicia sesion de nuevo.', 'warning')
            return redirect(url_for('auth.login'))
        if code_input != code:
            flash('Codigo incorrecto. Intentalo de nuevo.', 'danger')
            return render_template('auth/login_verify.html', expires_at=int(ts) + LOGIN_2FA_TTL_SEC)

        user = User.query.get(user_id)
        if not user or not user.is_admin:
            _clear_login_2fa_session()
            flash('No se pudo validar la cuenta. Inicia sesion de nuevo.', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=False)
        session.permanent = False
        session.modified = True
        session['sid'] = uuid.uuid4().hex
        session['nav_target'] = url_for('dashboard.index')
        session['nav_ts'] = int(time.time())
        _clear_login_2fa_session()
        flash('Sesion iniciada correctamente.', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login_verify.html', expires_at=int(ts) + LOGIN_2FA_TTL_SEC)


@auth_bp.route('/login/resend', methods=['POST'])
def login_resend_code():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    user_id = session.get('login_2fa_user_id')
    if not user_id:
        flash('No hay ningun inicio de sesion en proceso.', 'warning')
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    if not user or not user.is_admin or not user.email:
        _clear_login_2fa_session()
        flash('No se pudo reenviar el codigo. Inicia sesion de nuevo.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        _send_login_2fa_code(user)
        flash(f'Nuevo codigo enviado a {user.email}.', 'info')
    except Exception as e:
        flash(f'Error al reenviar el correo. ({str(e)})', 'danger')
    return redirect(url_for('auth.login_verify'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        dni = request.form.get('dni', '').strip().upper()
        email = request.form.get('email', '').strip().lower()
        telefono = request.form.get('telefono', '').strip()

        errors = []
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", username or ''):
            errors.append('El nombre de usuario debe tener entre 3 y 30 caracteres y solo letras, numeros, punto, guion o guion bajo.')
        if not password or len(password) < 6:
            errors.append('La contrasena debe tener al menos 6 caracteres.')
        if password != password2:
            errors.append('Las contraseas no coinciden.')
        if not dni:
            errors.append('El DNI/NIE es obligatorio.')
        elif not re.fullmatch(r"[A-Za-z0-9]{5,20}", dni):
            errors.append('El DNI/NIE solo puede contener letras y numeros (5-20 caracteres).')
        if not email or len(email) > 120:
            errors.append('El correo es obligatorio y debe ser valido.')
        if not telefono:
            errors.append('El telefono es obligatorio.')
        elif not telefono.isdigit() or not (9 <= len(telefono) <= 15):
            errors.append('El telefono solo puede tener numeros (9-15 digitos).')

        if User.query.filter_by(username=username).first():
            errors.append('Ese nombre de usuario ya esta en uso.')
        if User.query.filter_by(email=email).first():
            errors.append('Ese correo ya esta en uso.')
        if dni and User.query.filter_by(dni=dni).first():
            errors.append('Ese DNI/NIE ya esta en uso.')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/register.html', username=username, dni=dni, email=email, telefono=telefono)

        code = str(random.randint(100000, 999999))
        session['reg_dni'] = dni
        session['reg_username'] = username
        session['reg_password'] = password
        session['reg_email'] = email
        session['reg_telefono'] = telefono
        session['reg_code'] = code

        try:
            msg = Message("Codigo de verificacion - Gestion PRL",
                          recipients=[email])
            msg.body = (
                "Hola,\n\n"
                f"Tu codigo de verificacion para registrarte en la plataforma de RRHH es: {code}\n\n"
                "Si no has solicitado este registro ignoralo."
            )
            mail.send(msg)
            flash(f'Hemos enviado un codigo de verificacion a tu correo ({email}).', 'info')
            return redirect(url_for('auth.verify_email'))
        except Exception as e:
            flash(f'Error al enviar el correo. Por favor contacta con soporte. ({str(e)})', 'danger')

    return render_template('auth/register.html', username='', dni='', email='', telefono='')


@auth_bp.route('/verify', methods=['GET', 'POST'])
def verify_email():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if 'reg_code' not in session:
        flash('No hay ningun registro en proceso.', 'warning')
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        code_input = request.form.get('code', '').strip()
        if code_input == session['reg_code']:
            try:
                existing_user = User.query.filter(
                    (User.username == session['reg_username']) |
                    (User.email == session['reg_email']) |
                    (User.dni == session.get('reg_dni', ''))
                ).first()
                if existing_user:
                    flash('Ya existe una cuenta con esos datos. Inicia sesion o contacta con soporte.', 'danger')
                    return redirect(url_for('auth.login'))

                user = User(
                    username=session['reg_username'],
                    email=session['reg_email'],
                    nombre=session['reg_username'],
                    dni=session.get('reg_dni', ''),
                    telefono=session.get('reg_telefono', ''),
                    is_admin=True
                )
                user.set_password(session['reg_password'])
                db.session.add(user)
                db.session.commit()

                session.pop('reg_dni', None)
                session.pop('reg_username', None)
                session.pop('reg_password', None)
                session.pop('reg_email', None)
                session.pop('reg_telefono', None)
                session.pop('reg_code', None)

                flash('Cuenta creada y verificada exitosamente. Ya puedes iniciar sesion.', 'success')
                return redirect(url_for('auth.login'))
            except Exception as e:
                db.session.rollback()
                flash(f'Ocurrio un error al guardar el usuario: {str(e)}', 'danger')
        else:
            flash('Codigo incorrecto. Intentalo de nuevo.', 'danger')

    return render_template('auth/verify.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Sesion cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    if request.method == 'POST':
        # Todos los usarios son admin
        current_user.nombre = request.form.get('nombre', '')
        email = request.form.get('email', '').strip().lower()
        dni = request.form.get('dni', '').strip().upper()
        telefono = request.form.get('telefono', '').strip()

        if email:
            existing = User.query.filter(User.email == email, User.id != current_user.id).first()
            if existing:
                flash('Ese correo ya esta en uso por otra cuenta.', 'danger')
                return redirect(url_for('auth.perfil'))
            current_user.email = email

        if dni and not re.fullmatch(r"[A-Za-z0-9]{5,20}", dni):
            flash('El DNI/NIE solo puede contener letras y numeros (5-20 caracteres).', 'danger')
            return redirect(url_for('auth.perfil'))
        current_user.dni = dni

        if telefono and (not telefono.isdigit() or not (9 <= len(telefono) <= 15)):
            flash('El telefono solo puede tener numeros (9-15 digitos).', 'danger')
            return redirect(url_for('auth.perfil'))
        current_user.telefono = telefono

        new_password = request.form.get('new_password', '')
        if new_password:
            if len(new_password) < 6:
                flash('La contrasena debe tener al menos 6 caracteres.', 'danger')
                return redirect(url_for('auth.perfil'))
            current_user.set_password(new_password)

        db.session.commit()
        flash('Perfil actualizado correctamente.', 'success')
        return redirect(url_for('auth.perfil'))

    return render_template('auth/perfil.html')


@auth_bp.route('/perfil/delete', methods=['POST'])
@login_required
def delete_profile():
    user_id = current_user.id
    try:
        logout_user()
        session.clear()
        user = User.query.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()
        flash('Cuenta eliminada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'No se pudo eliminar la cuenta. ({str(e)})', 'danger')
    return redirect(url_for('auth.login'))


@auth_bp.route('/nav', methods=['POST'])
@login_required
def nav():
    target = request.form.get('target', '').strip()
    parsed = urlparse(target)
    if not parsed.path or parsed.scheme or parsed.netloc:
        flash('Destino no valido.', 'danger')
        return redirect(url_for('dashboard.index'))

    safe_target = parsed.path
    if parsed.query:
        safe_target += f"?{parsed.query}"

    session['nav_target'] = safe_target
    session['nav_ts'] = int(time.time())
    return redirect(safe_target)


@auth_bp.route('/heartbeat', methods=['POST'])
@login_required
def heartbeat():
    sid = session.get('sid')
    if sid:
        current_app.heartbeat[sid] = int(time.time())
    return '', 204
