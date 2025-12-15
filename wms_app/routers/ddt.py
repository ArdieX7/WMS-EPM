from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func
from typing import List
from datetime import datetime
import io
import os

from wms_app import models, schemas
from wms_app.models.ddt import DDT, DDTLine
from wms_app.database import database, get_db
from wms_app.routers.auth import require_permission

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

def find_next_available_ddt_number(db: Session, year: int = None) -> int:
    """
    Trova il prossimo numero DDT disponibile per l'anno specificato.
    Se ci sono 'buchi' nella sequenza (es: 1,2,3,8,9), ritorna 4.
    """
    if year is None:
        year = datetime.now().year

    # Ottieni tutti i numeri DDT dell'anno corrente
    existing_ddts = db.query(DDT).filter(
        DDT.ddt_number.like(f"%/{year}")
    ).all()

    if not existing_ddts:
        return 1

    # Estrai i numeri progressivi
    used_numbers = set()
    for ddt in existing_ddts:
        try:
            num = int(ddt.ddt_number.split("/")[0])
            used_numbers.add(num)
        except (ValueError, IndexError):
            continue

    # Trova il primo numero non usato partendo da 1
    next_num = 1
    while next_num in used_numbers:
        next_num += 1

    return next_num

def generate_ddt_number(db: Session, custom_number: int = None) -> str:
    """
    Genera un numero DDT progressivo.
    Se custom_number è fornito, usa quello (con validazione).
    Altrimenti trova il prossimo numero disponibile.
    """
    year = datetime.now().year

    if custom_number is not None:
        # Validazione numero custom
        if custom_number < 1 or custom_number > 999999:
            raise HTTPException(
                status_code=400,
                detail="Numero DDT deve essere tra 1 e 999999"
            )

        # Verifica che non esista già
        formatted_number = f"{custom_number:06d}/{year}"
        existing = db.query(DDT).filter(
            DDT.ddt_number == formatted_number
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Numero DDT {formatted_number} già esistente"
            )

        return formatted_number
    else:
        # Auto-genera con gap detection
        next_num = find_next_available_ddt_number(db, year)
        return f"{next_num:06d}/{year}"

@router.get("/manage", response_class=HTMLResponse)
async def get_ddt_management_page(request: Request, db: Session = Depends(get_db)):
    """Pagina gestione DDT"""
    ddts = db.query(DDT).options(
        joinedload(DDT.lines),
        joinedload(DDT.order)
    ).order_by(DDT.issue_date.desc()).all()
    
    # Tutti gli ordini senza DDT (anche non completati, con righe e prodotti per calcolo peso)
    orders_without_ddt = db.query(models.Order).options(
        joinedload(models.Order.lines).joinedload(models.OrderLine.product)
    ).filter(
        ~models.Order.order_number.in_(
            db.query(DDT.order_number).subquery()
        )
    ).order_by(models.Order.order_date.desc()).all()
    
    return get_templates().TemplateResponse("ddt.html", {
        "request": request,
        "ddts": ddts,
        "orders_without_ddt": orders_without_ddt,
        "active_page": "ddt"
    })

@router.get("/next-number")
def get_next_ddt_number(db: Session = Depends(get_db)):
    """
    Ritorna il prossimo numero DDT disponibile per l'anno corrente.
    Usato dal frontend per pre-compilare il campo numero DDT.
    """
    year = datetime.now().year
    next_num = find_next_available_ddt_number(db, year)

    return {
        "next_number": next_num,
        "year": year,
        "formatted": f"{next_num:06d}/{year}"
    }

