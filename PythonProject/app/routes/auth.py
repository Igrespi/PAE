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


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password) and user.is_admin:
            login_user(user, remember=False)
            session.permanent = False  # El servidor no fuerza guardar sesión en disco
            # Truco para asegurar cierres incluso con navegadores que restauran pestañas:
            session.modified = True
            session['sid'] = uuid.uuid4().hex
            session['nav_target'] = url_for('dashboard.index')
            session['nav_ts'] = int(time.time())
            next_page = request.args.get('next')
            flash('Sesion iniciada correctamente.', 'success')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            if user and not user.is_admin:
                current_app.logger.warning('Intento de login no admin usuario=%s ip=%s', username, request.remote_addr)
                flash('Acceso restringido a administradores.', 'danger')
            else:
                current_app.logger.warning('Login fallido para usuario=%s ip=%s', username, request.remote_addr)
                flash('Usuario o contrasena incorrectos.', 'danger')

    return render_template('auth/login.html')


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
