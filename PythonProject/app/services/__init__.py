from datetime import date, timedelta, datetime
from flask import current_app
from flask_mail import Message
from app.extensions import db, mail
from app.models import Document, NotificationLog
from app.utils.settings import get_alert_days


def check_and_send_notifications():
    """Revisa documentos próximos a caducar y envía notificaciones por email."""
    with current_app.app_context():
        default_days = current_app.config.get('ALERT_DAYS', [30, 15, 7, 1])
        alert_days = get_alert_days(default_days)
        hoy = date.today()

        for dias in alert_days:
            fecha_objetivo = hoy + timedelta(days=dias)
            tipo_alerta = f"{dias}_dias"

            # Buscar documentos que caducan exactamente en X días
            documentos = Document.query.filter(
                Document.fecha_caducidad == fecha_objetivo
            ).all()

            for doc in documentos:
                # Verificar que no se haya enviado ya esta alerta hoy
                ya_enviado = NotificationLog.query.filter(
                    NotificationLog.document_id == doc.id,
                    NotificationLog.tipo_alerta == tipo_alerta,
                    NotificationLog.enviado_en >= datetime.combine(hoy, datetime.min.time()),
                ).first()

                if ya_enviado:
                    continue

                # Enviar al empleado si tiene email
                destinatarios = []
                if doc.employee and doc.employee.email:
                    destinatarios.append(doc.employee.email)

                # Enviar también al admin
                admin_email = current_app.config.get('MAIL_DEFAULT_SENDER', '')
                if admin_email and admin_email not in destinatarios:
                    destinatarios.append(admin_email)

                if not destinatarios:
                    continue

                for email_destino in destinatarios:
                    enviar_alerta_caducidad(doc, dias, tipo_alerta, email_destino)


def enviar_alerta_caducidad(documento, dias, tipo_alerta, email_destino):
    """Envía un email de alerta de caducidad."""
    try:
        empleado = documento.employee
        tipo_doc = documento.document_type

        if dias <= 0:
            asunto = f"⚠️ DOCUMENTO CADUCADO - {documento.titulo} - {empleado.nombre_completo}"
        elif dias <= 7:
            asunto = f"🔴 URGENTE: Documento caduca en {dias} día(s) - {documento.titulo}"
        elif dias <= 15:
            asunto = f"🟡 AVISO: Documento caduca en {dias} días - {documento.titulo}"
        else:
            asunto = f"📋 Recordatorio: Documento caduca en {dias} días - {documento.titulo}"

        fecha_emision_txt = documento.fecha_emision.strftime('%d/%m/%Y') if documento.fecha_emision else 'N/A'
        fecha_caducidad_txt = documento.fecha_caducidad.strftime('%d/%m/%Y') if documento.fecha_caducidad else 'Sin caducidad'

        cuerpo_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
                <div style="background-color: {'#dc3545' if dias <= 7 else '#ffc107' if dias <= 15 else '#0d6efd'}; 
                            color: white; padding: 20px; text-align: center;">
                    <h2 style="margin: 0;">{'⚠️ DOCUMENTO CADUCADO' if dias <= 0 else f'Alerta de Caducidad - {dias} día(s)'}</h2>
                </div>
                <div style="padding: 20px;">
                    <h3>Detalles del Documento</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Empleado:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{empleado.nombre_completo}</td></tr>
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">DNI:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{empleado.dni}</td></tr>
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Departamento:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{empleado.departamento}</td></tr>
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Documento:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{documento.titulo}</td></tr>
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Tipo:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{tipo_doc.nombre if tipo_doc else 'N/A'}</td></tr>
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Fecha de emisión:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{fecha_emision_txt}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold; color: {'#dc3545' if dias <= 7 else '#856404'};">Fecha de caducidad:</td>
                            <td style="padding: 8px; font-weight: bold; color: {'#dc3545' if dias <= 7 else '#856404'};">
                                {fecha_caducidad_txt}</td></tr>
                    </table>
                    <div style="margin-top: 20px; padding: 15px; background-color: #fff3cd; border-radius: 5px;">
                        <strong>Acción requerida:</strong> Por favor, renueve este documento antes de su fecha de caducidad 
                        para garantizar el cumplimiento normativo en materia de PRL.
                    </div>
                </div>
                <div style="background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #6c757d;">
                    Sistema de Gestión PRL - Notificación automática
                </div>
            </div>
        </body>
        </html>
        """

        msg = Message(
            subject=asunto,
            recipients=[email_destino],
            html=cuerpo_html
        )
        mail.send(msg)

        # Registrar notificación exitosa
        log = NotificationLog(
            document_id=documento.id,
            employee_id=documento.employee_id,
            tipo_alerta=tipo_alerta,
            email_destino=email_destino,
            exitoso=True
        )
        db.session.add(log)
        db.session.commit()

    except Exception as e:
        # Registrar error
        log = NotificationLog(
            document_id=documento.id,
            employee_id=documento.employee_id,
            tipo_alerta=tipo_alerta,
            email_destino=email_destino,
            exitoso=False,
            mensaje_error=str(e)
        )
        db.session.add(log)
        db.session.commit()


def send_test_notification(email_destino):
    """Envía un email de prueba para verificar la configuración."""
    try:
        msg = Message(
            subject="🔧 Prueba - Sistema de Gestión PRL",
            recipients=[email_destino],
            html="""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; text-align: center;">
                    <h2>✅ Configuración de correo correcta</h2>
                    <p>Este es un email de prueba del Sistema de Gestión PRL.</p>
                    <p>Las notificaciones automáticas están funcionando correctamente.</p>
                </div>
            </body>
            </html>
            """
        )
        mail.send(msg)
        return True, "Email de prueba enviado correctamente."
    except Exception as e:
        return False, f"Error al enviar: {str(e)}"

