from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_required
from datetime import date, timedelta
from app.models import NotificationLog, Employee, Document, DocumentType
from app.extensions import db
from app.utils.decorators import admin_required
from app.utils.settings import get_alert_days, get_alert_interval_hours, set_alert_days, set_alert_interval_hours, parse_alert_days

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notificaciones')


@notifications_bp.route('/configurar', methods=['POST'])
@login_required
@admin_required
def update_settings():
    alert_days_text = request.form.get('alert_days', '').strip()
    interval_hours_text = request.form.get('alert_interval_hours', '').strip()

    days = parse_alert_days(alert_days_text)
    if not days:
        flash('Debes indicar al menos un dia de alerta valido.', 'warning')
        return redirect(url_for('notifications.history'))

    try:
        interval_hours = int(interval_hours_text)
    except ValueError:
        flash('El intervalo debe ser un numero entero de horas.', 'warning')
        return redirect(url_for('notifications.history'))

    if interval_hours < 1 or interval_hours > 168:
        flash('El intervalo debe estar entre 1 y 168 horas.', 'warning')
        return redirect(url_for('notifications.history'))

    set_alert_days(days)
    set_alert_interval_hours(interval_hours)

    scheduler = getattr(current_app, 'scheduler', None)
    if scheduler and scheduler.get_job('check_notifications'):
        scheduler.reschedule_job('check_notifications', trigger='interval', hours=interval_hours)

    flash('Configuracion de alertas actualizada.', 'success')
    return redirect(url_for('notifications.history'))


