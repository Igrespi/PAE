import os
import uuid
from datetime import date
from dateutil.relativedelta import relativedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, \
    current_app, send_from_directory, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import Employee, Document, DocumentType
from app.extensions import db
from app.utils.decorators import admin_required

file_manager_bp = Blueprint('file_manager', __name__, url_prefix='/gestion-documental')

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@file_manager_bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_required
def index():
    """Vista principal: lista de empleados con resumen de documentos."""
    if request.method == 'POST':
        action = request.form.get('action', '').strip()
        if action == 'clear':
            session.pop('fm_filters', None)
        else:
            session['fm_filters'] = {
                'search': request.form.get('search', '').strip(),
                'departamento': request.form.get('departamento', '').strip()
            }
        return redirect(url_for('file_manager.index'))

    filters = session.get('fm_filters', {})
    search = filters.get('search', '')
    departamento = filters.get('departamento', '').strip()

    query = Employee.query.filter_by(activo=True)

    if search:
        query = query.filter(
            db.or_(
                Employee.nombre.ilike(f'%{search}%'),
                Employee.apellidos.ilike(f'%{search}%'),
                Employee.dni.ilike(f'%{search}%'),
            )
        )

    if departamento:
        query = query.filter(Employee.departamento == departamento)

    empleados = query.order_by(Employee.apellidos, Employee.nombre).all()

    # Estadísticas por empleado
    empleados_data = []
    for emp in empleados:
        docs = emp.documents.all()
        total = len(docs)
        caducados = sum(1 for d in docs if d.estado == 'caducado')
        por_vencer = sum(1 for d in docs if d.estado == 'por_vencer')
        vigentes = sum(1 for d in docs if d.estado == 'vigente')
        tipos_count = len(set(d.document_type_id for d in docs if d.document_type_id))
        empleados_data.append({
            'employee': emp,
            'total': total,
            'caducados': caducados,
            'por_vencer': por_vencer,
            'vigentes': vigentes,
            'tipos_count': tipos_count
        })

    # Departamentos para filtro
    departamentos = db.session.query(Employee.departamento).distinct().filter(
        Employee.departamento != ''
    ).order_by(Employee.departamento).all()
    departamentos = [d[0] for d in departamentos]

    # Estadísticas globales
    total_docs = Document.query.count()
    total_tipos = DocumentType.query.count()

    return render_template('file_manager/index.html',
                           empleados_data=empleados_data,
                           search=search,
                           departamento=departamento,
                           departamentos=departamentos,
                           total_docs=total_docs,
                           total_tipos=total_tipos)


@file_manager_bp.route('/empleado/<int:id>')
@login_required
@admin_required
def employee_docs(id):
    """Vista de carpetas: documentos de un empleado organizados por tipo."""
    employee = Employee.query.get_or_404(id)
    documentos = employee.documents.order_by(Document.fecha_caducidad.asc()).all()

    # Obtener todos los tipos de documento del sistema
    all_tipos = DocumentType.query.order_by(DocumentType.nombre).all()

    # Agrupar documentos por tipo
    docs_por_tipo = {}
    for tipo in all_tipos:
        docs_por_tipo[tipo.id] = {
            'tipo': tipo,
            'nombre': tipo.nombre,
            'descripcion': tipo.descripcion,
            'obligatorio': tipo.obligatorio,
            'documentos': [],
            'caducados': 0,
            'por_vencer': 0,
            'vigentes': 0
        }

    # Documentos sin tipo (por si acaso)
    docs_sin_tipo = []

    for doc in documentos:
        tid = doc.document_type_id
        if tid and tid in docs_por_tipo:
            docs_por_tipo[tid]['documentos'].append(doc)
            estado = doc.estado
            if estado == 'caducado':
                docs_por_tipo[tid]['caducados'] += 1
            elif estado == 'por_vencer':
                docs_por_tipo[tid]['por_vencer'] += 1
            else:
                docs_por_tipo[tid]['vigentes'] += 1
        else:
            docs_sin_tipo.append(doc)

    # Separar tipos con documentos y vacíos
    tipos_con_docs = {k: v for k, v in docs_por_tipo.items() if v['documentos']}
    tipos_sin_docs = {k: v for k, v in docs_por_tipo.items() if not v['documentos']}

    # Resumen total
    total = len(documentos)
    caducados = sum(1 for d in documentos if d.estado == 'caducado')
    por_vencer = sum(1 for d in documentos if d.estado == 'por_vencer')
    vigentes = sum(1 for d in documentos if d.estado == 'vigente')

    # Filtro por tipo concreto (carpeta abierta)
    tipo_abierto = ''

    return render_template('file_manager/employee_docs.html',
                           employee=employee,
                           documentos=documentos,
                           tipos_con_docs=tipos_con_docs,
                           tipos_sin_docs=tipos_sin_docs,
                           docs_sin_tipo=docs_sin_tipo,
                           total=total,
                           caducados=caducados,
                           por_vencer=por_vencer,
                           vigentes=vigentes,
                           tipo_abierto=tipo_abierto)


