from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func
from typing import List
from datetime import datetime
import io

from wms_app import models, schemas
from wms_app.models.ddt import DDT, DDTLine
from wms_app.database import database, get_db

# Importazioni per PDF
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.pdfgen import canvas
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# Import templates in modo lazy per evitare import circolari
def get_templates():
    from wms_app.main import templates
    return templates

router = APIRouter(
    prefix="/ddt",
    tags=["ddt"],
)

def generate_ddt_number(db: Session) -> str:
    """Genera un numero DDT progressivo"""
    year = datetime.now().year
    
    # Trova l'ultimo numero DDT dell'anno corrente
    # I DDT hanno formato "000001/2025", quindi cerchiamo quelli che finiscono con "/YYYY"
    last_ddt = db.query(DDT).filter(
        DDT.ddt_number.like(f"%/{year}")
    ).order_by(DDT.ddt_number.desc()).first()
    
    if last_ddt:
        # Estrai il numero progressivo dall'ultimo DDT
        try:
            last_num = int(last_ddt.ddt_number.split("/")[0])
            next_num = last_num + 1
        except:
            next_num = 1
    else:
        next_num = 1
    
    return f"{next_num:06d}/{year}"

@router.get("/manage", response_class=HTMLResponse)
async def get_ddt_management_page(request: Request, db: Session = Depends(get_db)):
    """Pagina gestione DDT"""
    ddts = db.query(DDT).options(
        joinedload(DDT.lines),
        joinedload(DDT.order)
    ).order_by(DDT.issue_date.desc()).all()
    
    # Ordini completati senza DDT
    orders_without_ddt = db.query(models.Order).filter(
        models.Order.is_completed == True,
        ~models.Order.order_number.in_(
            db.query(DDT.order_number).subquery()
        )
    ).all()
    
    return get_templates().TemplateResponse("ddt.html", {
        "request": request,
        "ddts": ddts,
        "orders_without_ddt": orders_without_ddt,
        "active_page": "ddt"
    })

@router.post("/generate")
def generate_ddt_from_order(ddt_request: schemas.ddt.DDTGenerateRequest, db: Session = Depends(get_db)):
    """Genera DDT da ordine completato"""
    
    # Verifica che l'ordine esista ed sia completato
    order = db.query(models.Order).filter(
        models.Order.order_number == ddt_request.order_number,
        models.Order.is_completed == True
    ).options(joinedload(models.Order.lines)).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato o non completato")
    
    # Verifica che non esista già un DDT per questo ordine
    existing_ddt = db.query(DDT).filter(
        DDT.order_number == ddt_request.order_number
    ).first()
    
    if existing_ddt:
        raise HTTPException(status_code=400, detail="DDT già esistente per questo ordine")
    
    # Genera numero DDT
    ddt_number = generate_ddt_number(db)
    
    # Crea DDT
    ddt = DDT(
        ddt_number=ddt_number,
        order_number=ddt_request.order_number,
        customer_name=ddt_request.customer_name or order.customer_name,
        customer_address=ddt_request.customer_address,
        customer_city=ddt_request.customer_city,
        customer_cap=ddt_request.customer_cap,
        customer_province=ddt_request.customer_province,
        transporter_name=ddt_request.transporter_name,
        transporter_notes=ddt_request.transporter_notes,
        transport_reason=ddt_request.transport_reason,
        total_packages=ddt_request.total_packages,
        total_weight=ddt_request.total_weight,
        notes=ddt_request.notes
    )
    
    db.add(ddt)
    db.flush()  # Per ottenere l'ID del DDT
    
    # Aggiungi righe DDT dalle righe ordine
    for order_line in order.lines:
        if order_line.picked_quantity > 0:  # Solo prodotti effettivamente prelevati
            # Ottieni descrizione prodotto in modo sicuro
            product_description = order_line.product_sku
            try:
                if hasattr(order_line, 'product') and order_line.product and hasattr(order_line.product, 'description'):
                    product_description = order_line.product.description
            except:
                product_description = order_line.product_sku
            
            ddt_line = DDTLine(
                ddt_id=ddt.id,
                product_sku=order_line.product_sku,
                product_description=product_description,
                quantity=order_line.picked_quantity,
                unit_measure="pz"
            )
            db.add(ddt_line)
    
    db.commit()
    
    return {"message": f"DDT {ddt_number} generato con successo", "ddt_number": ddt_number}

