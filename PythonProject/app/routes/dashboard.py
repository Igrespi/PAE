from datetime import date, timedelta
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Document, Employee, DocumentType
from app.extensions import db

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    hoy = date.today()
    en_30_dias = hoy + timedelta(days=30)
    en_7_dias = hoy + timedelta(days=7)


    # --- VISTA ADMIN ---
    # Estadísticas generales
    total_empleados = Employee.query.filter_by(activo=True).count()
    total_documentos = Document.query.count()
    total_tipos = DocumentType.query.count()

    # Documentos por estado
    docs_caducados = Document.query.filter(
        Document.fecha_caducidad < hoy,
        Document.fecha_caducidad.isnot(None)
    ).count()

    docs_por_vencer_7 = Document.query.filter(
        Document.fecha_caducidad >= hoy,
        Document.fecha_caducidad <= en_7_dias
    ).count()

    docs_por_vencer_30 = Document.query.filter(
        Document.fecha_caducidad >= hoy,
        Document.fecha_caducidad <= en_30_dias
    ).count()

    docs_vigentes = Document.query.filter(
        db.or_(
            Document.fecha_caducidad > en_30_dias,
            Document.fecha_caducidad.is_(None)
        )
    ).count()

    # Documentos próximos a vencer (lista detallada)
    proximos_a_vencer = Document.query.filter(
        Document.fecha_caducidad >= hoy,
        Document.fecha_caducidad <= en_30_dias
    ).order_by(Document.fecha_caducidad.asc()).limit(20).all()

    # Documentos ya caducados
    caducados = Document.query.filter(
        Document.fecha_caducidad < hoy,
        Document.fecha_caducidad.isnot(None)
    ).order_by(Document.fecha_caducidad.desc()).limit(10).all()

    # Empleados con más documentos caducados
    empleados_alerta = []
    empleados = Employee.query.filter_by(activo=True).all()
    for emp in empleados:
        n_cad = emp.documentos_caducados
        n_pv = emp.documentos_por_vencer
        if n_cad > 0 or n_pv > 0:
            empleados_alerta.append({
                'empleado': emp,
                'caducados': n_cad,
                'por_vencer': n_pv
            })
    empleados_alerta.sort(key=lambda x: x['caducados'], reverse=True)

    return render_template('dashboard/index.html',
                           total_empleados=total_empleados,
                           total_documentos=total_documentos,
                           total_tipos=total_tipos,
                           docs_caducados=docs_caducados,
                           docs_por_vencer_7=docs_por_vencer_7,
                           docs_por_vencer_30=docs_por_vencer_30,
                           docs_vigentes=docs_vigentes,
                           proximos_a_vencer=proximos_a_vencer,
                           caducados=caducados,
                           empleados_alerta=empleados_alerta[:10])