@notifications_bp.route('/vaciar', methods=['POST'])
@login_required
@admin_required
def clear_history():
    try:
        deleted = NotificationLog.query.delete()
        db.session.commit()
        flash(f'Se eliminaron {deleted} notificacion(es).', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al vaciar el historial: {str(e)}', 'danger')
    return redirect(url_for('notifications.history'))


@notifications_bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_required
def history():
    if request.method == 'POST':
        action = request.form.get('action', '').strip()
        if action == 'clear':
            session.pop('notif_filters', None)
        else:
            session['notif_filters'] = {
                'exitoso': request.form.get('exitoso', '').strip(),
                'tipo_alerta': request.form.get('tipo_alerta', '').strip(),
                'email_destino': request.form.get('email_destino', '').strip(),
                'employee_id': request.form.get('employee_id', '').strip()
            }
        return redirect(url_for('notifications.history'))

    filters = session.get('notif_filters', {})
    exitoso = filters.get('exitoso', '')
    tipo_alerta = filters.get('tipo_alerta', '')
    email_destino = filters.get('email_destino', '')
    employee_id = filters.get('employee_id', '')
    page = request.args.get('page', 1, type=int)

    query = NotificationLog.query

    if exitoso == '1':
        query = query.filter(NotificationLog.exitoso == True)
    elif exitoso == '0':
        query = query.filter(NotificationLog.exitoso == False)

    if tipo_alerta:
        query = query.filter(NotificationLog.tipo_alerta == tipo_alerta)

    if email_destino:
        query = query.filter(NotificationLog.email_destino.ilike(f"%{email_destino}%"))

    if employee_id.isdigit():
        query = query.filter(NotificationLog.employee_id == int(employee_id))

    query = query.order_by(NotificationLog.enviado_en.desc())
    pagination = query.paginate(page=page, per_page=20, error_out=False)

    # Datos para el envío manual
    empleados = Employee.query.filter_by(activo=True).order_by(Employee.apellidos).all()
    departamentos = db.session.query(Employee.departamento).distinct().filter(
        Employee.departamento != ''
    ).order_by(Employee.departamento).all()
    departamentos = [d[0] for d in departamentos]
    tipos_doc = DocumentType.query.order_by(DocumentType.nombre).all()

    default_days = current_app.config.get('ALERT_DAYS', [30, 15, 7, 1])
    default_interval = int(current_app.config.get('ALERT_CHECK_INTERVAL_HOURS', 24))
    alert_days = get_alert_days(default_days)
    alert_interval_hours = get_alert_interval_hours(default_interval)

    return render_template('notifications/history.html',
                           notifications=pagination.items,
                           pagination=pagination,
                           exitoso=exitoso,
                           empleados=empleados,
                           alert_days=alert_days,
                           alert_interval_hours=alert_interval_hours,
                           tipo_alerta=tipo_alerta,
                           email_destino=email_destino,
                           employee_id=employee_id,
                           departamentos=departamentos,
                           tipos_doc=tipos_doc)


@notifications_bp.route('/enviar-prueba', methods=['POST'])
@login_required
@admin_required
def send_test():
    """Envía un email de prueba para verificar la configuración SMTP."""
    email = request.form.get('email', '').strip()
    if not email:
        flash('Debes indicar un email de destino.', 'warning')
        return redirect(url_for('notifications.history'))

    from app.services import send_test_notification
    ok, mensaje = send_test_notification(email)

    if ok:
        flash(f'Email de prueba enviado correctamente a {email}', 'success')
    else:
        flash(f'Error al enviar email de prueba: {mensaje}', 'danger')

    return redirect(url_for('notifications.history'))


@notifications_bp.route('/enviar-manual', methods=['POST'])
@login_required
@admin_required
def send_manual():
    """Envía una notificación manual sobre un documento a un empleado o a un grupo filtrado."""
    employee_id = request.form.get('employee_id', 0, type=int)
    document_id = request.form.get('document_id', 0, type=int)
    departamento = request.form.get('departamento', '').strip()
    tipo_doc_id = request.form.get('document_type_id', '').strip()
    estado = request.form.get('estado', '').strip()

    from app.services import enviar_alerta_caducidad

    if employee_id:
        emp = Employee.query.get(employee_id)
        if not emp or not emp.email:
            flash('El empleado no tiene email configurado.', 'warning')
            return redirect(url_for('notifications.history'))

        if document_id:
            doc = Document.query.get(document_id)
            if not doc:
                flash('Documento no encontrado.', 'danger')
                return redirect(url_for('notifications.history'))

            dias = doc.dias_restantes if doc.dias_restantes is not None else 0
            enviar_alerta_caducidad(doc, dias, 'manual', emp.email)
            flash(f'Notificación sobre "{doc.titulo}" enviada a {emp.email}', 'success')
            return redirect(url_for('notifications.history'))

        docs = emp.documents.all()
        docs_alerta = [d for d in docs if d.estado in ('caducado', 'por_vencer')]
        if not docs_alerta:
            flash(f'{emp.nombre_completo} no tiene documentos caducados o por vencer.', 'info')
            return redirect(url_for('notifications.history'))

        for doc in docs_alerta:
            dias = doc.dias_restantes if doc.dias_restantes is not None else 0
            enviar_alerta_caducidad(doc, dias, 'manual', emp.email)

        flash(f'{len(docs_alerta)} notificación(es) enviada(s) a {emp.email}', 'success')
        return redirect(url_for('notifications.history'))

    # Envio masivo por filtros
    emp_query = Employee.query.filter_by(activo=True)
    if departamento:
        emp_query = emp_query.filter(Employee.departamento == departamento)

    empleados = emp_query.order_by(Employee.apellidos).all()
    if not empleados:
        flash('No hay empleados que coincidan con los filtros.', 'warning')
        return redirect(url_for('notifications.history'))

    docs_enviados = 0
    hoy = date.today()
    en_30 = hoy + timedelta(days=30)

    for emp in empleados:
        if not emp.email:
            continue

        doc_query = Document.query.filter(Document.employee_id == emp.id)
        if tipo_doc_id.isdigit():
            doc_query = doc_query.filter(Document.document_type_id == int(tipo_doc_id))

        if estado == 'caducado':
            doc_query = doc_query.filter(Document.fecha_caducidad < hoy, Document.fecha_caducidad.isnot(None))
        elif estado == 'por_vencer':
            doc_query = doc_query.filter(Document.fecha_caducidad >= hoy, Document.fecha_caducidad <= en_30)
        elif estado == 'vigente':
            doc_query = doc_query.filter(
                db.or_(Document.fecha_caducidad > en_30, Document.fecha_caducidad.is_(None))
            )

        docs = doc_query.all()
        for doc in docs:
            dias = doc.dias_restantes if doc.dias_restantes is not None else 0
            enviar_alerta_caducidad(doc, dias, 'manual', emp.email)
            docs_enviados += 1

    if docs_enviados == 0:
        flash('No se encontraron documentos para enviar con los filtros seleccionados.', 'info')
    else:
        flash(f'Notificaciones enviadas para {docs_enviados} documento(s).', 'success')

    return redirect(url_for('notifications.history'))


@notifications_bp.route('/ejecutar-revision', methods=['POST'])
@login_required
@admin_required
def run_check():
    """Ejecuta manualmente la revisión de documentos y envío de alertas."""
    from app.services import check_and_send_notifications
    try:
        check_and_send_notifications()
        flash('Revisión de documentos ejecutada. Revisa el historial para ver los resultados.', 'success')
    except Exception as e:
        flash(f'Error al ejecutar la revisión: {str(e)}', 'danger')

    return redirect(url_for('notifications.history'))
