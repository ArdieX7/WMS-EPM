from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session
from typing import List
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

from wms_app import models, schemas
from wms_app.database import get_db
from wms_app.services.serial_service import SerialService

# Import templates in modo lazy per evitare import circolari
def get_templates():
    from wms_app.main import templates
    return templates

router = APIRouter(
    prefix="/serials",
    tags=["serials"],
)

# --- Viste HTML ---

@router.get("/manage", response_class=HTMLResponse)
async def get_serials_management_page(request: Request, db: Session = Depends(get_db)):
    """Pagina di gestione seriali prodotto"""
    serial_service = SerialService(db)
    orders_with_serials = serial_service.get_orders_with_serials()
    
    return get_templates().TemplateResponse("serials.html", {
        "request": request,
        "orders_with_serials": orders_with_serials,
        "active_page": "serials"
    })

# --- API Endpoints ---

@router.post("/upload", response_model=schemas.serials.SerialUploadResult)
async def upload_serials_file(
    file: UploadFile = File(...), 
    uploaded_by: str = "system",
    db: Session = Depends(get_db)
):
    """
    Upload e parsing del file seriali
    Formato atteso: ORDINE,EAN,SERIALE,EAN,SERIALE,...
    """
    # Verifica formato file
    if not file.filename.endswith(('.txt', '.csv')):
        raise HTTPException(status_code=400, detail="Formato file non supportato. Usare .txt o .csv")
    
    try:
        # Leggi contenuto file
        content = await file.read()
        file_content = content.decode('utf-8')
        
        # Processa con SerialService
        serial_service = SerialService(db)
        result = serial_service.parse_serial_file(file_content, uploaded_by)
        
        if not result.success:
            # Non raise HTTPException, restituisci il result per mostrare gli errori
            return result
        
        return result
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Errore codifica file. Usare codifica UTF-8.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante il caricamento: {str(e)}")

@router.get("/orders", response_model=List[schemas.serials.OrderSerialsView])
def get_orders_with_serials(db: Session = Depends(get_db)):
    """Lista ordini con seriali caricati"""
    serial_service = SerialService(db)
    return serial_service.get_orders_with_serials()

@router.get("/orders/{order_number}", response_model=schemas.serials.OrderSerialsView)
def get_order_serials(order_number: str, db: Session = Depends(get_db)):
    """Dettaglio seriali per un ordine specifico"""
    serial_service = SerialService(db)
    return serial_service.get_order_serials_view(order_number)

@router.get("/orders/{order_number}/validate", response_model=schemas.serials.SerialValidationSummary)
def validate_order_serials(order_number: str, db: Session = Depends(get_db)):
    """Validazione seriali di un ordine"""
    serial_service = SerialService(db)
    return serial_service.validate_serials_for_order(order_number)

@router.get("/orders/{order_number}/pdf")
async def generate_serials_pdf(order_number: str, db: Session = Depends(get_db)):
    """
    Genera PDF con seriali per un ordine
    """
    serial_service = SerialService(db)
    order_view = serial_service.get_order_serials_view(order_number)
    
    if not order_view.order_exists:
        raise HTTPException(status_code=404, detail=f"Ordine {order_number} non trovato")
    
    if not order_view.found_serials:
        raise HTTPException(status_code=404, detail=f"Nessun seriale trovato per ordine {order_number}")
    
    # Genera PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    
    # Crea stili personalizzati
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Centrato
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=20
    )
    
    story = []
    
    # Titolo
    story.append(Paragraph(f"SERIALI PRODOTTO - ORDINE {order_number}", title_style))
    story.append(Spacer(1, 12))
    
    # Data generazione
    current_date = datetime.now().strftime("%d/%m/%Y alle %H:%M")
    story.append(Paragraph(f"Documento generato il {current_date}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Tabella seriali per prodotto
    story.append(Paragraph("DETTAGLIO SERIALI PER PRODOTTO", subtitle_style))
    
    for sku in sorted(order_view.found_serials.keys()):
        serials = order_view.found_serials[sku]
        expected_qty = order_view.expected_products.get(sku, 0)
        found_qty = len(serials)
        
        # Sottotitolo prodotto
        product_title = f"SKU: {sku} (Attesi: {expected_qty}, Trovati: {found_qty})"
        story.append(Paragraph(product_title, styles['Heading3']))
        
        # Tabella seriali per questo prodotto
        serial_data = [["#", "Numero Seriale"]]
        for i, serial in enumerate(serials, 1):
            serial_data.append([str(i), serial])
        
        serial_table = Table(serial_data, colWidths=[0.5*inch, 4*inch])
        serial_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
        ]))
        
        story.append(serial_table)
        story.append(Spacer(1, 15))
    
    # Costruisci PDF
    doc.build(story)
    buffer.seek(0)
    
    # Ritorna response
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=seriali_ordine_{order_number}.pdf"}
    )