@file_manager_bp.route('/por-tipo')
@login_required
@admin_required
def by_type():
    """Vista global: todos los documentos clasificados por tipo."""
    tipos = DocumentType.query.order_by(DocumentType.nombre).all()

    tipos_data = []
    for tipo in tipos:
        docs = tipo.documents.all()
        empleados_ids = set(d.employee_id for d in docs)
        empleados_list = Employee.query.filter(Employee.id.in_(empleados_ids)).all() if empleados_ids else []

        caducados = sum(1 for d in docs if d.estado == 'caducado')
        por_vencer = sum(1 for d in docs if d.estado == 'por_vencer')
        vigentes = sum(1 for d in docs if d.estado == 'vigente')

        tipos_data.append({
            'tipo': tipo,
            'total': len(docs),
            'caducados': caducados,
            'por_vencer': por_vencer,
            'vigentes': vigentes,
            'empleados': empleados_list,
            'documentos': docs
        })

    return render_template('file_manager/by_type.html', tipos_data=tipos_data)


@file_manager_bp.route('/empleado/<int:employee_id>/documento/<int:doc_id>')
@login_required
@admin_required
def doc_detail(employee_id, doc_id):
    """Detalle de un documento dentro del contexto de Gestión Documental."""
    employee = Employee.query.get_or_404(employee_id)
    doc = Document.query.get_or_404(doc_id)
    if doc.employee_id != employee.id:
        flash('Este documento no pertenece al empleado indicado.', 'danger')
        return redirect(url_for('file_manager.employee_docs', id=employee.id))
    return render_template('file_manager/doc_detail.html', document=doc, employee=employee)


@file_manager_bp.route('/empleado/<int:employee_id>/documento/<int:doc_id>/descargar')
@login_required
@admin_required
def doc_download(employee_id, doc_id):
    """Descargar archivo desde contexto de Gestión Documental."""
    doc = Document.query.get_or_404(doc_id)
    if not doc.archivo_path:
        flash('Este documento no tiene archivo adjunto.', 'warning')
        return redirect(url_for('file_manager.doc_detail', employee_id=employee_id, doc_id=doc_id))
    upload_dir = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_dir, doc.archivo_path,
                               as_attachment=True,
                               download_name=doc.archivo_nombre)