@router.get("/{ddt_number:path}/pdf")
def generate_ddt_pdf(ddt_number: str, db: Session = Depends(get_db)):
    """Genera PDF del DDT"""
    
    if not PDF_AVAILABLE:
        raise HTTPException(status_code=500, detail="Generazione PDF non disponibile. Installare ReportLab.")
    
    # Trova DDT
    ddt = db.query(DDT).filter(
        DDT.ddt_number == ddt_number
    ).options(
        joinedload(DDT.lines),
        joinedload(DDT.order)
    ).first()
    
    if not ddt:
        raise HTTPException(status_code=404, detail="DDT non trovato")
    
    # Crea buffer PDF
    buffer = io.BytesIO()
    
    # Setup documento
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # Stili
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.black
    )
    
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6,
        textColor=colors.black
    )
    
    # Contenuto documento
    story = []
    
    # Titolo
    story.append(Paragraph("DOCUMENTO DI TRASPORTO", title_style))
    story.append(Spacer(1, 20))
    
    # Informazioni DDT - Layout a due colonne
    ddt_info_data = [
        ["Numero DDT:", ddt.ddt_number, "Data Emissione:", ddt.issue_date.strftime("%d/%m/%Y")],
        ["Ordine Rif.:", ddt.order_number, "Causale:", ddt.transport_reason],
        ["Cliente:", ddt.customer_name, "N. Colli:", str(ddt.total_packages)]
    ]
    
    if ddt.customer_address:
        ddt_info_data.append(["Indirizzo:", ddt.customer_address, "", ""])
    
    if ddt.customer_city:
        city_info = ddt.customer_city
        if ddt.customer_cap:
            city_info = f"{ddt.customer_cap} {city_info}"
        if ddt.customer_province:
            city_info = f"{city_info} ({ddt.customer_province})"
        ddt_info_data.append(["Città:", city_info, "", ""])
    
    if ddt.transporter_name:
        ddt_info_data.append(["Trasportatore:", ddt.transporter_name, "", ""])
    
    if ddt.total_weight:
        ddt_info_data.append(["Peso Totale:", ddt.total_weight, "", ""])
    
    info_table = Table(ddt_info_data, colWidths=[3*cm, 6*cm, 3*cm, 4*cm])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),  # Prima colonna in grassetto
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),  # Terza colonna in grassetto
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 30))
    
    # Tabella prodotti
    story.append(Paragraph("DETTAGLIO PRODOTTI", styles['Heading2']))
    story.append(Spacer(1, 15))
    
    # Header tabella
    product_data = [["Codice", "Descrizione", "Quantità", "U.M."]]
    
    # Righe prodotti
    for line in ddt.lines:
        product_data.append([
            line.product_sku,
            line.product_description,
            str(line.quantity),
            line.unit_measure
        ])
    
    # Calcola totale quantità
    total_qty = sum(line.quantity for line in ddt.lines)
    product_data.append(["", "TOTALE", str(total_qty), ""])
    
    product_table = Table(product_data, colWidths=[4*cm, 8*cm, 2*cm, 2*cm])
    product_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        
        # Dati
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 10),
        ('ALIGN', (0, 1), (0, -2), 'LEFT'),    # Codice
        ('ALIGN', (1, 1), (1, -2), 'LEFT'),    # Descrizione
        ('ALIGN', (2, 1), (2, -2), 'CENTER'),  # Quantità
        ('ALIGN', (3, 1), (3, -2), 'CENTER'),  # U.M.
        
        # Riga totale
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (0, -1), (-1, -1), 'CENTER'),
        
        # Bordi
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Alternanza colori righe
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.lightgrey])
    ]))
    
    story.append(product_table)
    story.append(Spacer(1, 30))
    
    # Note se presenti
    if ddt.notes:
        story.append(Paragraph("NOTE:", styles['Heading3']))
        story.append(Paragraph(ddt.notes, styles['Normal']))
        story.append(Spacer(1, 20))
    
    if ddt.transporter_notes:
        story.append(Paragraph("NOTE TRASPORTATORE:", styles['Heading3']))
        story.append(Paragraph(ddt.transporter_notes, styles['Normal']))
        story.append(Spacer(1, 20))
    
    # Firme
    story.append(Spacer(1, 40))
    signature_data = [
        ["Firma Mittente", "", "Firma Destinatario"],
        ["", "", ""],
        ["_____________________", "", "_____________________"]
    ]
    
    signature_table = Table(signature_data, colWidths=[6*cm, 4*cm, 6*cm])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
    ]))
    
    story.append(signature_table)
    
    # Genera PDF
    doc.build(story)
    buffer.seek(0)
    
    # Aggiorna stato stampato
    if not ddt.is_printed:
        ddt.is_printed = True
        ddt.printed_date = datetime.utcnow()
        db.commit()
    
    # Ritorna response
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=DDT_{ddt_number.replace('/', '_')}.pdf"}
    )

@router.get("/")
def get_ddts(db: Session = Depends(get_db)):
    """Lista tutti i DDT"""
    ddts = db.query(DDT).options(
        joinedload(DDT.lines)
    ).order_by(DDT.issue_date.desc()).all()
    return ddts

@router.get("/{ddt_number:path}")
def get_ddt(ddt_number: str, db: Session = Depends(get_db)):
    """Dettagli DDT specifico"""
    ddt = db.query(DDT).filter(
        DDT.ddt_number == ddt_number
    ).options(
        joinedload(DDT.lines),
        joinedload(DDT.order)
    ).first()
    
    if not ddt:
        raise HTTPException(status_code=404, detail="DDT non trovato")
    
    return ddt

@router.delete("/{ddt_number:path}")
def delete_ddt(ddt_number: str, db: Session = Depends(get_db)):
    """Elimina DDT"""
    ddt = db.query(DDT).filter(
        DDT.ddt_number == ddt_number
    ).first()
    
    if not ddt:
        raise HTTPException(status_code=404, detail="DDT non trovato")
    
    # Elimina prima le righe
    db.query(DDTLine).filter(
        DDTLine.ddt_id == ddt.id
    ).delete()
    
    # Poi il DDT
    db.delete(ddt)
    db.commit()
    
    return {"message": f"DDT {ddt_number} eliminato con successo"}