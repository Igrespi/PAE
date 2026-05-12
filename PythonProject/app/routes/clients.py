from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.models import Client, Employee
from app.extensions import db
from app.utils.decorators import admin_required

clients_bp = Blueprint('clients', __name__, url_prefix='/clientes')


@clients_bp.route('/')
@login_required
@admin_required
def list():
    clients = Client.query.order_by(Client.nombre).all()
    return render_template('clients/list.html', clients=clients)


@clients_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        email = request.form.get('email', '').strip().lower()
        telefono = request.form.get('telefono', '').strip()
        notas = request.form.get('notas', '').strip()

        if not nombre:
            flash('El nombre del cliente es obligatorio.', 'danger')
            return render_template('clients/form.html', client=None)

        try:
            client = Client(nombre=nombre, email=email, telefono=telefono, notas=notas)
            db.session.add(client)
            db.session.commit()
            flash('Cliente creado correctamente.', 'success')
            return redirect(url_for('clients.detail', id=client.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el cliente: {str(e)}', 'danger')

    return render_template('clients/form.html', client=None)


@clients_bp.route('/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def detail(id):
    client = Client.query.get_or_404(id)

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        email = request.form.get('email', '').strip().lower()
        telefono = request.form.get('telefono', '').strip()
        notas = request.form.get('notas', '').strip()
        employee_ids = request.form.getlist('employee_ids')

        if not nombre:
            flash('El nombre del cliente es obligatorio.', 'danger')
            return redirect(url_for('clients.detail', id=client.id))

        try:
            client.nombre = nombre
            client.email = email
            client.telefono = telefono
            client.notas = notas

            if employee_ids:
                ids = [int(eid) for eid in employee_ids if eid.isdigit()]
                assigned = Employee.query.filter(Employee.id.in_(ids)).all()
                client.employees = assigned
            else:
                client.employees = []

            db.session.commit()
            flash('Cliente actualizado correctamente.', 'success')
            return redirect(url_for('clients.detail', id=client.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el cliente: {str(e)}', 'danger')

    empleados = Employee.query.order_by(Employee.apellidos, Employee.nombre).all()
    asignados_ids = {e.id for e in client.employees}
    asignados = client.employees.order_by(Employee.apellidos, Employee.nombre).all()

    return render_template('clients/detail.html',
                           client=client,
                           empleados=empleados,
                           asignados_ids=asignados_ids,
                           asignados=asignados)
