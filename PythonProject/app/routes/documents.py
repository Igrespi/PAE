import os
import uuid
from datetime import date
from dateutil.relativedelta import relativedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, \
    current_app, send_from_directory, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import Document, Employee, DocumentType
from app.extensions import db
from app.utils.decorators import admin_required

documents_bp = Blueprint('documents', __name__, url_prefix='/documentos')

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@documents_bp.route('/', methods=['GET', 'POST'])
@login_required
def list():
    if request.method == 'POST':
        action = request.form.get('action', '').strip()
        if action == 'clear':
            session.pop('doc_filters', None)
        else:
            session['doc_filters'] = {
                'search': request.form.get('search', '').strip(),
                'estado': request.form.get('estado', '').strip(),
                'tipo_id': request.form.get('tipo_id', '').strip(),
                'empleado_id': request.form.get('empleado_id', '').strip(),
                'vista': request.form.get('vista', '').strip()
            }
        return redirect(url_for('documents.list'))

    filters = session.get('doc_filters', {})
    search = filters.get('search', '')
    estado = filters.get('estado', '')
    tipo_id = filters.get('tipo_id', '')
    empleado_id = filters.get('empleado_id', '')
    vista = filters.get('vista', '')
    page = request.args.get('page', 1, type=int)

    query = Document.query

    if search:
        query = query.join(Employee).filter(
            db.or_(Document.titulo.ilike(f'%{search}%'), Employee.apellidos.ilike(f'%{search}%'))
        )
    else:
        query = query.outerjoin(Employee)

    if tipo_id and tipo_id.isdigit():
        query = query.filter(Document.document_type_id == int(tipo_id))

    if empleado_id and empleado_id.isdigit():
        query = query.filter(Document.employee_id == int(empleado_id))

    # Filtrar por caducidad (estado virtual)
    hoy = date.today()
    from datetime import timedelta
    en_30 = hoy + timedelta(days=30)

    if estado == 'caducado':
        query = query.filter(Document.fecha_caducidad < hoy, Document.fecha_caducidad.isnot(None))
    elif estado == 'por_vencer':
        query = query.filter(Document.fecha_caducidad >= hoy, Document.fecha_caducidad <= en_30)
    elif estado == 'vigente':
        query = query.filter(
            db.or_(Document.fecha_caducidad > en_30, Document.fecha_caducidad.is_(None))
        )

    query = query.order_by(Document.fecha_caducidad.asc().nulls_last())
    pagination = query.paginate(page=page, per_page=15, error_out=False)
    documents = pagination.items

    empleados = Employee.query.filter_by(activo=True).order_by(Employee.apellidos).all()
    tipos = DocumentType.query.order_by(DocumentType.nombre).all()

    # Preparar datos para vista de carpetas (tipos)
    tipos_data = []
    for tipo in tipos:
        t_query = Document.query.filter_by(document_type_id=tipo.id)
        if search:
            t_query = t_query.join(Employee).filter(
                db.or_(Document.titulo.ilike(f'%{search}%'), Employee.apellidos.ilike(f'%{search}%'), Employee.nombre.ilike(f'%{search}%'))
            )
        if empleado_id and empleado_id.isdigit():
            t_query = t_query.filter(Document.employee_id == int(empleado_id))

        docs_tipo = t_query.all()
        vigentes = 0
        por_vencer = 0
        caducados = 0
        for d in docs_tipo:
            if d.estado == 'caducado':
                caducados += 1
            elif d.estado == 'por_vencer':
                por_vencer += 1
            else:
                vigentes += 1

        tipos_data.append({
            'tipo': tipo,
            'total': len(docs_tipo),
            'vigentes': vigentes,
            'por_vencer': por_vencer,
            'caducados': caducados,
            'documentos': docs_tipo
        })

    return render_template('documents/list.html',
                           pagination=pagination,
                           documents=documents,
                           search=search,
                           estado=estado,
                           tipo_id=tipo_id,
                           empleado_id=empleado_id,
                           empleados=empleados,
                           tipos=tipos,
                           tipos_data=tipos_data,
                           vista=vista)


@documents_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    if request.method == 'POST':
        try:
            employee_id = int(request.form.get('employee_id', 0))
            document_type_id = int(request.form.get('document_type_id', 0))
            titulo = request.form.get('titulo', '').strip()
            fecha_emision_str = request.form.get('fecha_emision', '')
            fecha_caducidad_str = request.form.get('fecha_caducidad', '')
            notas = request.form.get('notas', '').strip()
            calcular_auto = request.form.get('calcular_caducidad') == 'on'

            fecha_emision = date.fromisoformat(fecha_emision_str) if fecha_emision_str else date.today()

            # Calcular fecha de caducidad
            fecha_caducidad = None
            if fecha_caducidad_str:
                fecha_caducidad = date.fromisoformat(fecha_caducidad_str)
            elif calcular_auto:
                tipo = DocumentType.query.get(document_type_id)
                if tipo and tipo.validez_meses:
                    fecha_caducidad = fecha_emision + relativedelta(months=tipo.validez_meses)

            # Procesar archivo
            archivo_nombre = ''
            archivo_path = ''
            file = request.files.get('archivo')
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Añadir UUID para evitar colisiones
                unique_name = f"{uuid.uuid4().hex}_{filename}"
                upload_dir = current_app.config['UPLOAD_FOLDER']
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, unique_name)
                file.save(filepath)
                archivo_nombre = filename
                archivo_path = unique_name

            doc = Document(
                employee_id=employee_id,
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
            return redirect(url_for('documents.detail', id=doc.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear documento: {str(e)}', 'danger')

    empleados = Employee.query.filter_by(activo=True).order_by(Employee.apellidos).all()
    tipos = DocumentType.query.order_by(DocumentType.nombre).all()
    employee_preselect = ''

    return render_template('documents/form.html',
                           document=None,
                           empleados=empleados,
                           tipos=tipos,
                           employee_preselect=employee_preselect)


@documents_bp.route('/<int:id>')
@login_required
def detail(id):
    doc = Document.query.get_or_404(id)
    return render_template('documents/detail.html', document=doc)


@documents_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    doc = Document.query.get_or_404(id)

    if request.method == 'POST':
        try:
            doc.employee_id = int(request.form.get('employee_id', doc.employee_id))
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

            # Nuevo archivo (opcional)
            file = request.files.get('archivo')
            if file and file.filename and allowed_file(file.filename):
                # Eliminar archivo anterior
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
            return redirect(url_for('documents.detail', id=doc.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'danger')

    empleados = Employee.query.filter_by(activo=True).order_by(Employee.apellidos).all()
    tipos = DocumentType.query.order_by(DocumentType.nombre).all()

    return render_template('documents/form.html',
                           document=doc,
                           empleados=empleados,
                           tipos=tipos,
                           employee_preselect='')


@documents_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def delete(id):
    doc = Document.query.get_or_404(id)
    titulo = doc.titulo

    try:
        # Eliminar archivo físico
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

    return redirect(url_for('documents.list'))


@documents_bp.route('/<int:id>/descargar')
@login_required
def download(id):
    doc = Document.query.get_or_404(id)
    if not doc.archivo_path:
        flash('Este documento no tiene archivo adjunto.', 'warning')
        return redirect(url_for('documents.detail', id=id))

    upload_dir = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_dir, doc.archivo_path,
                               as_attachment=True,
                               download_name=doc.archivo_nombre)
