from datetime import date
from flask import Blueprint, request, current_app, jsonify
from app.extensions import db
from app.models import Employee, Document, DocumentType
import uuid

integrations_bp = Blueprint('integrations', __name__, url_prefix='/api/n8n')


def _get_client_ip():
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or 'unknown'


def _extract_api_key():
    header_key = request.headers.get('X-API-KEY', '').strip()
    if header_key:
        return header_key
    auth = request.headers.get('Authorization', '').strip()
    if auth.lower().startswith('bearer '):
        return auth.split(' ', 1)[1].strip()
    return ''


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _split_nombre(full_name):
    parts = [p for p in (full_name or '').strip().split(' ') if p]
    if len(parts) < 2:
        return None, None
    return parts[0], ' '.join(parts[1:])


def _normalize_dni(value):
    return (value or '').strip().upper()


@integrations_bp.route('/documents', methods=['POST'])
def upsert_document_from_n8n():
    api_key = current_app.config.get('N8N_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'API key no configurada en servidor'}), 503

    provided_key = _extract_api_key()
    if not provided_key or provided_key != api_key:
        return jsonify({'error': 'No autorizado'}), 401

    allowed_ips = current_app.config.get('N8N_ALLOWED_IPS', ['127.0.0.1', '::1'])
    client_ip = _get_client_ip()
    if allowed_ips and client_ip not in allowed_ips:
        return jsonify({'error': 'IP no permitida'}), 403

    payload = request.get_json(silent=True) or {}

    empleado = payload.get('empleado') or {}
    doc = payload.get('documento') or {}

    dni = _normalize_dni(empleado.get('dni') or payload.get('empleado_dni'))
    if not dni:
        return jsonify({'error': 'Falta DNI del empleado'}), 400

    employee = Employee.query.filter_by(dni=dni).first()

    nombre = (empleado.get('nombre') or payload.get('empleado_nombre') or '').strip()
    apellidos = (empleado.get('apellidos') or payload.get('empleado_apellidos') or '').strip()

    if not employee and (not nombre or not apellidos):
        full_name = payload.get('empleado') or empleado.get('nombre_completo')
        if isinstance(full_name, str):
            nombre, apellidos = _split_nombre(full_name)

    if not employee and (not nombre or not apellidos):
        return jsonify({'error': 'Faltan datos de empleado (nombre y apellidos)'}), 400

    documento_titulo = (doc.get('titulo') or payload.get('documento_titulo') or '').strip()
    if not documento_titulo:
        return jsonify({'error': 'Falta titulo de documento'}), 400

    documento_tipo = (doc.get('tipo') or payload.get('documento_tipo') or 'General').strip()
    notas = (doc.get('notas') or payload.get('notas') or '').strip()
    fecha_emision = _parse_date(doc.get('fecha_emision') or payload.get('fecha_emision')) or date.today()
    fecha_caducidad = _parse_date(doc.get('fecha_caducidad') or payload.get('fecha_caducidad'))

    email = (empleado.get('email') or payload.get('empleado_email') or '').strip()
    telefono = (empleado.get('telefono') or payload.get('empleado_telefono') or '').strip()

    create_if_missing = payload.get('create_if_missing', True)
    if isinstance(create_if_missing, str):
        create_if_missing = create_if_missing.strip().lower() in ('1', 'true', 'yes')

    created_employee = False
    if not employee and create_if_missing:
        employee = Employee(
            nombre=nombre,
            apellidos=apellidos,
            dni=dni,
            email=email,
            telefono=telefono,
            puesto='',
            departamento='',
            activo=True
        )
        db.session.add(employee)
        created_employee = True

    if not employee:
        return jsonify({'error': 'Empleado no encontrado'}), 404

    document_type = DocumentType.query.filter_by(nombre=documento_tipo).first()
    created_document_type = False
    if not document_type:
        document_type = DocumentType(nombre=documento_tipo, descripcion='Creado automaticamente desde n8n')
        db.session.add(document_type)
        created_document_type = True

    db.session.flush()

    document = Document(
        employee=employee,
        document_type=document_type,
        titulo=documento_titulo,
        archivo_nombre='',
        archivo_path='',
        fecha_emision=fecha_emision,
        fecha_caducidad=fecha_caducidad,
        notas=notas,
        uploaded_by=None
    )

    try:
        db.session.add(document)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({'error': f'Error al guardar: {str(exc)}'}), 500

    return jsonify({
        'status': 'ok',
        'employee_id': employee.id,
        'document_id': document.id,
        'created_employee': created_employee,
        'created_document_type': created_document_type
    }), 201


@integrations_bp.route('/employees', methods=['POST'])
def create_employee_from_n8n():
    api_key = current_app.config.get('N8N_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'API key no configurada en servidor'}), 503

    provided_key = _extract_api_key()
    if not provided_key or provided_key != api_key:
        return jsonify({'error': 'No autorizado'}), 401

    allowed_ips = current_app.config.get('N8N_ALLOWED_IPS', ['127.0.0.1', '::1'])
    client_ip = _get_client_ip()
    if allowed_ips and client_ip not in allowed_ips:
        return jsonify({'error': 'IP no permitida'}), 403

    payload = request.get_json(silent=True) or {}

    dni = _normalize_dni(payload.get('dni'))
    if not dni:
        return jsonify({'error': 'Falta DNI del empleado'}), 400

    nombre = payload.get('nombre', '').strip()
    apellidos = payload.get('apellidos', '').strip()

    if not nombre or not apellidos:
        full_name = payload.get('nombre_completo')
        if isinstance(full_name, str):
            nombre, apellidos = _split_nombre(full_name)

    if not nombre or not apellidos:
        return jsonify({'error': 'Faltan datos de empleado (nombre y apellidos)'}), 400

    email = payload.get('email', '').strip()
    telefono = payload.get('telefono', '').strip()
    puesto = payload.get('puesto', '').strip()
    departamento = payload.get('departamento', '').strip()

    employee = Employee.query.filter_by(dni=dni).first()
    if employee:
        return jsonify({
            'status': 'exists',
            'employee_id': employee.id,
            'mensaje': 'El empleado ya existe en la base de datos'
        }), 200

    employee = Employee(
        nombre=nombre,
        apellidos=apellidos,
        dni=dni,
        email=email,
        telefono=telefono,
        puesto=puesto,
        departamento=departamento,
        activo=True
    )

    try:
        db.session.add(employee)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({'error': f'Error al guardar: {str(exc)}'}), 500

    return jsonify({
        'status': 'ok',
        'employee_id': employee.id,
        'mensaje': 'Empleado creado exitosamente'
    }), 201