@file_manager_bp.route('/empleado/<int:employee_id>/subir', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_doc(employee_id):
    """Subir documento a un empleado desde Gestión Documental."""
    employee = Employee.query.get_or_404(employee_id)

    if request.method == 'POST':
        try:
            document_type_id = int(request.form.get('document_type_id', 0))
            titulo = request.form.get('titulo', '').strip()
            fecha_emision_str = request.form.get('fecha_emision', '')
            fecha_caducidad_str = request.form.get('fecha_caducidad', '')
            notas = request.form.get('notas', '').strip()
            calcular_auto = request.form.get('calcular_caducidad') == 'on'

            fecha_emision = date.fromisoformat(fecha_emision_str) if fecha_emision_str else date.today()

            fecha_caducidad = None
            if fecha_caducidad_str:
                fecha_caducidad = date.fromisoformat(fecha_caducidad_str)
            elif calcular_auto:
                tipo = DocumentType.query.get(document_type_id)
                if tipo and tipo.validez_meses:
                    fecha_caducidad = fecha_emision + relativedelta(months=tipo.validez_meses)

            archivo_nombre = ''
            archivo_path = ''
            file = request.files.get('archivo')
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_name = f"{uuid.uuid4().hex}_{filename}"
                upload_dir = current_app.config['UPLOAD_FOLDER']
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, unique_name)
                file.save(filepath)
                archivo_nombre = filename
                archivo_path = unique_name

            doc = Document(
                employee_id=employee.id,
                document_type_id=document_type_id,
                titulo=titulo,
                archivo_nombre=archivo_nombre,
                archivo_path=archivo_path,
                fecha_emision=fecha_emision,
                fecha_caducidad=fecha_caducidad,
                notas=notas,
                uploaded_by=current_user.id
            )

            db.session.add(doc)
            db.session.commit()
            flash(f'Documento "{titulo}" subido correctamente.', 'success')
            return redirect(url_for('file_manager.employee_docs', id=employee.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al subir documento: {str(e)}', 'danger')

    tipos = DocumentType.query.order_by(DocumentType.nombre).all()
    tipo_preselect = ''

    return render_template('file_manager/upload_doc.html',
                           employee=employee,
                           tipos=tipos,
                           tipo_preselect=tipo_preselect)


@file_manager_bp.route('/empleado/<int:employee_id>/documento/<int:doc_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def doc_edit(employee_id, doc_id):
    """Editar documento desde contexto de Gestión Documental."""
    employee = Employee.query.get_or_404(employee_id)
    doc = Document.query.get_or_404(doc_id)
    if doc.employee_id != employee.id:
        flash('Este documento no pertenece al empleado indicado.', 'danger')
        return redirect(url_for('file_manager.employee_docs', id=employee.id))

    if request.method == 'POST':
        try:
            doc.document_type_id = int(request.form.get('document_type_id', doc.document_type_id))
            doc.titulo = request.form.get('titulo', '').strip()
            doc.notas = request.form.get('notas', '').strip()

            fecha_emision_str = request.form.get('fecha_emision', '')
            if fecha_emision_str:
                doc.fecha_emision = date.fromisoformat(fecha_emision_str)

            fecha_caducidad_str = request.form.get('fecha_caducidad', '')
            if fecha_caducidad_str:
                doc.fecha_caducidad = date.fromisoformat(fecha_caducidad_str)
            elif request.form.get('sin_caducidad') == 'on':
                doc.fecha_caducidad = None

            file = request.files.get('archivo')
            if file and file.filename and allowed_file(file.filename):
                if doc.archivo_path:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.archivo_path)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                filename = secure_filename(file.filename)
                unique_name = f"{uuid.uuid4().hex}_{filename}"
                upload_dir = current_app.config['UPLOAD_FOLDER']
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, unique_name)
                file.save(filepath)
                doc.archivo_nombre = filename
                doc.archivo_path = unique_name

            db.session.commit()
            flash('Documento actualizado correctamente.', 'success')
            return redirect(url_for('file_manager.doc_detail', employee_id=employee.id, doc_id=doc.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'danger')

    tipos = DocumentType.query.order_by(DocumentType.nombre).all()
    return render_template('file_manager/edit_doc.html',
                           document=doc,
                           employee=employee,
                           tipos=tipos)


@file_manager_bp.route('/empleado/<int:employee_id>/documento/<int:doc_id>/eliminar', methods=['POST'])
@login_required
@admin_required
def doc_delete(employee_id, doc_id):
    """Eliminar documento desde contexto de Gestión Documental."""
    doc = Document.query.get_or_404(doc_id)
    titulo = doc.titulo
    try:
        if doc.archivo_path:
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.archivo_path)
            if os.path.exists(filepath):
                os.remove(filepath)
        db.session.delete(doc)
        db.session.commit()
        flash(f'Documento "{titulo}" eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'danger')
    return redirect(url_for('file_manager.employee_docs', id=employee_id))
