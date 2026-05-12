import csv
import io
from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from app.models import Document, Employee


def generar_csv_documentos(documentos):
    """Genera un CSV con la lista de documentos."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    writer.writerow([
        'Empleado', 'DNI', 'Departamento', 'Tipo Documento',
        'Título', 'Fecha Emisión', 'Fecha Caducidad', 'Estado', 'Días Restantes'
    ])

    for doc in documentos:
        writer.writerow([
            doc.employee.nombre_completo if doc.employee else '',
            doc.employee.dni if doc.employee else '',
            doc.employee.departamento if doc.employee else '',
            doc.document_type.nombre if doc.document_type else '',
            doc.titulo,
            doc.fecha_emision.strftime('%d/%m/%Y') if doc.fecha_emision else '',
            doc.fecha_caducidad.strftime('%d/%m/%Y') if doc.fecha_caducidad else 'Sin caducidad',
            doc.estado_badge[0],
            str(doc.dias_restantes) if doc.dias_restantes is not None else 'N/A'
        ])

    output.seek(0)
    return output.getvalue()


def generar_pdf_documentos(documentos, titulo_informe="Informe de Documentos PRL"):
    """Genera un PDF con la lista de documentos."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=1.5 * cm, bottomMargin=1.5 * cm)

    styles = getSampleStyleSheet()
    elements = []

    # Título
    titulo_style = ParagraphStyle(
        'CustomTitle', parent=styles['Title'], fontSize=18, spaceAfter=20
    )
    elements.append(Paragraph(titulo_informe, titulo_style))
    elements.append(Paragraph(f"Generado el: {date.today().strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Tabla de datos
    data = [['Empleado', 'DNI', 'Depto.', 'Tipo', 'Título', 'Emisión', 'Caducidad', 'Estado', 'Días']]

    for doc_item in documentos:
        estado_texto = doc_item.estado_badge[0]
        data.append([
            doc_item.employee.nombre_completo[:25] if doc_item.employee else '',
            doc_item.employee.dni if doc_item.employee else '',
            (doc_item.employee.departamento[:15] if doc_item.employee else ''),
            (doc_item.document_type.nombre[:20] if doc_item.document_type else ''),
            doc_item.titulo[:25],
            doc_item.fecha_emision.strftime('%d/%m/%Y') if doc_item.fecha_emision else '',
            doc_item.fecha_caducidad.strftime('%d/%m/%Y') if doc_item.fecha_caducidad else 'Sin cad.',
            estado_texto,
            str(doc_item.dias_restantes) if doc_item.dias_restantes is not None else 'N/A'
        ])

    if len(data) == 1:
        elements.append(Paragraph("No se encontraron documentos con los filtros seleccionados.", styles['Normal']))
    else:
        col_widths = [4 * cm, 2.5 * cm, 2.5 * cm, 3 * cm, 4 * cm, 2.5 * cm, 2.5 * cm, 2 * cm, 1.5 * cm]
        table = Table(data, colWidths=col_widths)

        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ])

        # Colorear filas según estado
        for i, row in enumerate(data[1:], start=1):
            if row[7] == 'Caducado':
                style.add('TEXTCOLOR', (7, i), (7, i), colors.red)
                style.add('FONTNAME', (7, i), (7, i), 'Helvetica-Bold')
            elif row[7] == 'Por vencer':
                style.add('TEXTCOLOR', (7, i), (7, i), colors.HexColor('#856404'))
                style.add('FONTNAME', (7, i), (7, i), 'Helvetica-Bold')
            elif row[7] == 'Vigente':
                style.add('TEXTCOLOR', (7, i), (7, i), colors.green)

        table.setStyle(style)
        elements.append(table)

    # Resumen
    elements.append(Spacer(1, 20))
    total = len(data) - 1
    caducados = sum(1 for d in documentos if d.estado == 'caducado')
    por_vencer = sum(1 for d in documentos if d.estado == 'por_vencer')
    vigentes = sum(1 for d in documentos if d.estado == 'vigente')
    resumen = f"<b>Resumen:</b> Total: {total} | Vigentes: {vigentes} | Por vencer: {por_vencer} | Caducados: {caducados}"
    elements.append(Paragraph(resumen, styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

