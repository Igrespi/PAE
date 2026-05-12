from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.models import DocumentType
from app.extensions import db
from app.utils.decorators import admin_required

document_types_bp = Blueprint('document_types', __name__, url_prefix='/tipos-documento')


@document_types_bp.route('/')
@login_required
@admin_required
def list():
    tipos = DocumentType.query.order_by(DocumentType.nombre).all()
    return render_template('document_types/list.html', tipos=tipos)


@document_types_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    if request.method == 'POST':
        try:
            tipo = DocumentType(
                nombre=request.form.get('nombre', '').strip(),
                descripcion=request.form.get('descripcion', '').strip(),
                validez_meses=int(request.form.get('validez_meses', 0)) or None,
                obligatorio=request.form.get('obligatorio') == 'on'
            )
            db.session.add(tipo)
            db.session.commit()
            flash(f'Tipo de documento "{tipo.nombre}" creado correctamente.', 'success')
            return redirect(url_for('documents.list', vista='tipos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear tipo de documento: {str(e)}', 'danger')

    return render_template('document_types/form.html', tipo=None)


@document_types_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    tipo = DocumentType.query.get_or_404(id)

    if request.method == 'POST':
        try:
            tipo.nombre = request.form.get('nombre', '').strip()
            tipo.descripcion = request.form.get('descripcion', '').strip()
            tipo.validez_meses = int(request.form.get('validez_meses', 0)) or None
            tipo.obligatorio = request.form.get('obligatorio') == 'on'

            db.session.commit()
            flash(f'Tipo de documento actualizado correctamente.', 'success')
            return redirect(url_for('documents.list', vista='tipos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'danger')

    return render_template('document_types/form.html', tipo=tipo)


@document_types_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def delete(id):
    tipo = DocumentType.query.get_or_404(id)
    nombre = tipo.nombre

    # Verificar si hay documentos asociados
    if tipo.documents.count() > 0:
        flash(f'No se puede eliminar "{nombre}" porque tiene {tipo.documents.count()} documento(s) asociado(s).', 'warning')
        return redirect(url_for('documents.list', vista='tipos'))

    try:
        db.session.delete(tipo)
        db.session.commit()
        flash(f'Tipo de documento "{nombre}" eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'danger')

    return redirect(url_for('documents.list', vista='tipos'))

