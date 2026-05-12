from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required
from app.models import Employee
from app.extensions import db
from app.utils.decorators import admin_required
from datetime import date
import re

employees_bp = Blueprint('employees', __name__, url_prefix='/empleados')


def _is_valid_name(value, min_len, max_len):
    if not value:
        return False
    if not (min_len <= len(value) <= max_len):
        return False
    return re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 ]+", value) is not None


def _is_valid_optional_text(value, max_len):
    if not value:
        return True
    if len(value) > max_len:
        return False
    return re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 ]+", value) is not None


def _is_valid_dni(value):
    return re.fullmatch(r"[A-Za-z0-9]{5,20}", value or "") is not None


def _is_valid_phone(value):
    return re.fullmatch(r"\d{9,15}", value or "") is not None


@employees_bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_required
def list():
    if request.method == 'POST':
        action = request.form.get('action', '').strip()
        if action == 'clear':
            session.pop('emp_filters', None)
        else:
            session['emp_filters'] = {
                'search': request.form.get('search', '').strip(),
                'departamento': request.form.get('departamento', '').strip(),
                'estado': request.form.get('estado', '').strip()
            }
        return redirect(url_for('employees.list'))

    filters = session.get('emp_filters', {})
    search = filters.get('search', '')
    departamento = filters.get('departamento', '')
    estado = filters.get('estado', '')
    page = request.args.get('page', 1, type=int)

    query = Employee.query

    if search:
        query = query.filter(
            db.or_(
                Employee.nombre.ilike(f'%{search}%'),
                Employee.apellidos.ilike(f'%{search}%'),
                Employee.dni.ilike(f'%{search}%'),
                Employee.email.ilike(f'%{search}%'),
            )
        )

    if departamento:
        query = query.filter(Employee.departamento == departamento)

    if estado == 'activo':
        query = query.filter(Employee.activo == True)
    elif estado == 'inactivo':
        query = query.filter(Employee.activo == False)

    query = query.order_by(Employee.apellidos, Employee.nombre)
    pagination = query.paginate(page=page, per_page=15, error_out=False)

    # Obtener departamentos únicos para el filtro
    departamentos = db.session.query(Employee.departamento).distinct().filter(
        Employee.departamento != ''
    ).order_by(Employee.departamento).all()
    departamentos = [d[0] for d in departamentos]

    return render_template('employees/list.html',
                           employees=pagination.items,
                           pagination=pagination,
                           search=search,
                           departamento=departamento,
                           estado=estado,
                           departamentos=departamentos)