@router.get("/orders/{order_number}/excel")
async def generate_serials_excel(order_number: str, db: Session = Depends(get_db)):
    """
    Genera Excel con seriali per un ordine
    """
    if not EXCEL_AVAILABLE:
        raise HTTPException(status_code=500, detail="Excel export non disponibile. Installare openpyxl.")
    
    serial_service = SerialService(db)
    order_view = serial_service.get_order_serials_view(order_number)
    
    if not order_view.order_exists:
        raise HTTPException(status_code=404, detail=f"Ordine {order_number} non trovato")
    
    if not order_view.found_serials:
        raise HTTPException(status_code=404, detail=f"Nessun seriale trovato per ordine {order_number}")
    
    # Crea workbook
    wb = Workbook()
    ws = wb.active
    ws.title = f"Seriali Ordine {order_number}"
    
    # Stili
    header_font = Font(bold=True, size=14)
    subheader_font = Font(bold=True, size=12)
    normal_font = Font(size=10)
    header_fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
    
    # Titolo
    ws['A1'] = f"SERIALI PRODOTTO - ORDINE {order_number}"
    ws['A1'].font = header_font
    ws.merge_cells('A1:C1')
    
    # Data
    current_date = datetime.now().strftime("%d/%m/%Y alle %H:%M")
    ws['A2'] = f"Documento generato il {current_date}"
    ws['A2'].font = normal_font
    ws.merge_cells('A2:C2')
    
    # Riga vuota
    row = 4
    
    # Headers
    ws[f'A{row}'] = "SKU Prodotto"
    ws[f'B{row}'] = "Numero Seriale"
    ws[f'C{row}'] = "Posizione"
    
    # Stile headers
    for col in ['A', 'B', 'C']:
        cell = ws[f'{col}{row}']
        cell.font = subheader_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
    
    row += 1
    
    # Dati seriali per prodotto
    for sku in sorted(order_view.found_serials.keys()):
        serials = order_view.found_serials[sku]
        
        for i, serial in enumerate(serials, 1):
            ws[f'A{row}'] = sku
            ws[f'B{row}'] = serial
            ws[f'C{row}'] = i  # Posizione numerica
            
            # Stile celle
            for col in ['A', 'B', 'C']:
                ws[f'{col}{row}'].font = normal_font
                ws[f'{col}{row}'].alignment = Alignment(horizontal='left')
            
            row += 1
    
    # Autofit colonne
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Salva in buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    # Ritorna response
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=seriali_ordine_{order_number}.xlsx"}
    )

@router.get("/format-info", response_model=schemas.serials.SerialFileFormat)
def get_file_format_info():
    """Informazioni sul formato file seriali"""
    return schemas.serials.SerialFileFormat()

@router.get("/duplicates")
def get_duplicate_serials(db: Session = Depends(get_db)):
    """Trova tutti i seriali duplicati nel sistema"""
    serial_service = SerialService(db)
    return serial_service.get_duplicate_serials_in_system()

@router.get("/check/{serial_number}")
def check_serial_exists(serial_number: str, db: Session = Depends(get_db)):
    """Verifica se un seriale specifico esiste già"""
    serial_service = SerialService(db)
    existing = serial_service.check_serial_exists(serial_number)
    
    if existing:
        return {
            "exists": True,
            "serial_number": serial_number,
            "order_number": existing.order_number,
            "product_sku": existing.product_sku,
            "ean_code": existing.ean_code,
            "uploaded_at": existing.uploaded_at
        }
    else:
        return {
            "exists": False,
            "serial_number": serial_number
        }

@router.delete("/orders/{order_number}")
def delete_order_serials(order_number: str, db: Session = Depends(get_db)):
    """Elimina tutti i seriali di un ordine"""
    deleted_count = db.query(models.serials.ProductSerial).filter(
        models.serials.ProductSerial.order_number == order_number
    ).delete()
    
    db.commit()
    
    return {"message": f"Eliminati {deleted_count} seriali per ordine {order_number}"}

@router.delete("/batch/{upload_batch_id}")
def delete_batch_serials(upload_batch_id: str, db: Session = Depends(get_db)):
    """Elimina tutti i seriali di un batch upload"""
    deleted_count = db.query(models.serials.ProductSerial).filter(
        models.serials.ProductSerial.upload_batch_id == upload_batch_id
    ).delete()
    
    db.commit()
    
    return {"message": f"Eliminati {deleted_count} seriali per batch {upload_batch_id}"}