@router.post("/generate")
def generate_ddt_from_order(ddt_request: schemas.ddt.DDTGenerateRequest, db: Session = Depends(get_db)):
    """Genera DDT da ordine completato"""
    
    # Verifica che l'ordine esista (anche se non completato)
    order = db.query(models.Order).filter(
        models.Order.order_number == ddt_request.order_number
    ).options(joinedload(models.Order.lines)).first()

    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    
    # Verifica che non esista già un DDT per questo ordine
    existing_ddt = db.query(DDT).filter(
        DDT.order_number == ddt_request.order_number
    ).first()
    
    if existing_ddt:
        raise HTTPException(status_code=400, detail="DDT già esistente per questo ordine")

    # Genera numero DDT (usa custom_ddt_number se fornito)
    ddt_number = generate_ddt_number(db, custom_number=ddt_request.custom_ddt_number)
    
    # Crea DDT
    ddt = DDT(
        ddt_number=ddt_number,
        order_number=ddt_request.order_number,
        customer_name=ddt_request.customer_name or order.customer_name,
        customer_address=ddt_request.customer_address,
        customer_city=ddt_request.customer_city,
        customer_cap=ddt_request.customer_cap,
        customer_province=ddt_request.customer_province,
        # Campi deprecati - non più usati nei nuovi DDT
        # transporter_name=ddt_request.transporter_name,
        # transporter_notes=ddt_request.transporter_notes,
        # transport_reason=ddt_request.transport_reason,
        total_packages=ddt_request.total_packages,
        total_weight=ddt_request.total_weight,
        notes=ddt_request.notes
    )
    
    db.add(ddt)
    db.flush()  # Per ottenere l'ID del DDT
    
    # Aggiungi righe DDT dalle righe ordine (usa quantità ordine, non prelevata)
    for order_line in order.lines:
        if order_line.requested_quantity > 0:  # Tutte le righe dell'ordine
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
                quantity=order_line.requested_quantity,  # Usa quantità richiesta dall'ordine
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

    # Header con logo aziendale e titolo
    # Logo aziendale (in alto a destra)
    logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "EPM GL -Black4x.png")

    if os.path.exists(logo_path):
        logo = Image(logo_path, width=4*cm, height=2*cm, kind='proportional')
    else:
        # Fallback se logo non trovato
        logo = Paragraph("<i>Logo non trovato</i>", styles['Normal'])

    # Titolo documento (a sinistra)
    header_text = f"<b>DOCUMENTO DI TRASPORTO</b><br/>N. {ddt.ddt_number}"
    header_paragraph = Paragraph(header_text, header_style)

    # Tabella header con titolo a sinistra e logo a destra
    header_data = [[header_paragraph, logo]]
    header_table = Table(header_data, colWidths=[12*cm, 5*cm])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 15))

    # Layout Mittente e Destinatario a due colonne
    # Mittente (colonna sinistra - hardcoded)
    mittente_text = """
    <b>EPM</b><br/>
    Luogo di carico c/o magazzino LD Tyres srl<br/>
    Via Campobello 20/22<br/>
    00071 Pomezia (RM)
    """

    # Destinatario (colonna destra - da DDT)
    city_info = ""
    if ddt.customer_city:
        city_info = ddt.customer_city
        if ddt.customer_cap:
            city_info = f"{ddt.customer_cap} {city_info}"
        if ddt.customer_province:
            city_info = f"{city_info} ({ddt.customer_province})"

    destinatario_text = f"""
    <b>DESTINATARIO</b><br/>
    {ddt.customer_name}<br/>
    {ddt.customer_address or ''}<br/>
    {city_info}
    """

    # Tabella a 2 colonne per Mittente/Destinatario
    mittente_destinatario_data = [[Paragraph(mittente_text, styles['Normal']), Paragraph(destinatario_text, styles['Normal'])]]
    mittente_table = Table(mittente_destinatario_data, colWidths=[8.5*cm, 8.5*cm])
    mittente_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 1, colors.grey),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))

    story.append(mittente_table)
    story.append(Spacer(1, 15))

    # Informazioni DDT (ordine, data, colli, peso)
    ddt_details_data = [
        ["Ordine Riferimento:", ddt.order_number, "Data Emissione:", ddt.issue_date.strftime("%d/%m/%Y")],
        ["N. PLT:", str(ddt.total_packages), "Peso Totale:", ddt.total_weight or "N/D"]
    ]

    details_table = Table(ddt_details_data, colWidths=[4*cm, 4*cm, 4*cm, 4.5*cm])
    details_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))

    story.append(details_table)
    story.append(Spacer(1, 20))
    
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
    
    # Calcola totale quantità (TOTALE COLLI)
    total_qty = sum(line.quantity for line in ddt.lines)
    product_data.append(["", "TOTALE COLLI", str(total_qty), ""])
    
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
        ["Timbro e Firma Trasportatore", "", "Timbro e Firma Destinatario"],
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

@router.get("/check-order/{order_number}")
def check_ddt_for_order(order_number: str, db: Session = Depends(get_db)):
    """Controlla se un ordine ha un DDT collegato"""
    ddt = db.query(DDT).filter(DDT.order_number == order_number).first()
    
    if ddt:
        return {
            "has_ddt": True,
            "ddt_number": ddt.ddt_number,
            "ddt_id": ddt.id
        }
    else:
        return {"has_ddt": False}

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