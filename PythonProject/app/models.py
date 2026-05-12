from datetime import datetime, date, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    dni = db.Column(db.String(20), default='')
    telefono = db.Column(db.String(20), default='')
    password_hash = db.Column(db.String(256), nullable=False)
    nombre = db.Column(db.String(100), default='')
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)


    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class Employee(db.Model):
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(150), nullable=False)
    dni = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), default='')
    telefono = db.Column(db.String(20), default='')
    puesto = db.Column(db.String(100), default='')
    departamento = db.Column(db.String(100), default='')
    fecha_alta = db.Column(db.Date, default=date.today)
    activo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    documents = db.relationship('Document', backref='employee', lazy='dynamic',
                                cascade='all, delete-orphan')

    @property
    def nombre_completo(self):
        return f'{self.nombre} {self.apellidos}'

    @property
    def documentos_caducados(self):
        return sum(1 for d in self.documents if d.estado == 'caducado')

    @property
    def documentos_por_vencer(self):
        return sum(1 for d in self.documents if d.estado == 'por_vencer')

    def __repr__(self):
        return f'<Employee {self.nombre_completo}>'


class Client(db.Model):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), default='')
    telefono = db.Column(db.String(20), default='')
    notas = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=utcnow)

    employees = db.relationship(
        'Employee',
        secondary='client_employees',
        backref=db.backref('clients', lazy='dynamic'),
        lazy='dynamic'
    )

    def __repr__(self):
        return f'<Client {self.nombre}>'


class DocumentType(db.Model):
    __tablename__ = 'document_types'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), unique=True, nullable=False)
    descripcion = db.Column(db.Text, default='')
    validez_meses = db.Column(db.Integer, nullable=True)  # Duración por defecto en meses
    obligatorio = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    documents = db.relationship('Document', backref='document_type', lazy='dynamic')

    def __repr__(self):
        return f'<DocumentType {self.nombre}>'


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    document_type_id = db.Column(db.Integer, db.ForeignKey('document_types.id'), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    archivo_nombre = db.Column(db.String(255), default='')
    archivo_path = db.Column(db.String(500), default='')
    fecha_emision = db.Column(db.Date, nullable=False)
    fecha_caducidad = db.Column(db.Date, nullable=True)
    notas = db.Column(db.Text, default='')
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    uploader = db.relationship('User', backref='uploaded_documents')
    notifications = db.relationship('NotificationLog', backref='document', lazy='dynamic',
                                     cascade='all, delete-orphan')

    @property
    def estado(self):
        if not self.fecha_caducidad:
            return 'vigente'
        hoy = date.today()
        if self.fecha_caducidad < hoy:
            return 'caducado'
        dias_restantes = (self.fecha_caducidad - hoy).days
        if dias_restantes <= 30:
            return 'por_vencer'
        return 'vigente'

    @property
    def dias_restantes(self):
        if not self.fecha_caducidad:
            return None
        return (self.fecha_caducidad - date.today()).days

    @property
    def estado_badge(self):
        estados = {
            'caducado': ('Caducado', 'danger'),
            'por_vencer': ('Por vencer', 'warning'),
            'vigente': ('Vigente', 'success'),
        }
        return estados.get(self.estado, ('Desconocido', 'secondary'))

    def __repr__(self):
        return f'<Document {self.titulo}>'


class NotificationLog(db.Model):
    __tablename__ = 'notification_logs'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    tipo_alerta = db.Column(db.String(50), nullable=False)  # "30_dias", "15_dias", "7_dias", "1_dia"
    email_destino = db.Column(db.String(120), nullable=False)
    enviado_en = db.Column(db.DateTime, default=utcnow)
    exitoso = db.Column(db.Boolean, default=True)
    mensaje_error = db.Column(db.Text, default='')

    employee = db.relationship('Employee', backref='notifications')

    def __repr__(self):
        return f'<NotificationLog {self.tipo_alerta} - Doc:{self.document_id}>'


client_employees = db.Table(
    'client_employees',
    db.Column('client_id', db.Integer, db.ForeignKey('clients.id'), primary_key=True),
    db.Column('employee_id', db.Integer, db.ForeignKey('employees.id'), primary_key=True)
)


class AppSetting(db.Model):
    __tablename__ = 'app_settings'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(500), nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow)

    def __repr__(self):
        return f'<AppSetting {self.key}>'