@employees_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre', '').strip()
            apellidos = request.form.get('apellidos', '').strip()
            dni = request.form.get('dni', '').strip().upper()
            email = request.form.get('email', '').strip()
            telefono = request.form.get('telefono', '').strip()
            puesto = request.form.get('puesto', '').strip()
            departamento = request.form.get('departamento', '').strip()

            if not _is_valid_name(nombre, 2, 100):
                flash('El nombre solo puede contener letras y numeros (2-100 caracteres).', 'danger')
                return render_template('employees/form.html', employee=None)
            if not _is_valid_name(apellidos, 2, 150):
                flash('Los apellidos solo pueden contener letras y numeros (2-150 caracteres).', 'danger')
                return render_template('employees/form.html', employee=None)
            if not _is_valid_dni(dni):
                flash('El DNI/NIE solo puede contener letras y numeros (5-20 caracteres).', 'danger')
                return render_template('employees/form.html', employee=None)
            if telefono and not _is_valid_phone(telefono):
                flash('El telefono solo puede tener numeros (9-15 digitos).', 'danger')
                return render_template('employees/form.html', employee=None)
            if not _is_valid_optional_text(puesto, 100):
                flash('El puesto solo puede contener letras y numeros (max 100 caracteres).', 'danger')
                return render_template('employees/form.html', employee=None)
            if not _is_valid_optional_text(departamento, 100):
                flash('El departamento solo puede contener letras y numeros (max 100 caracteres).', 'danger')
                return render_template('employees/form.html', employee=None)

            if Employee.query.filter_by(dni=dni).first():
                flash('Ya existe un empleado con ese DNI/NIE.', 'danger')
                return render_template('employees/form.html', employee=None)

            if email:
                existing_email = Employee.query.filter(Employee.email == email).first()
                if existing_email:
                    flash('Ya existe un empleado con ese correo.', 'danger')
                    return render_template('employees/form.html', employee=None)

            employee = Employee(
                nombre=nombre,
                apellidos=apellidos,
                dni=dni,
                email=email,
                telefono=telefono,
                puesto=puesto,
                departamento=departamento,
                fecha_alta=date.fromisoformat(request.form.get('fecha_alta', str(date.today()))),
                activo=request.form.get('activo') == 'on'
            )
            db.session.add(employee)
            db.session.commit()
            flash(f'Empleado "{employee.nombre_completo}" creado correctamente.', 'success')
            return redirect(url_for('employees.detail', id=employee.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el empleado: {str(e)}', 'danger')

    return render_template('employees/form.html', employee=None)


@employees_bp.route('/<int:id>')
@login_required
@admin_required
def detail(id):
    employee = Employee.query.get_or_404(id)
    from app.models import Document
    documentos = employee.documents.order_by(Document.fecha_caducidad.asc()).all()

    # Agrupar documentos por tipo
    docs_por_tipo = {}
    for doc in documentos:
        tipo_nombre = doc.document_type.nombre if doc.document_type else 'Sin tipo'
        tipo_id = doc.document_type_id if doc.document_type else 0
        if tipo_id not in docs_por_tipo:
            docs_por_tipo[tipo_id] = {
                'nombre': tipo_nombre,
                'documentos': [],
                'caducados': 0,
                'por_vencer': 0,
                'vigentes': 0
            }
        docs_por_tipo[tipo_id]['documentos'].append(doc)
        estado = doc.estado
        if estado == 'caducado':
            docs_por_tipo[tipo_id]['caducados'] += 1
        elif estado == 'por_vencer':
            docs_por_tipo[tipo_id]['por_vencer'] += 1
        else:
            docs_por_tipo[tipo_id]['vigentes'] += 1

    # Ordenar por nombre de tipo
    docs_por_tipo_sorted = dict(sorted(docs_por_tipo.items(), key=lambda x: x[1]['nombre']))

    return render_template('employees/detail.html',
                           employee=employee,
                           documentos=documentos,
                           docs_por_tipo=docs_por_tipo_sorted)


@employees_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    employee = Employee.query.get_or_404(id)

    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre', '').strip()
            apellidos = request.form.get('apellidos', '').strip()
            dni = request.form.get('dni', '').strip().upper()
            email = request.form.get('email', '').strip()
            telefono = request.form.get('telefono', '').strip()
            puesto = request.form.get('puesto', '').strip()
            departamento = request.form.get('departamento', '').strip()

            if not _is_valid_name(nombre, 2, 100):
                flash('El nombre solo puede contener letras y numeros (2-100 caracteres).', 'danger')
                return render_template('employees/form.html', employee=employee)
            if not _is_valid_name(apellidos, 2, 150):
                flash('Los apellidos solo pueden contener letras y numeros (2-150 caracteres).', 'danger')
                return render_template('employees/form.html', employee=employee)
            if not _is_valid_dni(dni):
                flash('El DNI/NIE solo puede contener letras y numeros (5-20 caracteres).', 'danger')
                return render_template('employees/form.html', employee=employee)
            if telefono and not _is_valid_phone(telefono):
                flash('El telefono solo puede tener numeros (9-15 digitos).', 'danger')
                return render_template('employees/form.html', employee=employee)
            if not _is_valid_optional_text(puesto, 100):
                flash('El puesto solo puede contener letras y numeros (max 100 caracteres).', 'danger')
                return render_template('employees/form.html', employee=employee)
            if not _is_valid_optional_text(departamento, 100):
                flash('El departamento solo puede contener letras y numeros (max 100 caracteres).', 'danger')
                return render_template('employees/form.html', employee=employee)

            existing = Employee.query.filter(Employee.dni == dni, Employee.id != employee.id).first()
            if existing:
                flash('Ya existe otro empleado con ese DNI/NIE.', 'danger')
                return render_template('employees/form.html', employee=employee)

            if email:
                existing_email = Employee.query.filter(Employee.email == email, Employee.id != employee.id).first()
                if existing_email:
                    flash('Ya existe otro empleado con ese correo.', 'danger')
                    return render_template('employees/form.html', employee=employee)

            employee.nombre = nombre
            employee.apellidos = apellidos
            employee.dni = dni
            employee.email = email
            employee.telefono = telefono
            employee.puesto = puesto
            employee.departamento = departamento
            employee.fecha_alta = date.fromisoformat(request.form.get('fecha_alta', str(date.today())))
            employee.activo = request.form.get('activo') == 'on'

            db.session.commit()
            flash(f'Empleado "{employee.nombre_completo}" actualizado correctamente.', 'success')
            return redirect(url_for('employees.detail', id=employee.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'danger')

    return render_template('employees/form.html', employee=employee)


@employees_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def delete(id):
    employee = Employee.query.get_or_404(id)
    nombre = employee.nombre_completo
    try:
        db.session.delete(employee)
        db.session.commit()
        flash(f'Empleado "{nombre}" eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'danger')

    return redirect(url_for('employees.list'))
