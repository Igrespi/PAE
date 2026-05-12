"""
Script de inicializacion: crea las tablas, un usuario admin y tipos de documento.
Ejecutar una sola vez: python seed.py
"""
from app import create_app
from app.extensions import db
from app.models import User, Employee, DocumentType, Document, Client


def seed():
    app = create_app()

    with app.app_context():
        db.create_all()
        print("✅ Tablas creadas correctamente.")

        # ─── Usuario admin ───
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@empresa.com',
                nombre='Administrador',
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✅ Usuario admin creado (admin / admin123)")
        else:
            print("ℹ️ Usuario admin ya existe.")

        # ─── Tipos de documento PRL ───
        tipos_data = [
            ("Reconocimiento médico", "Reconocimiento médico laboral periódico", 12, True),
            ("Formación PRL básica (20h)", "Curso de Prevención de Riesgos Laborales nivel básico - 20 horas", None, True),
            ("Formación PRL (60h)", "Curso de PRL nivel intermedio - 60 horas", None, False),
            ("Certificado de aptitud médica", "Certificado de aptitud para el puesto de trabajo", 12, True),
            ("Permiso trabajo en altura", "Certificación para trabajos en altura", 24, False),
            ("Permiso trabajo en espacios confinados", "Certificación para trabajos en espacios confinados", 24, False),
            ("Curso manipulación de cargas", "Formación en manipulación manual de cargas", 24, False),
            ("Certificado manejo de carretilla", "Certificación para manejo de carretilla elevadora", 60, False),
            ("Curso de primeros auxilios", "Formación en primeros auxilios y emergencias", 24, False),
            ("Entrega de EPIs", "Registro de entrega de Equipos de Protección Individual", 12, True),
            ("Plan de emergencia - Acuse", "Acuse de recibo del plan de emergencias", None, True),
            ("Información de riesgos del puesto", "Documento de información sobre riesgos específicos del puesto", None, True),
            ("Coordinación de Actividades Empresariales (CAE)", "Documentación CAE para subcontratas", 12, False),
            ("Seguro de responsabilidad civil", "Póliza de seguro RC", 12, False),
            ("Certificado instalación eléctrica", "Certificado de instalación eléctrica del centro de trabajo", 60, False),
        ]

        tipos_creados = 0
        for nombre, desc, validez, obligatorio in tipos_data:
            if not DocumentType.query.filter_by(nombre=nombre).first():
                tipo = DocumentType(
                    nombre=nombre,
                    descripcion=desc,
                    validez_meses=validez,
                    obligatorio=obligatorio
                )
                db.session.add(tipo)
                tipos_creados += 1

        db.session.commit()
        print(f"✅ {tipos_creados} tipos de documento creados.")

        # ─── Empleados de ejemplo ───
        empleados_data = [
            ("Sergi", "Pinilla", "12345678A", "sergi.pinilla@oxigent.com", "600111222", "Tecnico PRL", "Administracion"),
            ("Laura", "Martinez", "23456789B", "laura.martinez@oxigent.com", "600222333", "HRBP", "Recursos Humanos"),
            ("Carlos", "Ruiz", "34567890C", "carlos.ruiz@oxigent.com", "600333444", "Operario", "Logistica"),
            ("Nuria", "Soler", "45678901D", "nuria.soler@oxigent.com", "600444555", "Supervisora", "Operaciones"),
            ("Pablo", "Gomez", "56789012E", "pablo.gomez@oxigent.com", "600555666", "Analista", "Administracion"),
            ("Marta", "Lopez", "67890123F", "marta.lopez@oxigent.com", "600666777", "Coordinadora", "Recursos Humanos"),
        ]

        empleados_creados = 0
        for nombre, apellidos, dni, email, telefono, puesto, departamento in empleados_data:
            if not Employee.query.filter_by(dni=dni).first():
                emp = Employee(
                    nombre=nombre,
                    apellidos=apellidos,
                    dni=dni,
                    email=email,
                    telefono=telefono,
                    puesto=puesto,
                    departamento=departamento,
                    activo=True
                )
                db.session.add(emp)
                empleados_creados += 1

        db.session.commit()
        if empleados_creados:
            print(f"✅ {empleados_creados} empleados de ejemplo creados.")
        else:
            print("ℹ️ Empleados de ejemplo ya existen.")

        forced_email = 'sergi.pinilla@estudiantat.upc.edu'
        actualizados = Employee.query.update({Employee.email: forced_email})
        db.session.commit()
        print(f"✅ Emails de empleados actualizados a {forced_email} ({actualizados} registro(s)).")

        # ─── Clientes de ejemplo ───
        clientes_data = [
            ("Oxigent Retail", "contacto@oxigent-retail.com", "931112233", "Cliente con equipos de tienda."),
            ("Oxigent Logistics", "rrhh@oxigent-logistics.com", "932223344", "Operaciones logisticas y almacenes."),
        ]

        for nombre, email, telefono, notas in clientes_data:
            if not Client.query.filter_by(nombre=nombre).first():
                client = Client(nombre=nombre, email=email, telefono=telefono, notas=notas)
                db.session.add(client)

        db.session.commit()

        empleados = Employee.query.order_by(Employee.apellidos, Employee.nombre).all()
        clientes = Client.query.order_by(Client.nombre).all()
        if empleados and clientes:
            if len(clientes) > 0:
                clientes[0].employees = empleados[: min(3, len(empleados))]
            if len(clientes) > 1:
                clientes[1].employees = empleados[min(3, len(empleados)) : min(6, len(empleados))]
            db.session.commit()

        print("\n" + "=" * 50)
        print("🚀 ¡Base de datos inicializada correctamente!")
        print("=" * 50)
        print(f"\n📊 Resumen:")
        print(f"   - Usuarios: {User.query.count()}")
        print(f"   - Empleados: {Employee.query.count()}")
        print(f"   - Tipos de documento: {DocumentType.query.count()}")
        print(f"   - Documentos: {Document.query.count()}")
        print(f"   - Clientes: {Client.query.count()}")
        print(f"\n🔐 Acceso: usuario 'admin' / contraseña 'admin123'")
        print("🌐 Ejecuta 'python run_tunnel.py' para iniciar el servidor (local o Cloudflare).")


if __name__ == '__main__':
    seed()

