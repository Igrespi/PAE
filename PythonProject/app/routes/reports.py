from datetime import date, timedelta
from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from app.models import Document, Employee, DocumentType
from app.extensions import db
from app.services.report_service import generar_csv_documentos, generar_pdf_documentos
from app.utils.decorators import admin_required

reports_bp = Blueprint('reports', __name__, url_prefix='/informes')


@reports_bp.route('/')
@login_required
@admin_required
def index():
    tipos = DocumentType.query.order_by(DocumentType.nombre).all()
    departamentos = db.session.query(Employee.departamento).distinct().filter(
        Employee.departamento != ''
    ).order_by(Employee.departamento).all()
    departamentos = [d[0] for d in departamentos]

    return render_template('reports/index.html', tipos=tipos, departamentos=departamentos)


@reports_bp.route('/generar', methods=['POST'])
@login_required
@admin_required
def generar():
    formato = request.form.get('formato', 'csv')
    estado = request.form.get('estado', '')
    tipo_id = request.form.get('tipo_id', '')
    departamento = request.form.get('departamento', '')

    query = Document.query.join(Employee)

    hoy = date.today()
    en_30 = hoy + timedelta(days=30)

    if estado == 'caducado':
        query = query.filter(Document.fecha_caducidad < hoy, Document.fecha_caducidad.isnot(None))
    elif estado == 'por_vencer':
        query = query.filter(Document.fecha_caducidad >= hoy, Document.fecha_caducidad <= en_30)
    elif estado == 'vigente':
        query = query.filter(
            db.or_(Document.fecha_caducidad > en_30, Document.fecha_caducidad.is_(None))
        )

    if tipo_id:
        query = query.filter(Document.document_type_id == int(tipo_id))

    if departamento:
        query = query.filter(Employee.departamento == departamento)

    documentos = query.order_by(Document.fecha_caducidad.asc()).all()

    titulo = "Informe de Documentos PRL"
    if estado:
        titulo += f" - Estado: {estado.replace('_', ' ').title()}"

    if formato == 'pdf':
        pdf_data = generar_pdf_documentos(documentos, titulo)
        return Response(
            pdf_data,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=informe_prl_{date.today().isoformat()}.pdf'}
        )
    else:
        csv_data = generar_csv_documentos(documentos)
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=informe_prl_{date.today().isoformat()}.csv'}
        )

