from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func
from sqlalchemy import and_
from typing import List, Dict, Tuple, Any, Optional
from collections import defaultdict
from datetime import datetime, date
import os
import shutil
from pathlib import Path
import io

# Import per export Excel e PDF
try:
    import openpyxl
    import openpyxl.styles
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch

from wms_app import models, schemas
from wms_app.database import database, get_db
from wms_app.routers.auth import require_permission
from wms_app.services.logging_service import LoggingService
from wms_app.models.logs import OperationType, OperationCategory, OperationStatus

# Import templates in modo lazy per evitare import circolari
def get_templates():
    from wms_app.main import templates
    return templates

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
)

# --- Viste HTML (devono essere definite prima delle rotte con parametri di percorso) ---

@router.get("/manage", response_class=HTMLResponse)
async def get_orders_management_page(request: Request, db: Session = Depends(get_db)):
    # Escludi ordini archiviati dalla vista principale
    orders = db.query(models.Order).filter(models.Order.is_archived == 0).options(joinedload(models.Order.lines)).all()
    products = db.query(models.Product).all()
    return get_templates().TemplateResponse("orders.html", {
        "request": request,
        "orders": orders,
        "products": products,
        "active_page": "orders"
    })

# --- API Endpoints per la Gestione Ordini (generici, senza parametri di percorso) ---

@router.post("/", response_model=schemas.Order)
def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    logger = LoggingService(db)
    
    # Controlla ordine duplicato
    db_order = db.query(models.Order).filter(models.Order.order_number == order.order_number).first()
    if db_order:
        # Log errore ordine duplicato
        logger.log_error(
            operation_type=OperationType.ORDINE_CREATO,
            error=f"Order number {order.order_number} already exists",
            operation_category=OperationCategory.MANUAL,
            file_name=f"ORDER_{order.order_number}",
            details={
                'order_number': order.order_number,
                'customer_name': order.customer_name,
                'error_reason': 'duplicate_order_number',
                'operation_description': f"Tentativo fallito creazione ordine {order.order_number}: numero ordine già esistente"
            },
            api_endpoint="/orders/"
        )
        raise HTTPException(status_code=400, detail="Order number already exists")

    new_order = models.Order(order_number=order.order_number, customer_name=order.customer_name)
    db.add(new_order)
    
    try:
        db.flush() # Per ottenere l'ID dell'ordine prima del commit
    except Exception as e:
        logger.log_error(
            operation_type=OperationType.ORDINE_CREATO,
            error=e,
            operation_category=OperationCategory.MANUAL,
            file_name=f"ORDER_{order.order_number}",
            details={
                'order_number': order.order_number,
                'customer_name': order.customer_name,
                'error_reason': 'database_flush_failed',
                'operation_description': f"Errore database durante creazione ordine {order.order_number}"
            },
            api_endpoint="/orders/"
        )
        raise HTTPException(status_code=500, detail="Database error during order creation")

    for line_data in order.lines:
        product = db.query(models.Product).filter(models.Product.sku == line_data.product_sku).first()
        if not product:
            # Log errore prodotto non trovato
            logger.log_error(
                operation_type=OperationType.ORDINE_CREATO,
                error=f"Product SKU {line_data.product_sku} not found",
                operation_category=OperationCategory.MANUAL,
                product_sku=line_data.product_sku,
                file_name=f"ORDER_{order.order_number}",
                details={
                    'order_number': order.order_number,
                    'customer_name': order.customer_name,
                    'error_reason': 'product_not_found',
                    'missing_sku': line_data.product_sku,
                    'operation_description': f"Errore creazione ordine {order.order_number}: prodotto {line_data.product_sku} non trovato"
                },
                api_endpoint="/orders/"
            )
            raise HTTPException(status_code=404, detail=f"Product SKU {line_data.product_sku} not found for order line")
        
        new_line = models.OrderLine(
            order_id=new_order.id,
            product_sku=line_data.product_sku,
            requested_quantity=line_data.requested_quantity
        )
        db.add(new_line)
    
    # LOGGING: Registra la creazione manuale dell'ordine (successo)
    
    # Logga ogni prodotto dell'ordine separatamente per visibilità nelle colonne
    for line_data in order.lines:
        logger.log_operation(
            operation_type=OperationType.ORDINE_CREATO,
            operation_category=OperationCategory.MANUAL,
            status=OperationStatus.SUCCESS,
            product_sku=line_data.product_sku,  # SKU del prodotto nell'ordine
            quantity=line_data.requested_quantity,  # Quantità richiesta
            user_id="manual_user",  # TODO: Sostituire con sistema auth reale
            file_name=f"ORDER_{new_order.order_number}",  # Numero ordine nella colonna Dettagli
            details={
                'order_number': new_order.order_number,  # Numero ordine nei dettagli JSON
                'customer_name': new_order.customer_name,
                'creation_method': 'manual',
                'operation_description': f"Creazione manuale ordine {new_order.order_number}: aggiunto {line_data.requested_quantity}x {line_data.product_sku} per cliente {new_order.customer_name}",
                'total_order_lines': len(order.lines),
                'total_order_items': sum(line.requested_quantity for line in order.lines)
            },
            api_endpoint="/orders/"
        )
    
    db.commit()
    db.refresh(new_order)
    return new_order

@router.get("/", response_model=List[schemas.Order])
def read_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # Escludi ordini archiviati dalla lista principale
    orders = db.query(models.Order).filter(
        models.Order.is_archived == 0
    ).options(
        joinedload(models.Order.lines).joinedload(models.OrderLine.product)
    ).offset(skip).limit(limit).all()
    
    # Calcola il peso totale per ogni ordine
    for order in orders:
        total_weight = 0.0
        for line in order.lines:
            if line.product and line.product.weight:
                total_weight += line.requested_quantity * line.product.weight
        order.total_weight = total_weight
    
    return orders

# --- EXPORT ENDPOINTS (devono essere prima di /{order_id}) ---

@router.get("/export-excel")
async def export_orders_excel(
    from_date: Optional[date] = Query(None, description="Data inizio (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="Data fine (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Esporta ordini in formato Excel con filtro per range di date.
    Include sia ordini attivi che archiviati.
    """
    if not EXCEL_AVAILABLE:
        raise HTTPException(status_code=500, detail="Export Excel non disponibile. Installare openpyxl.")
    
    try:
        # Query unificata per ordini attivi e archiviati
        query = db.query(models.Order).options(joinedload(models.Order.lines))
        
        # Applica filtri date se forniti
        if from_date:
            query = query.filter(models.Order.order_date >= from_date)
        if to_date:
            query = query.filter(models.Order.order_date <= to_date)
            
        orders = query.order_by(models.Order.order_date.desc()).all()
        
        # Crea workbook Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Ordini Export"
        
        # Headers
        headers = [
            "N° Ordine", "Cliente", "Data Ordine", "Stato",
            "Quantità Totale", "N° DDT", "N° PLT", "Evaso il"
        ]
        
        # Styling headers
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="0066CC", end_color="0066CC", fill_type="solid")
        header_alignment = Alignment(horizontal="center")
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
        
        # Popola dati
        for row, order in enumerate(orders, 2):
            # Calcola quantità totale ordine
            total_quantity = sum(line.requested_quantity for line in order.lines)
            
            # Determina stato
            if order.is_cancelled:
                status = "Annullato"
            elif order.is_archived:
                status = "Archiviato"
            elif order.is_completed:
                status = "Completato"
            else:
                status = "Attivo"
            
            # Popola riga
            ws.cell(row=row, column=1, value=order.order_number)
            ws.cell(row=row, column=2, value=order.customer_name or "")
            ws.cell(row=row, column=3, value=order.order_date.strftime("%d/%m/%Y") if order.order_date else "")
            ws.cell(row=row, column=4, value=status)
            ws.cell(row=row, column=5, value=total_quantity)
            ws.cell(row=row, column=6, value=order.ddt_number or "")
            ws.cell(row=row, column=7, value=order.plt_number or "")
            ws.cell(row=row, column=8, value=order.archived_date.strftime("%d/%m/%Y") if order.archived_date else "")
        
        # Auto-dimensiona colonne
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
        
        # Nome file con date
        date_suffix = ""
        if from_date and to_date:
            date_suffix = f"_{from_date.strftime('%Y%m%d')}_{to_date.strftime('%Y%m%d')}"
        elif from_date:
            date_suffix = f"_dal_{from_date.strftime('%Y%m%d')}"
        elif to_date:
            date_suffix = f"_fino_{to_date.strftime('%Y%m%d')}"
            
        filename = f"export_ordini{date_suffix}.xlsx"
        
        return Response(
            content=buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'export Excel: {str(e)}")

@router.get("/export-pdf")
async def export_orders_pdf(
    from_date: Optional[date] = Query(None, description="Data inizio (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="Data fine (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Esporta ordini in formato PDF con filtro per range di date.
    Include sia ordini attivi che archiviati.
    """
    try:
        # Query unificata per ordini attivi e archiviati
        query = db.query(models.Order).options(joinedload(models.Order.lines))
        
        # Applica filtri date se forniti
        if from_date:
            query = query.filter(models.Order.order_date >= from_date)
        if to_date:
            query = query.filter(models.Order.order_date <= to_date)
            
        orders = query.order_by(models.Order.order_date.desc()).all()
        
        # Crea PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        # Stili
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1  # Center
        )
        
        # Contenuto PDF
        story = []
        
        # Titolo
        date_range = ""
        if from_date and to_date:
            date_range = f" ({from_date.strftime('%d/%m/%Y')} - {to_date.strftime('%d/%m/%Y')})"
        elif from_date:
            date_range = f" (dal {from_date.strftime('%d/%m/%Y')})"
        elif to_date:
            date_range = f" (fino al {to_date.strftime('%d/%m/%Y')})"
            
        title = Paragraph(f"Export Ordini{date_range}", title_style)
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Prepara dati tabella
        table_data = []
        table_data.append(["N° Ordine", "Cliente", "Data", "Stato", "Qtà Tot", "DDT", "PLT", "Evaso il"])
        
        for order in orders:
            # Calcola quantità totale
            total_quantity = sum(line.requested_quantity for line in order.lines)
            
            # Determina stato
            if order.is_cancelled:
                status = "Annullato"
            elif order.is_archived:
                status = "Archiviato"
            elif order.is_completed:
                status = "Completato"
            else:
                status = "Attivo"
            
            table_data.append([
                order.order_number or "",
                order.customer_name[:20] + "..." if order.customer_name and len(order.customer_name) > 20 else (order.customer_name or ""),
                order.order_date.strftime("%d/%m/%Y") if order.order_date else "",
                status,
                str(total_quantity),
                order.ddt_number or "",
                order.plt_number or "",
                order.archived_date.strftime("%d/%m/%Y") if order.archived_date else ""
            ])
        
        # Crea tabella
        table = Table(table_data, colWidths=[1.2*inch, 1.5*inch, 0.8*inch, 0.8*inch, 0.6*inch, 0.7*inch, 0.5*inch, 0.8*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        
        story.append(table)
        
        # Genera PDF
        doc.build(story)
        buffer.seek(0)
        
        # Nome file con date
        date_suffix = ""
        if from_date and to_date:
            date_suffix = f"_{from_date.strftime('%Y%m%d')}_{to_date.strftime('%Y%m%d')}"
        elif from_date:
            date_suffix = f"_dal_{from_date.strftime('%Y%m%d')}"
        elif to_date:
            date_suffix = f"_fino_{to_date.strftime('%Y%m%d')}"
            
        filename = f"export_ordini{date_suffix}.pdf"
        
        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'export PDF: {str(e)}")

@router.get("/archived")
def get_archived_orders(db: Session = Depends(get_db)):
    """Recupera tutti gli ordini archiviati."""
    try:
        archived_orders = db.query(models.Order).filter(
            models.Order.is_archived == 1
        ).options(joinedload(models.Order.lines).joinedload(models.OrderLine.product)).order_by(models.Order.id.desc()).all()
        
        orders_data = []
        for order in archived_orders:
            # Calcola il peso totale per ogni ordine
            total_weight = 0.0
            for line in order.lines:
                if line.product and line.product.weight:
                    total_weight += line.requested_quantity * line.product.weight
            
            order_data = {
                "id": order.id,
                "order_number": order.order_number,
                "customer_name": order.customer_name,
                "order_date": order.order_date.isoformat() if order.order_date else None,
                "archived_date": order.archived_date.isoformat() if order.archived_date else None,
                "is_completed": bool(order.is_completed),
                "is_cancelled": bool(order.is_cancelled),
                "ddt_number": order.ddt_number,
                "plt_number": order.plt_number,
                "carrier_name": order.carrier_name,
                "total_weight": total_weight,
                "lines": [
                    {
                        "product_sku": line.product_sku,
                        "requested_quantity": line.requested_quantity,
                        "picked_quantity": line.picked_quantity
                    }
                    for line in order.lines
                ]
            }
            orders_data.append(order_data)
        
        return {"orders": orders_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching archived orders: {str(e)}")

# --- API Endpoints con parametri di percorso (devono essere definiti dopo le rotte generiche) ---


@router.post("/import-orders-txt")
async def import_orders_from_txt(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Il file non è in formato UTF-8 valido.")

    orders_in_file = {}
    line_number = 0
    for line in text_content.splitlines():
        line_number += 1
        if not line.strip():
            continue
        
        parts = line.strip().split(',')
        if len(parts) != 4:
            raise HTTPException(status_code=400, detail=f"Formato non valido alla riga {line_number}: la riga deve contenere NumeroOrdine,Cliente,SKU,Qty")

        order_number, customer_name, sku, qty_str = parts
        order_number = order_number.strip()
        customer_name = customer_name.strip()
        sku = sku.strip()

        try:
            quantity = int(qty_str.strip())
            if quantity <= 0:
                raise ValueError("La quantità deve essere positiva.")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Quantità non valida alla riga {line_number}: '{qty_str}'")

        if order_number not in orders_in_file:
            orders_in_file[order_number] = {
                "customer_name": customer_name,
                "lines": []
            }
        
        orders_in_file[order_number]["lines"].append({"sku": sku, "quantity": quantity})

    created_count = 0
    updated_count = 0

    for order_number, order_data in orders_in_file.items():
        db_order = db.query(models.Order).filter(models.Order.order_number == order_number).first()

        if not db_order:
            # Crea un nuovo ordine
            db_order = models.Order(
                order_number=order_number, 
                customer_name=order_data['customer_name']
            )
            db.add(db_order)
            db.flush() # Per ottenere l'ID dell'ordine
            created_count += 1
        else:
            # Ordine esistente, verifica se è già completato
            if db_order.is_completed:
                continue # Salta gli ordini già completati
            updated_count += 1

        # Aggiungi le righe d'ordine
        for line in order_data['lines']:
            # Controlla se il prodotto esiste
            product = db.query(models.Product).filter(models.Product.sku == line['sku']).first()
            if not product:
                db.rollback()
                raise HTTPException(status_code=404, detail=f"Prodotto con SKU '{line['sku']}' non trovato per l'ordine '{order_number}'. L'importazione è stata annullata.")

            # Controlla se una riga simile esiste già per evitare duplicati
            existing_line = db.query(models.OrderLine).filter(
                models.OrderLine.order_id == db_order.id,
                models.OrderLine.product_sku == line['sku']
            ).first()

            if existing_line:
                # Aggiorna la quantità della riga esistente
                existing_line.requested_quantity += line['quantity']
            else:
                # Crea una nuova riga d'ordine
                new_line = models.OrderLine(
                    order_id=db_order.id,
                    product_sku=line['sku'],
                    requested_quantity=line['quantity']
                )
                db.add(new_line)

    # LOGGING: Registra l'import da file TXT
    logger = LoggingService(db)
    file_name = file.filename if hasattr(file, 'filename') else 'orders_import.txt'
    
    # Logga ogni prodotto di ogni ordine importato
    for order_number, order_data in orders_in_file.items():
        db_order = db.query(models.Order).filter(models.Order.order_number == order_number).first()
        if db_order:  # Solo se l'ordine è stato creato/aggiornato con successo
            for line in order_data['lines']:
                operation_type_to_use = OperationType.ORDINE_CREATO  # Default per ordini nuovi
                creation_method = 'file_import'
                
                # Determina se è creazione o aggiornamento
                if order_number in [o for o in orders_in_file.keys()]:
                    existing_order_check = db.query(models.Order).filter(
                        models.Order.order_number == order_number,
                        models.Order.id != db_order.id
                    ).first()
                    if existing_order_check:
                        operation_type_to_use = OperationType.ORDINE_MODIFICATO
                        creation_method = 'file_update'
                
                logger.log_operation(
                    operation_type=operation_type_to_use,
                    operation_category=OperationCategory.FILE,
                    status=OperationStatus.SUCCESS,
                    product_sku=line['sku'],  # SKU del prodotto importato
                    quantity=line['quantity'],  # Quantità richiesta
                    user_id="file_import_user",
                    file_name=f"ORDER_{order_number}",  # Numero ordine nella colonna Dettagli
                    details={
                        'order_number': order_number,  # Numero ordine nei dettagli JSON
                        'customer_name': order_data['customer_name'],
                        'creation_method': creation_method,
                        'source_file': file_name,
                        'operation_description': f"Import file: {creation_method} ordine {order_number}, aggiunto {line['quantity']}x {line['sku']} per cliente {order_data['customer_name']}",
                        'import_stats': {
                            'orders_created': created_count,
                            'orders_updated': updated_count
                        }
                    },
                    api_endpoint="/orders/import-orders-txt"
                )

    db.commit()
    return {"message": f"Importazione completata. Ordini creati: {created_count}. Ordini aggiornati: {updated_count}."}

# --- Nuovi Endpoint Picking (DEVONO essere prima di /{order_id}) ---

@router.post("/validate-picking-txt")
async def validate_picking_from_txt(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Valida le operazioni di picking da file TXT scanner e restituisce un recap dettagliato.
    Formato pistola scanner: numero ordine, ubicazione, EAN/SKU ripetuti o EAN/SKU_quantità
    Compatibile con il sistema recap dell'inventario per editing pre-commit.
    """
    try:
        picking_data, parse_errors = await _parse_picking_file_scanner(file, db)
    except HTTPException as e:
        raise e
    
    recap_items = []
    errors = []
    warnings = []
    line_counter = 0
    
    # Prepara mappe per validazione
    all_orders = {o.order_number: o for o in db.query(models.Order).options(joinedload(models.Order.lines)).all()}
    all_products = {p.sku: p for p in db.query(models.Product).all()}
    all_eans = {e.ean: e.product_sku for e in db.query(models.EanCode).all()}
    
    # Aggiungi errori di parsing al recap
    for parse_error in parse_errors:
        errors.append({
            "line": parse_error["line"],
            "message": parse_error["message"],
            "field": parse_error["field"],
            "value": parse_error["value"]
        })
        
        # Crea un recap item per permettere la correzione
        line_counter += 1
        
        # Determina customer_name se l'ordine esiste
        customer_name = ""
        if parse_error["order"] != "MANCANTE":
            order = all_orders.get(parse_error["order"])
            if order:
                customer_name = order.customer_name
        
        # Logica migliorata per i campi
        location = ""
        sku = ""
        
        if parse_error["field"] == "location":
            # Manca solo l'ubicazione, il prodotto è specificato
            location = ""  # Campo vuoto da compilare
            sku = parse_error["value"]  # Mantieni il SKU dal file
        elif parse_error["field"] == "sku":
            # Prodotto non trovato nel database, ubicazione è ok
            location = parse_error["location"]
            sku = parse_error["value"]  # Mantieni quello dal file per editing
        elif parse_error["field"] == "order":
            # Ordine mancante
            location = parse_error["location"] if parse_error["location"] != "MANCANTE" else ""
            sku = parse_error["value"]
        else:
            # Caso generale
            location = parse_error["location"] if parse_error["location"] != "MANCANTE" else ""
            sku = parse_error["value"]
        
        recap_item = {
            "line": parse_error["line"],
            "order_number": parse_error["order"] if parse_error["order"] != "MANCANTE" else "",
            "customer_name": customer_name,
            "location": location,
            "sku": sku,
            "description": "",
            "input_code": parse_error["value"],
            "quantity": 1,
            "current_stock": 0,
            "remaining_to_pick": 0,
            "remaining_stock": 0,
            "status": "error"
        }
        recap_items.append(recap_item)
    
    # Processa tutti i dati parsati correttamente
    for order_number, locations_data in picking_data.items():
        order = all_orders.get(order_number)
        
        for location, skus_data in locations_data.items():
            for sku, quantity in skus_data.items():
                line_counter += 1
                
                # Prepara item recap
                recap_item = {
                    "line": line_counter,
                    "order_number": order_number,
                    "customer_name": order.customer_name if order else "ORDINE NON TROVATO",
                    "location": location,
                    "sku": sku,
                    "description": "",
                    "input_code": sku,  # Codice originale dal file
                    "quantity": quantity,
                    "current_stock": 0,
                    "remaining_to_pick": 0,
                    "remaining_stock": 0,
                    "status": "ok"
                }
                
                # Validazione ordine
                if not order:
                    errors.append({
                        "line": line_counter,
                        "message": f"Ordine '{order_number}' non trovato nel database",
                        "field": "order_number",
                        "value": order_number
                    })
                    recap_item["status"] = "error"
                    recap_item["customer_name"] = "ORDINE NON TROVATO"
                    
                elif order.is_completed:
                    errors.append({
                        "line": line_counter,
                        "message": f"Ordine '{order_number}' è già completato",
                        "field": "order",
                        "value": order_number
                    })
                    recap_item["status"] = "error"
                    
                else:
                    # Validazione prodotto nell'ordine
                    order_line = None
                    for line in order.lines:
                        if line.product_sku == sku:
                            order_line = line
                            break
                    
                    if not order_line:
                        # Controlla se è un EAN code che corrisponde a un SKU nell'ordine
                        actual_sku = all_eans.get(sku)
                        if actual_sku:
                            for line in order.lines:
                                if line.product_sku == actual_sku:
                                    order_line = line
                                    recap_item["sku"] = actual_sku  # Aggiorna con il SKU corretto
                                    break
                    
                    if not order_line:
                        errors.append({
                            "line": line_counter,
                            "message": f"Prodotto '{sku}' non presente nell'ordine {order_number}",
                            "field": "sku",
                            "value": sku
                        })
                        recap_item["status"] = "error"
                    else:
                        # Calcola quantità rimanente da prelevare dall'ordine
                        remaining_order = order_line.requested_quantity - order_line.picked_quantity
                        recap_item["remaining_to_pick"] = remaining_order
                        
                        if quantity > remaining_order:
                            if remaining_order == 0:
                                warnings.append({
                                    "line": line_counter,
                                    "message": f"Prodotto '{sku}' già completamente prelevato per ordine {order_number}",
                                    "field": "quantity",
                                    "value": quantity
                                })
                                recap_item["status"] = "warning"
                            else:
                                warnings.append({
                                    "line": line_counter,
                                    "message": f"Quantità eccessiva: rimanenti da prelevare {remaining_order}, tentativo prelievo {quantity}",
                                    "field": "quantity", 
                                    "value": quantity
                                })
                                recap_item["status"] = "warning"
                
                # Validazione giacenza
                inventory_item = db.query(models.Inventory).filter(
                    models.Inventory.location_name == location,
                    models.Inventory.product_sku == recap_item["sku"]
                ).first()
                
                if inventory_item:
                    recap_item["current_stock"] = inventory_item.quantity
                    # Calcola giacenza rimanente dopo il prelievo
                    recap_item["remaining_stock"] = max(0, inventory_item.quantity - quantity)
                    if inventory_item.quantity < quantity:
                        errors.append({
                            "line": line_counter,
                            "message": f"Giacenza insufficiente in '{location}': disponibili {inventory_item.quantity}, richiesti {quantity}",
                            "field": "quantity",
                            "value": quantity
                        })
                        recap_item["status"] = "error"
                else:
                    recap_item["current_stock"] = 0
                    recap_item["remaining_stock"] = 0
                    errors.append({
                        "line": line_counter,
                        "message": f"Prodotto '{recap_item['sku']}' non presente in ubicazione '{location}'",
                        "field": "location",
                        "value": location
                    })
                    recap_item["status"] = "error"
                
                # Aggiungi descrizione prodotto se disponibile
                product = all_products.get(recap_item["sku"])
                if product:
                    recap_item["description"] = product.description
                
                recap_items.append(recap_item)
    
    # Prepara risultato finale in formato compatibile con recap inventory
    result = {
        "recap_items": recap_items,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "total": len(recap_items),
            "ok": len([item for item in recap_items if item["status"] == "ok"]),
            "warnings": len([item for item in recap_items if item["status"] == "warning"]),
            "errors": len([item for item in recap_items if item["status"] == "error"])
        },
        "orders_summary": {}
    }
    
    # Aggiungi summary per ordine
    for order_number in picking_data.keys():
        order = all_orders.get(order_number)
        if order:
            order_items = [item for item in recap_items if item["order_number"] == order_number]
            result["orders_summary"][order_number] = {
                "customer_name": order.customer_name,
                "is_completed": order.is_completed,
                "total_operations": len(order_items),
                "valid_operations": len([item for item in order_items if item["status"] == "ok"]),
                "lines": {line.product_sku: {
                    "requested": line.requested_quantity,
                    "picked": line.picked_quantity,
                    "remaining": line.requested_quantity - line.picked_quantity
                } for line in order.lines}
            }
    
    return result

@router.post("/commit-picking-txt")
async def commit_picking_from_txt(file: UploadFile = File(...), force: bool = False, db: Session = Depends(get_db)):
    """
    Commit delle operazioni di picking dopo validazione.
    Se force=True, esegue solo le operazioni valide ignorando quelle con warning/errori.
    """
    try:
        picking_data, parse_errors = await _parse_picking_file_scanner(file, db)
    except HTTPException as e:
        raise e
    
    if not picking_data and not parse_errors:
        raise HTTPException(status_code=400, detail="Il file è vuoto o non contiene dati validi.")
    
    if parse_errors and not force:
        raise HTTPException(status_code=400, detail=f"Errori di parsing trovati. Usa force=true per ignorarli: {len(parse_errors)} errori")
    
    successful_operations = []
    skipped_operations = []
    
    for order_number, locations_data in picking_data.items():
        # Trova l'ordine
        order = db.query(models.Order).filter(models.Order.order_number == order_number).first()
        if not order or order.is_completed:
            skipped_operations.append(f"Ordine '{order_number}' saltato (non trovato o completato)")
            continue
        
        for location, skus_data in locations_data.items():
            for sku, quantity in skus_data.items():
                # Trova la riga ordine
                order_line = db.query(models.OrderLine).filter(
                    models.OrderLine.order_id == order.id,
                    models.OrderLine.product_sku == sku
                ).first()
                
                if not order_line:
                    skipped_operations.append(f"Prodotto '{sku}' non trovato nell'ordine '{order_number}'")
                    continue
                
                # Verifica giacenza disponibile
                inventory_item = db.query(models.Inventory).filter(
                    models.Inventory.location_name == location,
                    models.Inventory.product_sku == sku
                ).first()
                
                if not inventory_item or inventory_item.quantity < quantity:
                    skipped_operations.append(f"Giacenza insufficiente per {sku} in {location}")
                    continue
                
                # Verifica quantità ordine (con tolleranza se force=True)
                remaining_to_pick = order_line.requested_quantity - order_line.picked_quantity
                actual_quantity = quantity
                
                if quantity > remaining_to_pick:
                    if force and remaining_to_pick > 0:
                        actual_quantity = remaining_to_pick  # Preleva solo quello che serve
                        skipped_operations.append(f"Ridotta quantità per {sku} da {quantity} a {actual_quantity}")
                    elif remaining_to_pick == 0:
                        skipped_operations.append(f"Saltato {sku}: già completamente prelevato")
                        continue
                    else:
                        skipped_operations.append(f"Saltato {sku}: quantità eccessiva")
                        continue
                
                # Esegui l'operazione di picking
                inventory_item.quantity -= actual_quantity
                order_line.picked_quantity += actual_quantity
                
                # Aggiungi a OutgoingStock
                outgoing_item = db.query(models.OutgoingStock).filter(
                    models.OutgoingStock.order_line_id == order_line.id,
                    models.OutgoingStock.product_sku == sku
                ).first()
                
                if outgoing_item:
                    outgoing_item.quantity += actual_quantity
                else:
                    new_outgoing_item = models.OutgoingStock(
                        order_line_id=order_line.id,
                        product_sku=sku,
                        quantity=actual_quantity
                    )
                    db.add(new_outgoing_item)
                
                successful_operations.append(f"Prelevato {actual_quantity}x {sku} da {location} per ordine {order_number}")
    
    if not successful_operations and not force:
        db.rollback()
        raise HTTPException(status_code=400, detail="Nessuna operazione valida da eseguire")
    
    # LOGGING: Registra le operazioni di picking da file
    logger = LoggingService(db)
    
    # Prepara operazioni per logging
    batch_operations = []
    for order_number, locations_data in picking_data.items():
        for location, skus_data in locations_data.items():
            for sku, quantity in skus_data.items():
                # Controlla se l'operazione è stata eseguita con successo
                operation_found = any(f"{quantity}x {sku} da {location} per ordine {order_number}" in op 
                                    for op in successful_operations)
                if operation_found:
                    batch_operations.append({
                        'product_sku': sku,
                        'location_from': location,
                        'location_to': None,  # Picking: scala da inventario
                        'quantity': quantity,
                        'status': OperationStatus.SUCCESS,
                        'details': {
                            'order_number': order_number,
                            'operation_description': f"Picking da file: {sku} ({quantity} pz) da {location} per ordine {order_number}",
                            'source': 'picking_file_scanner',
                            'picking_type': 'file_picking'
                        }
                    })
    
    # Registra operazioni senza log batch start/end
    if batch_operations:
        file_name = file.filename if hasattr(file, 'filename') else 'picking_file.txt'
        logger.log_file_operations(
            operation_type=OperationType.PRELIEVO_FILE,
            operation_category=OperationCategory.FILE,
            operations=batch_operations,
            file_name=file_name,
            user_id="file_user"
        )
    
    db.commit()
    
    return {
        "message": f"Picking completato: {len(successful_operations)} operazioni eseguite",
        "successful_operations": successful_operations,
        "skipped_operations": skipped_operations,
        "force_mode": force
    }

@router.post("/debug-picking-txt")
async def debug_picking_from_txt(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Endpoint di debug per verificare il parsing del file scanner.
    """
    try:
        picking_data, parse_errors = await _parse_picking_file_scanner(file, db)
        
        # Check database contents
        all_locations = {loc.name for loc in db.query(models.Location).all()}
        all_products = {p.sku for p in db.query(models.Product).all()}
        all_eans = {e.ean: e.product_sku for e in db.query(models.EanCode).all()}
        
        return {
            "file_name": file.filename,
            "parsed_data": dict(picking_data),
            "parse_errors": parse_errors,
            "parser_used": "new_scanner_parser",
            "database_info": {
                "locations": list(all_locations)[:10],
                "products": list(all_products)[:10], 
                "eans": list(all_eans.keys())[:10]
            }
        }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

@router.post("/import-picking-txt")
async def import_picking_from_txt_legacy(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Endpoint legacy che usa il nuovo parser scanner ma mantiene il comportamento originale.
    """
    try:
        # Parsing con il nuovo formato scanner
        picking_data, parse_errors = await _parse_picking_file_scanner(file, db)
        
        if not picking_data and not parse_errors:
            raise HTTPException(status_code=400, detail="Il file è vuoto o non contiene dati validi.")
        
        if parse_errors:
            # Endpoint legacy fallisce con errori di parsing
            error_messages = [f"Riga {e['line']}: {e['message']}" for e in parse_errors]
            raise HTTPException(status_code=400, detail=f"Errori nel parsing: {'; '.join(error_messages)}")
        
        return {"message": f"Parser chiamato correttamente. Ordini trovati: {list(picking_data.keys())}"}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")

# --- Export Prodotti per Ordine (prima degli endpoint con path parameters) ---

@router.get("/export-products-excel")
async def export_products_excel(
    from_date: Optional[date] = Query(None, description="Data inizio (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="Data fine (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Esporta i prodotti per ordine usciti in formato Excel con filtro per range di date.
    Una riga per ogni prodotto-ordine con dettagli completi.
    """
    if not EXCEL_AVAILABLE:
        raise HTTPException(status_code=500, detail="Export Excel non disponibile. Installare openpyxl.")
    
    try:
        # Query usando il pattern che funziona nel resto del sistema
        query = db.query(models.Order).options(
            joinedload(models.Order.lines).joinedload(models.OrderLine.product)
        )
        
        # Applica filtri date se forniti
        if from_date:
            query = query.filter(models.Order.order_date >= from_date)
        if to_date:
            query = query.filter(models.Order.order_date <= to_date)
        
        # Ordinamento per data decrescente
        orders = query.order_by(models.Order.order_date.desc()).all()
        
        if not orders:
            raise HTTPException(status_code=404, detail="Nessun ordine trovato per il periodo specificato.")
        
        # Estrai tutte le righe prodotto da tutti gli ordini
        product_lines = []
        for order in orders:
            for line in order.lines:
                product_lines.append({
                    'order_number': order.order_number,
                    'customer_name': order.customer_name,
                    'order_date': order.order_date,
                    'ddt_number': order.ddt_number,
                    'plt_number': order.plt_number,
                    'is_completed': order.is_completed,
                    'is_cancelled': order.is_cancelled,
                    'is_archived': order.is_archived,
                    'product_sku': line.product_sku,
                    'requested_quantity': line.requested_quantity,
                    'picked_quantity': line.picked_quantity,
                    'description': line.product.description if line.product else ""
                })

        if not product_lines:
            raise HTTPException(status_code=404, detail="Nessun prodotto trovato negli ordini del periodo specificato.")

        # Creazione del workbook Excel
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Prodotti per Ordine"
        
        # Intestazioni delle colonne
        headers = [
            "N° Ordine",
            "Cliente",
            "Data Ordine",
            "DDT",
            "PLT",
            "SKU Prodotto",
            "Descrizione Prodotto",
            "Quantità Richiesta",
            "Quantità Prelevata",
            "Stato Riga",
            "Stato Ordine"
        ]
        
        # Scrivi le intestazioni con formattazione
        for col, header in enumerate(headers, 1):
            cell = worksheet.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="CCE5FF", end_color="CCE5FF", fill_type="solid")
        
        # Scrivi i dati delle righe prodotto
        for row, product_line in enumerate(product_lines, 2):
            # Determina lo stato della riga prodotto
            if product_line['picked_quantity'] == 0:
                riga_status = "Non Prelevato"
            elif product_line['picked_quantity'] >= product_line['requested_quantity']:
                riga_status = "Completo"
            else:
                riga_status = "Parziale"
            
            # Stato ordine (usa stessa logica dell'export ordini)
            if product_line['is_cancelled']:
                ordine_status = "Annullato"
            elif product_line['is_archived']:
                ordine_status = "Archiviato"
            elif product_line['is_completed']:
                ordine_status = "Completato"
            else:
                ordine_status = "Attivo"
            
            # Scrivi i dati della riga
            data = [
                product_line['order_number'],
                product_line['customer_name'],
                product_line['order_date'].strftime("%Y-%m-%d") if product_line['order_date'] else "",
                product_line['ddt_number'] or "",
                product_line['plt_number'] or "",
                product_line['product_sku'],
                product_line['description'] or "",
                product_line['requested_quantity'],
                product_line['picked_quantity'],
                riga_status,
                ordine_status
            ]
            
            for col, value in enumerate(data, 1):
                worksheet.cell(row=row, column=col, value=value)
        
        # Auto-dimensiona le colonne
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Salva in memory buffer
        buffer = io.BytesIO()
        workbook.save(buffer)
        buffer.seek(0)
        
        # Genera nome file dinamico
        filename = "export_prodotti_ordini"
        if from_date or to_date:
            filename += f"_{from_date or 'inizio'}_{to_date or 'fine'}"
        filename += ".xlsx"
        
        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        }
        
        return Response(content=buffer.read(), headers=headers)
        
    except Exception as e:
        logger.error(f"Errore nella generazione dell'Excel prodotti per ordine: {str(e)}")
        raise HTTPException(status_code=500, detail="Errore interno del server")


@router.get("/export-products-pdf")
async def export_products_pdf(
    from_date: Optional[date] = Query(None, description="Data inizio (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="Data fine (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Esporta i prodotti per ordine usciti in formato PDF con filtro per range di date.
    Una riga per ogni prodotto-ordine con dettagli completi.
    """
    try:
        # Query usando il pattern che funziona nel resto del sistema (stessa del Excel)
        query = db.query(models.Order).options(
            joinedload(models.Order.lines).joinedload(models.OrderLine.product)
        )
        
        # Applica filtri date se forniti
        if from_date:
            query = query.filter(models.Order.order_date >= from_date)
        if to_date:
            query = query.filter(models.Order.order_date <= to_date)
        
        # Ordinamento per data decrescente
        orders = query.order_by(models.Order.order_date.desc()).all()
        
        if not orders:
            raise HTTPException(status_code=404, detail="Nessun ordine trovato per il periodo specificato.")
        
        # Estrai tutte le righe prodotto da tutti gli ordini
        product_lines = []
        for order in orders:
            for line in order.lines:
                product_lines.append({
                    'order_number': order.order_number,
                    'customer_name': order.customer_name,
                    'order_date': order.order_date,
                    'ddt_number': order.ddt_number,
                    'plt_number': order.plt_number,
                    'is_completed': order.is_completed,
                    'is_cancelled': order.is_cancelled,
                    'is_archived': order.is_archived,
                    'product_sku': line.product_sku,
                    'requested_quantity': line.requested_quantity,
                    'picked_quantity': line.picked_quantity,
                    'description': line.product.description if line.product else ""
                })

        if not product_lines:
            raise HTTPException(status_code=404, detail="Nessun prodotto trovato negli ordini del periodo specificato.")

        # Creazione del PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=40, bottomMargin=40)
        
        # Stili
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1  # Center
        )
        
        # Contenuto del PDF
        story = []
        
        # Titolo
        period_text = ""
        if from_date or to_date:
            period_text = f" ({from_date or 'inizio'} - {to_date or 'fine'})"
        title = Paragraph(f"Report Prodotti per Ordine Usciti{period_text}", title_style)
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Tabella con i dati
        table_data = [
            ['N° Ordine', 'Cliente', 'Data', 'PLT', 'SKU', 'Descrizione', 'Richiesto', 'Prelevato', 'Stato']
        ]

        # Aggiungi le righe dei prodotti
        for product_line in product_lines:
            # Determina lo stato della riga prodotto
            if product_line['picked_quantity'] == 0:
                riga_status = "Non Prelevato"
            elif product_line['picked_quantity'] >= product_line['requested_quantity']:
                riga_status = "Completo"
            else:
                riga_status = "Parziale"

            # Formatta i dati per la tabella (accorcia per PDF)
            row = [
                product_line['order_number'][:12] + "..." if len(product_line['order_number']) > 15 else product_line['order_number'],
                product_line['customer_name'][:15] + "..." if len(product_line['customer_name']) > 18 else product_line['customer_name'],
                product_line['order_date'].strftime("%d/%m/%y") if product_line['order_date'] else "",
                product_line['plt_number'] or "",
                product_line['product_sku'][:12] + "..." if len(product_line['product_sku']) > 15 else product_line['product_sku'],
                (product_line['description'][:20] + "..." if len(product_line['description'] or "") > 23 else product_line['description'] or ""),
                str(product_line['requested_quantity']),
                str(product_line['picked_quantity']),
                riga_status[:8]
            ]
            table_data.append(row)

        # Crea la tabella
        table = Table(table_data, colWidths=[55, 75, 42, 28, 65, 90, 38, 38, 44])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        
        # Genera il PDF
        doc.build(story)
        pdf_content = buffer.getvalue()
        buffer.close()
        
        # Genera nome file dinamico
        filename = "export_prodotti_ordini"
        if from_date or to_date:
            filename += f"_{from_date or 'inizio'}_{to_date or 'fine'}"
        filename += ".pdf"
        
        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "application/pdf"
        }
        
        return Response(content=pdf_content, media_type="application/pdf", headers=headers)
        
    except Exception as e:
        logger.error(f"Errore nella generazione del PDF prodotti per ordine: {str(e)}")
        raise HTTPException(status_code=500, detail="Errore interno del server")


# --- API Endpoints con parametri di percorso (devono essere definiti dopo le rotte generiche) ---

@router.get("/open-for-picking")
def get_open_orders_for_picking(
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("orders_picking_scan"))
):
    """Lista ordini aperti con progress picking per il modal di selezione."""
    orders = db.query(models.Order).filter(
        models.Order.is_completed == False,
        models.Order.is_cancelled == False,
        models.Order.is_archived == False
    ).options(
        joinedload(models.Order.lines).joinedload(models.OrderLine.product)
    ).order_by(models.Order.id.desc()).all()

    result = []
    for order in orders:
        lines_data = []
        total_items = 0
        total_picked = 0
        for line in order.lines:
            remaining = line.requested_quantity - line.picked_quantity
            lines_data.append({
                "order_line_id": line.id,
                "product_sku": line.product_sku,
                "product_name": line.product.description if line.product else None,
                "requested_quantity": line.requested_quantity,
                "picked_quantity": line.picked_quantity,
                "remaining": remaining
            })
            total_items += line.requested_quantity
            total_picked += line.picked_quantity

        result.append({
            "order_id": order.id,
            "order_number": order.order_number,
            "customer_name": order.customer_name,
            "lines": lines_data,
            "total_items": total_items,
            "total_picked": total_picked,
            "is_fully_picked": total_picked >= total_items and total_items > 0
        })

    return {"orders": result}


@router.get("/{order_id}", response_model=schemas.Order)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).options(joinedload(models.Order.lines)).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

# --- Logica di Picking ---

@router.get("/{order_id}/picking-suggestions", response_model=Dict[str, schemas.PickingSuggestion])
def get_picking_suggestions(order_id: int, db: Session = Depends(get_db)):
    from wms_app.services.reservation_service import ReservationService
    
    order = db.query(models.Order).options(joinedload(models.Order.lines)).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.is_completed:
        raise HTTPException(status_code=400, detail="Order is already completed")

    # Inizializza il servizio di prenotazioni
    reservation_service = ReservationService(db)
    
    # Pulisce automaticamente le prenotazioni scadute
    reservation_service.cleanup_expired_reservations()
    
    # Prepara lista prodotti necessari per l'ordine
    products_needed = []
    for line in order.lines:
        if line.requested_quantity > line.picked_quantity:
            remaining_to_pick = line.requested_quantity - line.picked_quantity
            products_needed.append({
                'sku': line.product_sku,
                'quantity': remaining_to_pick,
                'line_id': line.id
            })
    
    if not products_needed:
        return {}  # Ordine già completamente prelevato
    
    # Usa il Round-Robin Reservation System per allocare ubicazioni
    try:
        allocations = reservation_service.allocate_picking_locations(
            order_id=str(order.order_number), 
            products_needed=products_needed
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore allocazione picking: {str(e)}")
    
    # Converte il risultato nel formato atteso dal frontend
    suggestions = {}
    for allocation in allocations:
        sku = allocation['sku']
        
        product_suggestions = []
        for loc_allocation in allocation['allocations']:
            product_suggestions.append({
                "location_name": loc_allocation['location_name'],
                "quantity": loc_allocation['quantity'],
                "reservation_id": loc_allocation['reservation_id']  # Nuovo campo per tracking
            })
        
        if allocation['fully_allocated']:
            suggestions[sku] = schemas.PickingSuggestion(
                status="full_stock",
                needed=allocation['requested_quantity'],
                available_in_locations=product_suggestions
            )
        elif len(allocation['allocations']) > 0:
            # Stock parziale disponibile
            suggestions[sku] = schemas.PickingSuggestion(
                status="partial_stock",
                needed=allocation['requested_quantity'],
                available_in_locations=product_suggestions
            )
        else:
            # Nessuna allocazione disponibile - prodotto non presente in inventario
            suggestions[sku] = schemas.PickingSuggestion(
                status="out_of_stock",
                needed=allocation['requested_quantity'],
                available_in_locations=[]
            )
    
    return suggestions

@router.post("/{order_id}/confirm-pick", response_model=schemas.Order)
def confirm_pick(order_id: int, pick_confirmation: schemas.PickConfirmation, db: Session = Depends(get_db)):
    from wms_app.services.reservation_service import ReservationService
    
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.is_completed:
        raise HTTPException(status_code=400, detail="Order is already completed")

    reservation_service = ReservationService(db)

    for picked_item in pick_confirmation.picked_items:
        order_line = db.query(models.OrderLine).filter(
            models.OrderLine.id == picked_item.order_line_id,
            models.OrderLine.order_id == order_id
        ).first()
        if not order_line:
            raise HTTPException(status_code=404, detail=f"Order line {picked_item.order_line_id} not found for this order")

        inventory_item = db.query(models.Inventory).filter(
            models.Inventory.product_sku == picked_item.product_sku,
            models.Inventory.location_name == picked_item.location_name
        ).first()

        if not inventory_item or inventory_item.quantity < picked_item.quantity:
            raise HTTPException(status_code=400, detail=f"Not enough stock of {picked_item.product_sku} in {picked_item.location_name} to pick {picked_item.quantity}")

        # Scala dalla giacenza
        inventory_item.quantity -= picked_item.quantity
        order_line.picked_quantity += picked_item.quantity

        # Sposta in OutgoingStock
        outgoing_item = db.query(models.OutgoingStock).filter(
            models.OutgoingStock.order_line_id == picked_item.order_line_id,
            models.OutgoingStock.product_sku == picked_item.product_sku
        ).first()

        if outgoing_item:
            outgoing_item.quantity += picked_item.quantity
        else:
            new_outgoing_item = models.OutgoingStock(
                order_line_id=picked_item.order_line_id,
                product_sku=picked_item.product_sku,
                quantity=picked_item.quantity
            )
            db.add(new_outgoing_item)
        
        # NUOVO: Completa la prenotazione se present
        # Cerca prenotazioni attive per questo ordine/prodotto/ubicazione
        if hasattr(picked_item, 'reservation_id') and picked_item.reservation_id:
            reservation_service.complete_reservation(picked_item.reservation_id, picked_item.quantity)
        else:
            # Fallback: cerca prenotazione per order_number/sku/location
            from wms_app.models.reservations import InventoryReservation
            reservation = db.query(InventoryReservation).filter(
                InventoryReservation.order_id == str(order.order_number),
                InventoryReservation.product_sku == picked_item.product_sku,
                InventoryReservation.location_name == picked_item.location_name,
                InventoryReservation.status == 'active'
            ).first()
            
            if reservation:
                reservation_service.complete_reservation(reservation.id, picked_item.quantity)
    
    # LOGGING: Registra le operazioni di picking manuale
    logger = LoggingService(db)
    
    # Crea operazioni di log per ogni item prelevato
    for picked_item in pick_confirmation.picked_items:
        logger.log_operation(
            operation_type=OperationType.PRELIEVO_MANUALE,
            operation_category=OperationCategory.MANUAL,
            status=OperationStatus.SUCCESS,
            product_sku=picked_item.product_sku,
            location_from=picked_item.location_name,
            location_to=None,  # Picking: scala da inventario
            quantity=picked_item.quantity,
            user_id="picking_user",  # TODO: Sostituire con sistema auth reale
            details={
                'order_number': order.order_number,
                'order_line_id': picked_item.order_line_id,
                'operation_description': f"Picking manuale: {picked_item.product_sku} ({picked_item.quantity} pz) da {picked_item.location_name} per ordine {order.order_number}",
                'picking_type': 'manual_picking',
                'reservation_id': getattr(picked_item, 'reservation_id', None),
                'customer_name': order.customer_name
            },
            api_endpoint="/orders/{order_id}/confirm-pick"
        )
    
    db.commit()
    db.refresh(order)
    return order

@router.post("/{order_id}/fulfill", response_model=schemas.Order)
def fulfill_order(order_id: int, db: Session = Depends(get_db)):
    # LOGGING: Inizializza logger per tracciare tutto il processo
    logger = LoggingService(db)

    try:
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.is_completed:
            raise HTTPException(status_code=400, detail="Order is already completed")

        # Log inizio evasione
        print(f"🔄 FULFILL START: Order {order.order_number} (ID: {order_id}) - is_completed={order.is_completed}, is_archived={order.is_archived}")

        # Scala da OutgoingStock e completa l'ordine
        for line in order.lines:
            # FIX: Trova TUTTI i record OutgoingStock per questa linea d'ordine
            # (può esserci più di un record se prelevato da posizioni multiple)
            outgoing_items = db.query(models.OutgoingStock).filter(
                models.OutgoingStock.order_line_id == line.id,
                models.OutgoingStock.product_sku == line.product_sku
            ).all()

            # Verifica che la somma delle quantità in OutgoingStock corrisponda a picked_quantity
            total_outgoing_quantity = sum(item.quantity for item in outgoing_items)
            if total_outgoing_quantity != line.picked_quantity:
                # Log del problema ma continua l'evasione (per compatibilità con dati esistenti)
                print(f"⚠️  WARNING: OutgoingStock mismatch for order {order.order_number}, line {line.id}: "
                      f"total_outgoing={total_outgoing_quantity}, picked={line.picked_quantity}")

            # Cancella TUTTI i record OutgoingStock per questa linea
            for outgoing_item in outgoing_items:
                db.delete(outgoing_item)

            if line.requested_quantity != line.picked_quantity:
                raise HTTPException(status_code=400, detail=f"Order line {line.id} not fully picked. Requested: {line.requested_quantity}, Picked: {line.picked_quantity}")

        # Imposta ordine come completato
        order.is_completed = True
        print(f"✅ FULFILL VALIDATION PASSED: Order {order.order_number} - setting is_completed=True")

        # Prepara dettagli per il log
        order_summary = []
        total_items_fulfilled = 0

        for line in order.lines:
            order_summary.append({
                'product_sku': line.product_sku,
                'requested_quantity': line.requested_quantity,
                'picked_quantity': line.picked_quantity
            })
            total_items_fulfilled += line.picked_quantity

        # Logga ogni prodotto evaso separatamente per visibilità nelle colonne SKU/Ubicazioni
        for line in order.lines:
            logger.log_operation(
                operation_type=OperationType.ORDINE_EVASO,
                operation_category=OperationCategory.MANUAL,
                status=OperationStatus.SUCCESS,
                product_sku=line.product_sku,  # SKU del prodotto evaso
                location_from="OUTGOING",  # Da giacenza in uscita
                location_to=None,  # Evasione (esce dal magazzino)
                quantity=line.picked_quantity,  # Quantità evasa
                user_id="fulfill_user",  # TODO: Sostituire con sistema auth reale
                file_name=f"ORDER_{order.order_number}",  # Numero ordine nella colonna Dettagli
                details={
                    'order_number': order.order_number,  # Numero ordine nei dettagli JSON
                    'customer_name': order.customer_name,
                    'order_date': order.order_date.isoformat() if order.order_date else None,
                    'operation_description': f"Evasione ordine {order.order_number}: evaso {line.picked_quantity}x {line.product_sku} per cliente {order.customer_name}",
                    'fulfill_type': 'manual_fulfill',
                    'order_line_id': line.id,
                    'requested_quantity': line.requested_quantity,
                    'total_order_items': total_items_fulfilled
                },
                api_endpoint=f"/orders/{order_id}/fulfill"
            )

        # COMMIT CON GESTIONE ERRORI ROBUSTA
        try:
            print(f"💾 FULFILL COMMIT: Attempting database commit for order {order.order_number}")
            db.commit()
            print(f"✅ FULFILL SUCCESS: Order {order.order_number} committed successfully - is_completed=True")

            db.refresh(order)
            return order

        except Exception as commit_error:
            # Rollback esplicito in caso di errore commit
            db.rollback()

            # Log errore dettagliato
            error_msg = f"Database commit failed for order {order.order_number}: {str(commit_error)}"
            print(f"❌ FULFILL COMMIT ERROR: {error_msg}")

            logger.log_error(
                operation_type="FULFILL_COMMIT_FAILED",
                error=commit_error,
                operation_category=OperationCategory.MANUAL,
                file_name=f"ORDER_{order.order_number}",
                details={
                    'order_id': order_id,
                    'order_number': order.order_number,
                    'customer_name': order.customer_name,
                    'error_type': type(commit_error).__name__,
                    'error_message': str(commit_error),
                    'operation_description': f"ERRORE CRITICO: Commit fallito durante evasione ordine {order.order_number}. L'ordine NON è stato evaso."
                },
                api_endpoint=f"/orders/{order_id}/fulfill"
            )

            # Restituisci errore chiaro all'utente
            raise HTTPException(
                status_code=500,
                detail=f"ERRORE CRITICO: Impossibile completare l'evasione dell'ordine {order.order_number}. "
                       f"Il database ha rifiutato la transazione. L'ordine NON è stato evaso. "
                       f"Contattare l'amministratore. Dettagli: {str(commit_error)}"
            )

    except HTTPException:
        # Re-raise HTTPExceptions (errori di validazione)
        raise

    except Exception as e:
        # Cattura qualsiasi altro errore imprevisto
        db.rollback()

        error_msg = f"Unexpected error during fulfill for order ID {order_id}: {str(e)}"
        print(f"❌ FULFILL UNEXPECTED ERROR: {error_msg}")

        logger.log_error(
            operation_type="FULFILL_UNEXPECTED_ERROR",
            error=e,
            operation_category=OperationCategory.MANUAL,
            details={
                'order_id': order_id,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'operation_description': f"Errore imprevisto durante evasione ordine ID {order_id}"
            },
            api_endpoint=f"/orders/{order_id}/fulfill"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Errore imprevisto durante l'evasione: {str(e)}"
        )

# --- Nuova Funzionalità: Picking da File TXT ---

async def _parse_picking_file_scanner(file: UploadFile, db: Session) -> Tuple[Dict[str, Dict[str, Dict[str, int]]], List[Dict[str, Any]]]:
    """
    Parsing del file di picking da pistola scanner con formato:
    - Riga 1: Numero Ordine
    - Riga 2: Ubicazione
    - Righe 3+: EAN/SKU ripetuti (quantità = numero ripetizioni) oppure EAN/SKU_quantità
    - Il pattern si ripete per più ordini
    
    Ritorna: (parsed_data, parse_errors)
    """
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Il file non è in formato UTF-8 valido.")
    
    lines = [line.strip() for line in text_content.splitlines() if line.strip()]
    parsed_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    parse_errors = []
    
    # Parsing migliorato per il formato scanner
    current_order = None
    current_location = None
    
    # Ottieni le ubicazioni esistenti dal database per confronto
    all_locations = {loc.name for loc in db.query(models.Location).all()}
    
    # Aggiunge anche tutti gli ordini esistenti per aiutare il riconoscimento
    all_orders = {o.order_number for o in db.query(models.Order).all()}
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # PRIMA verifica se è una ubicazione esistente nel database
        if line in all_locations:
            current_location = line
            continue
        
        # SECONDA verifica: è un ordine conosciuto nel database?
        if line in all_orders:
            current_order = line
            current_location = None
            continue
            
        # TERZA verifica: se non abbiamo ancora un ordine e la riga sembra un ordine
        # (solo numerico o molto corto), trattalo come ordine
        if current_order is None and (line.isdigit() or (len(line) <= 6 and line.replace('-', '').replace('_', '').isalnum())):
            current_order = line
            current_location = None
            continue
        
        # Altrimenti è un prodotto
        if current_order and current_location:
            ean_or_sku = line
            quantity = 1
            
            # Parsing quantità da formato SKU_quantità
            if '_' in ean_or_sku:
                parts = ean_or_sku.rsplit('_', 1)
                if len(parts) == 2 and parts[1].isdigit():
                    ean_or_sku = parts[0]
                    quantity = int(parts[1])
            
            # Trova SKU nel database
            sku_found = None
            try:
                # Prova come EAN
                ean_code = db.query(models.EanCode).filter(models.EanCode.ean == ean_or_sku).first()
                if ean_code:
                    sku_found = ean_code.product_sku
                else:
                    # Prova come SKU diretto
                    product = db.query(models.Product).filter(models.Product.sku == ean_or_sku).first()
                    if product:
                        sku_found = product.sku
            except Exception:
                # Ignora errori di database per evitare hang
                pass
            
            if sku_found:
                parsed_data[current_order][current_location][sku_found] += quantity
            else:
                parse_errors.append({
                    "line": i+1,
                    "message": f"EAN/SKU '{ean_or_sku}' non trovato nel database",
                    "field": "sku",
                    "value": ean_or_sku,
                    "order": current_order,
                    "location": current_location
                })
        else:
            # Gestisci casi speciali quando mancano ordine o ubicazione
            if current_order and not current_location:
                # Prodotto senza ubicazione - deve richiedere ubicazione
                parse_errors.append({
                    "line": i+1,
                    "message": f"Prodotto '{line}' senza ubicazione (ordine: {current_order})",
                    "field": "location",
                    "value": line,
                    "order": current_order,
                    "location": "MANCANTE"
                })
            elif not current_order:
                # Prodotto senza ordine
                parse_errors.append({
                    "line": i+1,
                    "message": f"Prodotto '{line}' senza numero ordine",
                    "field": "order",
                    "value": line,
                    "order": "MANCANTE",
                    "location": current_location or "MANCANTE"
                })
            else:
                parse_errors.append({
                    "line": i+1,
                    "message": f"Prodotto '{line}' senza ordine o ubicazione validi",
                    "field": "general",
                    "value": line,
                    "order": current_order or "MANCANTE",
                    "location": current_location or "MANCANTE"
                })
        
    return parsed_data, parse_errors

@router.get("/{order_id}/picking-list-print")
async def get_picking_list_print(order_id: int, db: Session = Depends(get_db)):
    """
    Genera una versione stampabile della picking list per un ordine.
    """
    order = db.query(models.Order).options(joinedload(models.Order.lines)).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Usa lo stesso sistema di prenotazioni della UI per coerenza
    from wms_app.services.reservation_service import ReservationService
    
    reservation_service = ReservationService(db)
    reservation_service.cleanup_expired_reservations()
    
    # Prepara lista prodotti necessari per l'ordine (stesso formato della UI)
    products_needed = []
    for line in order.lines:
        if line.requested_quantity > line.picked_quantity:
            remaining_to_pick = line.requested_quantity - line.picked_quantity
            products_needed.append({
                'sku': line.product_sku,
                'quantity': remaining_to_pick,
                'line_id': line.id
            })
    
    suggestions = {}
    
    if products_needed:
        try:
            # Usa il sistema di prenotazioni per allocare ubicazioni (come nella UI)
            allocations = reservation_service.allocate_picking_locations(
                order_id=str(order.order_number), 
                products_needed=products_needed
            )
            
            # Converte il risultato nel formato per la stampa
            for allocation in allocations:
                sku = allocation['sku']

                product_suggestions = []
                for loc_allocation in allocation['allocations']:
                    # Recupera la giacenza attuale nella locazione per controllo qualità
                    current_stock_item = db.query(models.Inventory).filter(
                        models.Inventory.location_name == loc_allocation['location_name'],
                        models.Inventory.product_sku == sku
                    ).first()

                    current_stock = current_stock_item.quantity if current_stock_item else 0

                    product_suggestions.append({
                        "location_name": loc_allocation['location_name'],
                        "quantity": loc_allocation['quantity'],
                        "current_stock": current_stock
                    })

                suggestions[sku] = {
                    "needed": allocation['requested_quantity'],
                    "locations": product_suggestions
                }
                
        except Exception as e:
            # Fallback: usa inventario fisico se il sistema prenotazioni fallisce
            for line in order.lines:
                if line.requested_quantity <= line.picked_quantity:
                    continue
                    
                remaining_to_pick = line.requested_quantity - line.picked_quantity
                product_sku = line.product_sku
                
                available_stock = db.query(models.Inventory).filter(
                    models.Inventory.product_sku == product_sku,
                    models.Inventory.quantity > 0
                ).order_by(
                    models.Inventory.location_name
                ).all()
                
                product_suggestions = []
                for item in available_stock:
                    if remaining_to_pick <= 0:
                        break

                    qty_from_location = min(remaining_to_pick, item.quantity)
                    product_suggestions.append({
                        "location_name": item.location_name,
                        "quantity": qty_from_location,
                        "current_stock": item.quantity  # Giacenza attuale per controllo qualità
                    })
                    remaining_to_pick -= qty_from_location
                
                suggestions[product_sku] = {
                    "needed": line.requested_quantity - line.picked_quantity,
                    "locations": product_suggestions
                }
    
    # Genera HTML stampabile
    # Prepara il numero ordine per il JavaScript
    order_number = order.order_number
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Picking List - Ordine {order_number}</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Libre+Barcode+39&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }}
            
            /* Layout a tre colonne per header */
            .header-content {{ 
                display: flex; 
                justify-content: space-between; 
                align-items: flex-start;
                margin-bottom: 20px;
            }}
            
            .order-info {{ 
                flex: 1; 
                padding-right: 20px;
            }}
            
            .barcode-container {{ 
                flex: 1; 
                text-align: center; 
                padding: 0 20px;
            }}
            .barcode {{ font-family: 'Libre Barcode 39', monospace; font-size: 48px; margin: 10px 0; }}
            .barcode-text {{ font-size: 14px; font-weight: bold; margin-top: 5px; }}
            
            .products-recap {{ 
                flex: 1; 
                padding-left: 20px;
                border-left: 1px solid #ccc;
            }}
            .products-recap h3 {{ 
                margin: 0 0 10px 0; 
                font-size: 16px; 
                color: #333;
            }}
            .product-item {{ 
                margin: 5px 0; 
                font-size: 14px; 
                display: flex; 
                justify-content: space-between;
                color: #000;
            }}
            .product-sku {{ 
                font-weight: bold; 
                color: #000;
            }}
            .product-qty {{ 
                font-weight: bold;
                color: #000;
            }}
            
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 13px; }}
            th, td {{ border: 1px solid #000; padding: 6px; text-align: left; }}
            th {{ background-color: #f0f0f0; font-weight: bold; text-align: center; }}
            .location {{ font-weight: bold; }}
            td:nth-child(3), td:nth-child(4), td:nth-child(5), td:nth-child(6) {{ text-align: center; }}
            @media print {{ 
                body {{ margin: 0; }}
                .no-print {{ display: none; }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>PICKING LIST</h1>
        </div>
        
        <div class="header-content">
            <!-- Colonna Sinistra: Info Ordine -->
            <div class="order-info">
                <p><strong>Numero Ordine:</strong> {order_number}</p>
                <p><strong>Cliente:</strong> {order.customer_name}</p>
                <p><strong>Data:</strong> {order.order_date.strftime('%d/%m/%Y %H:%M') if order.order_date else 'N/A'}</p>
            </div>
            
            <!-- Colonna Centrale: Barcode -->
            <div class="barcode-container">
                <div class="barcode">*{order_number}*</div>
                <div class="barcode-text">{order_number}</div>
            </div>
            
            <!-- Colonna Destra: Recap Prodotti -->
            <div class="products-recap">
                <h3>Quantità Ordine:</h3>"""

    # Aggiungi il recap dei prodotti richiesti (quantità totale richiesta, non rimanente)
    total_pieces_requested = 0
    for line in order.lines:
        total_pieces_requested += line.requested_quantity
        html_content += f"""
                <div class="product-item">
                    <span class="product-sku">{line.product_sku}</span>
                    <span class="product-qty">{line.requested_quantity} pz</span>
                </div>"""

    # Aggiungi totale pezzi
    html_content += f"""
                <div class="product-item" style="border-top: 1px solid #333; margin-top: 8px; padding-top: 8px; font-weight: bold;">
                    <span>TOTALE COLLI:</span>
                    <span class="product-qty">{total_pieces_requested} pz</span>
                </div>"""

    html_content += """
            </div>
        </div>
        <table>
            <thead>
                <tr>
                    <th>SKU</th>
                    <th>Ubicazione</th>
                    <th>Quantità da Prelevare</th>
                    <th>Qty in Locazione</th>
                    <th>Qty Post Prelievo</th>
                    <th>☐ Prelevato</th>
                </tr>
            </thead>
            <tbody>
    """

    for sku, suggestion in suggestions.items():
        for location in suggestion["locations"]:
            current_stock = location.get('current_stock', 0)
            qty_to_pick = location['quantity']
            qty_after_picking = current_stock - qty_to_pick

            # Evidenzia in grassetto se la locazione andrà a 0
            post_pick_style = "font-weight: bold; color: #FF5913;" if qty_after_picking == 0 else ""

            html_content += f"""
                <tr>
                    <td>{sku}</td>
                    <td class="location">{location['location_name']}</td>
                    <td style="text-align: center;">{qty_to_pick}</td>
                    <td style="text-align: center; font-weight: bold;">{current_stock}</td>
                    <td style="text-align: center; {post_pick_style}">{qty_after_picking}</td>
                    <td style="text-align: center; width: 50px;">☐</td>
                </tr>
            """
    
    html_content += """
            </tbody>
        </table>
        <div class="no-print">
            <button onclick="window.print()">Stampa</button>
            <button onclick="window.close()">Chiudi</button>
        </div>
        
        <script>
            // Auto-print quando la pagina è caricata
            window.onload = function() {{
                setTimeout(function() {{
                    window.print();
                }}, 500);
            }}
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

# --- Nuovi Endpoint per Gestione Archiviazione e Annullamento ---

@router.post("/{order_id}/archive")
def archive_order(order_id: int, fulfillment_request: schemas.FulfillmentRequest, db: Session = Depends(get_db)):
    """Archivia un ordine completato o annullato."""
    # LOGGING: Inizializza logger
    logger = LoggingService(db)

    try:
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # Log stato iniziale
        print(f"📦 ARCHIVE START: Order {order.order_number} (ID: {order_id}) - is_completed={order.is_completed}, is_cancelled={order.is_cancelled}, is_archived={order.is_archived}")

        # Validazione stato ordine con log dettagliato
        if not order.is_completed and not order.is_cancelled:
            error_msg = f"Cannot archive order {order.order_number}: not completed and not cancelled (is_completed={order.is_completed}, is_cancelled={order.is_cancelled})"
            print(f"❌ ARCHIVE VALIDATION FAILED: {error_msg}")

            logger.log_error(
                operation_type="ARCHIVE_VALIDATION_FAILED",
                error=error_msg,
                operation_category=OperationCategory.MANUAL,
                file_name=f"ORDER_{order.order_number}",
                details={
                    'order_id': order_id,
                    'order_number': order.order_number,
                    'is_completed': order.is_completed,
                    'is_cancelled': order.is_cancelled,
                    'is_archived': order.is_archived,
                    'error_reason': 'order_not_ready_for_archive',
                    'operation_description': f"Tentativo fallito di archiviare ordine {order.order_number}: l'ordine non è né completato né annullato"
                },
                api_endpoint=f"/orders/{order_id}/archive"
            )

            raise HTTPException(
                status_code=400,
                detail=f"L'ordine {order.order_number} non può essere archiviato perché non è stato completato o annullato. "
                       f"Stato attuale: is_completed={order.is_completed}, is_cancelled={order.is_cancelled}"
            )

        if order.is_archived:
            print(f"⚠️  ARCHIVE SKIP: Order {order.order_number} già archiviato")
            raise HTTPException(status_code=400, detail=f"Order {order.order_number} is already archived")

        # Verifica ulteriore: se l'ordine è completato, assicurati che OutgoingStock sia stato pulito
        if order.is_completed:
            outgoing_check = db.query(models.OutgoingStock).join(models.OrderLine).filter(
                models.OrderLine.order_id == order_id
            ).count()

            if outgoing_check > 0:
                warning_msg = f"WARNING: Order {order.order_number} has {outgoing_check} outgoing stock items still present (should be 0 if fulfilled)"
                print(f"⚠️  {warning_msg}")

                logger.log_warning(
                    operation_type="ARCHIVE_OUTGOING_WARNING",
                    warning_message=warning_msg,
                    operation_category=OperationCategory.MANUAL,
                    file_name=f"ORDER_{order.order_number}",
                    details={
                        'order_id': order_id,
                        'order_number': order.order_number,
                        'outgoing_stock_count': outgoing_check,
                        'operation_description': f"L'ordine {order.order_number} viene archiviato ma ha ancora {outgoing_check} record in OutgoingStock"
                    }
                )

        # Archivia l'ordine
        order.is_archived = True
        order.archived_date = datetime.utcnow()

        # Salva il numero DDT se fornito
        ddt_number = None
        if fulfillment_request.ddt_number:
            ddt_number = fulfillment_request.ddt_number.strip()
            order.ddt_number = ddt_number
            print(f"📄 ARCHIVE DDT: DDT number {ddt_number} assigned to order {order.order_number}")

        # Salva il numero PLT se fornito
        if fulfillment_request.plt_number:
            order.plt_number = fulfillment_request.plt_number.strip()

        # COMMIT CON GESTIONE ERRORI
        try:
            print(f"💾 ARCHIVE COMMIT: Attempting database commit for order {order.order_number}")
            db.commit()
            print(f"✅ ARCHIVE SUCCESS: Order {order.order_number} archived successfully - is_archived=True, DDT={ddt_number or 'none'}")

            # Log operazione di successo
            logger.log_operation(
                operation_type="ORDINE_ARCHIVIATO",
                operation_category=OperationCategory.MANUAL,
                status=OperationStatus.SUCCESS,
                file_name=f"ORDER_{order.order_number}",
                details={
                    'order_id': order_id,
                    'order_number': order.order_number,
                    'customer_name': order.customer_name,
                    'ddt_number': ddt_number,
                    'is_completed': order.is_completed,
                    'is_cancelled': order.is_cancelled,
                    'operation_description': f"Ordine {order.order_number} archiviato con successo" + (f" (DDT: {ddt_number})" if ddt_number else "")
                },
                api_endpoint=f"/orders/{order_id}/archive"
            )

            return {"message": f"Order {order.order_number} archived successfully"}

        except Exception as commit_error:
            # Rollback esplicito
            db.rollback()

            error_msg = f"Database commit failed for archiving order {order.order_number}: {str(commit_error)}"
            print(f"❌ ARCHIVE COMMIT ERROR: {error_msg}")

            logger.log_error(
                operation_type="ARCHIVE_COMMIT_FAILED",
                error=commit_error,
                operation_category=OperationCategory.MANUAL,
                file_name=f"ORDER_{order.order_number}",
                details={
                    'order_id': order_id,
                    'order_number': order.order_number,
                    'error_type': type(commit_error).__name__,
                    'error_message': str(commit_error),
                    'operation_description': f"Errore durante archiviazione ordine {order.order_number}"
                },
                api_endpoint=f"/orders/{order_id}/archive"
            )

            raise HTTPException(
                status_code=500,
                detail=f"Errore durante l'archiviazione dell'ordine {order.order_number}: {str(commit_error)}"
            )

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        db.rollback()

        error_msg = f"Unexpected error archiving order ID {order_id}: {str(e)}"
        print(f"❌ ARCHIVE UNEXPECTED ERROR: {error_msg}")

        logger.log_error(
            operation_type="ARCHIVE_UNEXPECTED_ERROR",
            error=e,
            operation_category=OperationCategory.MANUAL,
            details={
                'order_id': order_id,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'operation_description': f"Errore imprevisto durante archiviazione ordine ID {order_id}"
            },
            api_endpoint=f"/orders/{order_id}/archive"
        )

        raise HTTPException(status_code=500, detail=f"Error archiving order: {str(e)}")

@router.post("/{order_id}/cancel")
def cancel_order(order_id: int, db: Session = Depends(get_db)):
    """Annulla un ordine e rilascia la giacenza in uscita."""
    try:
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Validazione stato ordine
        
        if order.is_completed:
            raise HTTPException(status_code=400, detail="Cannot cancel a completed order")
        
        if order.is_cancelled:
            raise HTTPException(status_code=400, detail="Order is already cancelled")
        
        if order.is_archived:
            raise HTTPException(status_code=400, detail="Cannot cancel an archived order")
        
        # Recupera tutte le giacenze in uscita per questo ordine
        outgoing_stocks = db.query(models.OutgoingStock).join(models.OrderLine).filter(
            models.OrderLine.order_id == order_id
        ).all()
        
        released_items = []
        inventory_restored = []
        
        for stock in outgoing_stocks:
            released_items.append({
                "product_sku": stock.product_sku,
                "quantity": stock.quantity
            })
            
            # NUOVO: Ripristina giacenza in inventario (ipotesi: location TERRA)
            # Cerca se esiste già giacenza per questo prodotto in TERRA
            terra_inventory = db.query(models.Inventory).filter(
                models.Inventory.product_sku == stock.product_sku,
                models.Inventory.location_name == "TERRA"
            ).first()
            
            if terra_inventory:
                terra_inventory.quantity += stock.quantity
            else:
                # Crea nuovo record inventario in TERRA
                new_inventory = models.Inventory(
                    product_sku=stock.product_sku,
                    location_name="TERRA",
                    quantity=stock.quantity
                )
                db.add(new_inventory)
            
            inventory_restored.append({
                "product_sku": stock.product_sku,
                "quantity": stock.quantity,
                "restored_to": "TERRA"
            })
            
            # Rimuovi dalla giacenza in uscita
            db.delete(stock)
        
        # Annulla l'ordine
        order.is_cancelled = True
        order.cancelled_date = datetime.utcnow()
        
        # LOGGING: Registra l'annullamento dell'ordine
        logger = LoggingService(db)
        
        # Prepara dettagli prodotti per log leggibile
        restored_products_summary = []
        for item in inventory_restored:
            restored_products_summary.append(f"{item['quantity']}x {item['product_sku']} → {item['restored_to']}")
        
        # Logga ogni prodotto ripristinato separatamente per visibilità nelle colonne SKU/Ubicazioni
        for item in inventory_restored:
            logger.log_operation(
                operation_type=OperationType.ORDINE_ANNULLATO,
                operation_category=OperationCategory.MANUAL,
                status=OperationStatus.SUCCESS,
                product_sku=item['product_sku'],  # SKU del prodotto ripristinato
                location_from=None,  # Da OutgoingStock (non ha ubicazione fisica)
                location_to=item['restored_to'],  # Ripristinato a TERRA
                quantity=item['quantity'],  # Quantità ripristinata
                user_id="cancel_user",  # TODO: Sostituire con sistema auth reale
                file_name=f"ORDER_{order.order_number}",  # Numero ordine nella colonna Dettagli
                details={
                    'order_number': order.order_number,  # Numero ordine nei dettagli JSON
                    'customer_name': order.customer_name,
                    'cancelled_date': order.cancelled_date.isoformat(),
                    'operation_description': f"Annullamento ordine {order.order_number}: ripristinato {item['quantity']}x {item['product_sku']} in {item['restored_to']} per riposizionamento",
                    'cancel_type': 'manual_cancel',
                    'total_order_items': sum(restored['quantity'] for restored in inventory_restored),
                    'restoration_reason': 'order_cancellation'
                },
                api_endpoint=f"/orders/{order_id}/cancel"
            )
        
        db.commit()
        
        return {
            "message": f"Order {order.order_number} cancelled successfully",
            "released_items": released_items,
            "inventory_restored": inventory_restored,
            "note": "I prodotti sono stati automaticamente ripristinati in ubicazione TERRA in attesa di riposizionamento manuale da parte degli operatori"
        }
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error cancelling order: {str(e)}")

@router.delete("/{order_id}/unarchive")
def unarchive_order(order_id: int, db: Session = Depends(get_db)):
    """Rimuove un ordine dall'archivio (riporta nella lista normale)."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if not order.is_archived:
        raise HTTPException(status_code=400, detail="Order is not archived")

    # Rimuovi dall'archivio
    order.is_archived = False
    order.archived_date = None

    try:
        db.commit()
        return {"message": f"Order {order.order_number} removed from archive successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error unarchiving order: {str(e)}")

@router.put("/{order_id}/update-carrier")
def update_carrier_name(
    order_id: int,
    request: schemas.UpdateCarrierRequest,
    db: Session = Depends(get_db)
):
    """Modifica il vettore di un ordine archiviato."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    if not order.is_archived:
        raise HTTPException(status_code=400, detail="Solo gli ordini archiviati possono avere il vettore modificato")
    order.carrier_name = request.carrier_name
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore salvataggio vettore: {str(e)}")
    return {"success": True, "carrier_name": order.carrier_name, "order_number": order.order_number}


@router.put("/{order_id}/update-ddt")
def update_ddt_number(
    order_id: int,
    request: schemas.UpdateDdtNumberRequest,
    db: Session = Depends(get_db)
):
    """Modifica il numero DDT di un ordine archiviato."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    if not order.is_archived:
        raise HTTPException(status_code=400, detail="Solo gli ordini archiviati possono avere il DDT modificato")
    order.ddt_number = request.ddt_number
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore salvataggio DDT: {str(e)}")
    return {"success": True, "ddt_number": order.ddt_number, "order_number": order.order_number}


@router.put("/{order_id}/update-plt")
def update_plt_number(
    order_id: int,
    request: schemas.UpdatePltNumberRequest,
    db: Session = Depends(get_db)
):
    """Modifica il numero di PLT di un ordine archiviato."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    if not order.is_archived:
        raise HTTPException(status_code=400, detail="Solo gli ordini archiviati possono avere il PLT modificato")

    order.plt_number = request.plt_number
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore salvataggio PLT: {str(e)}")

    return {"success": True, "plt_number": order.plt_number, "order_number": order.order_number}


@router.put("/{order_id}/update-archived-date")
def update_archived_date(
    order_id: int,
    request: schemas.UpdateArchivedDateRequest,
    db: Session = Depends(get_db)
):
    """
    Modifica la data di archiviazione di un ordine archiviato.
    Utile per correggere la data quando l'ordine è stato consegnato fisicamente
    in un giorno diverso dalla registrazione nel sistema.
    """
    # LOGGING: Inizializza logger
    logger = LoggingService(db)

    try:
        # Recupera ordine
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # Log stato iniziale
        old_archived_date = order.archived_date
        print(f"📅 UPDATE ARCHIVED DATE START: Order {order.order_number} (ID: {order_id}) - current_date={old_archived_date}")

        # Validazione: ordine deve essere archiviato
        if not order.is_archived:
            error_msg = f"Order {order.order_number} is not archived"
            print(f"❌ UPDATE ARCHIVED DATE FAILED: {error_msg}")

            logger.log_error(
                operation_type="UPDATE_ARCHIVED_DATE_FAILED",
                error=error_msg,
                operation_category=OperationCategory.MANUAL,
                file_name=f"ORDER_{order.order_number}",
                details={
                    'order_id': order_id,
                    'order_number': order.order_number,
                    'is_archived': order.is_archived,
                    'error_reason': 'order_not_archived',
                    'operation_description': f"Tentativo fallito di modificare data archiviazione per ordine {order.order_number}: ordine non archiviato"
                },
                api_endpoint=f"/orders/{order_id}/update-archived-date"
            )

            raise HTTPException(
                status_code=400,
                detail=f"L'ordine {order.order_number} non è archiviato. Solo gli ordini archiviati possono avere la data modificata."
            )

        new_date = request.new_archived_date

        # Normalizza date a naive datetime per confronti
        new_date_naive = new_date.replace(tzinfo=None) if new_date.tzinfo else new_date
        order_date_naive = order.order_date.replace(tzinfo=None) if (order.order_date and order.order_date.tzinfo) else order.order_date
        old_archived_date_naive = old_archived_date.replace(tzinfo=None) if (old_archived_date and old_archived_date.tzinfo) else old_archived_date

        # Validazione: data non può essere antecedente alla data ordine (confronta solo gg/mm/aaaa, ignora ore)
        if order_date_naive and new_date_naive.date() < order_date_naive.date():
            error_msg = f"New archived date ({new_date_naive.date()}) cannot be earlier than order date ({order_date_naive.date()})"
            print(f"❌ UPDATE ARCHIVED DATE FAILED: {error_msg}")

            logger.log_error(
                operation_type="UPDATE_ARCHIVED_DATE_FAILED",
                error=error_msg,
                operation_category=OperationCategory.MANUAL,
                file_name=f"ORDER_{order.order_number}",
                details={
                    'order_id': order_id,
                    'order_number': order.order_number,
                    'order_date': order.order_date.isoformat() if order.order_date else None,
                    'new_archived_date': new_date.isoformat(),
                    'error_reason': 'date_before_order_date',
                    'operation_description': f"Tentativo fallito di modificare data archiviazione: data antecedente alla data ordine"
                },
                api_endpoint=f"/orders/{order_id}/update-archived-date"
            )

            raise HTTPException(
                status_code=400,
                detail=f"La data di archiviazione ({new_date_naive.strftime('%d/%m/%Y')}) non può essere antecedente alla data ordine ({order_date_naive.strftime('%d/%m/%Y')})"
            )

        # Validazione: data deve essere diversa dalla corrente
        if old_archived_date_naive and old_archived_date_naive == new_date_naive:
            print(f"⚠️  UPDATE ARCHIVED DATE SKIP: Date unchanged for order {order.order_number}")
            return {
                "message": "La data di archiviazione è già quella specificata",
                "order_number": order.order_number,
                "archived_date": old_archived_date.isoformat() if old_archived_date else None
            }

        # Aggiorna la data (usa versione naive per consistenza con il database)
        order.archived_date = new_date_naive
        print(f"✅ UPDATE ARCHIVED DATE VALIDATION PASSED: Order {order.order_number} - updating from {old_archived_date} to {new_date_naive}")

        # COMMIT CON GESTIONE ERRORI
        try:
            print(f"💾 UPDATE ARCHIVED DATE COMMIT: Attempting database commit for order {order.order_number}")
            db.commit()
            print(f"✅ UPDATE ARCHIVED DATE SUCCESS: Order {order.order_number} - archived_date updated to {new_date_naive}")

            # Log operazione di successo
            logger.log_operation(
                operation_type="ARCHIVED_DATE_UPDATED",
                operation_category=OperationCategory.MANUAL,
                status=OperationStatus.SUCCESS,
                file_name=f"ORDER_{order.order_number}",
                details={
                    'order_id': order_id,
                    'order_number': order.order_number,
                    'customer_name': order.customer_name,
                    'old_archived_date': old_archived_date.isoformat() if old_archived_date else None,
                    'new_archived_date': new_date_naive.isoformat(),
                    'operation_description': f"Data archiviazione ordine {order.order_number} modificata da {old_archived_date.strftime('%Y-%m-%d %H:%M:%S') if old_archived_date else 'N/A'} a {new_date_naive.strftime('%Y-%m-%d %H:%M:%S')}"
                },
                api_endpoint=f"/orders/{order_id}/update-archived-date"
            )

            return {
                "message": f"Data di archiviazione aggiornata con successo per ordine {order.order_number}",
                "order_number": order.order_number,
                "old_archived_date": old_archived_date.isoformat() if old_archived_date else None,
                "new_archived_date": new_date_naive.isoformat()
            }

        except Exception as commit_error:
            # Rollback esplicito
            db.rollback()

            error_msg = f"Database commit failed for updating archived date: {str(commit_error)}"
            print(f"❌ UPDATE ARCHIVED DATE COMMIT ERROR: {error_msg}")

            logger.log_error(
                operation_type="UPDATE_ARCHIVED_DATE_COMMIT_FAILED",
                error=commit_error,
                operation_category=OperationCategory.MANUAL,
                file_name=f"ORDER_{order.order_number}",
                details={
                    'order_id': order_id,
                    'order_number': order.order_number,
                    'error_type': type(commit_error).__name__,
                    'error_message': str(commit_error),
                    'operation_description': f"Errore durante modifica data archiviazione ordine {order.order_number}"
                },
                api_endpoint=f"/orders/{order_id}/update-archived-date"
            )

            raise HTTPException(
                status_code=500,
                detail=f"Errore durante l'aggiornamento della data di archiviazione: {str(commit_error)}"
            )

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        db.rollback()

        error_msg = f"Unexpected error updating archived date for order ID {order_id}: {str(e)}"
        print(f"❌ UPDATE ARCHIVED DATE UNEXPECTED ERROR: {error_msg}")

        logger.log_error(
            operation_type="UPDATE_ARCHIVED_DATE_UNEXPECTED_ERROR",
            error=e,
            operation_category=OperationCategory.MANUAL,
            details={
                'order_id': order_id,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'operation_description': f"Errore imprevisto durante modifica data archiviazione ordine ID {order_id}"
            },
            api_endpoint=f"/orders/{order_id}/update-archived-date"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Errore durante l'aggiornamento della data: {str(e)}"
        )

# --- Sistema Import Automatico da Cartella ---

@router.post("/auto-import/configure-folder")
def configure_auto_import_folder(request: dict, db: Session = Depends(get_db)):
    """Configura il percorso della cartella per l'import automatico."""
    try:
        folder_path = request.get("folder_path")
        if not folder_path:
            raise HTTPException(status_code=400, detail="folder_path è richiesto")
        
        # Valida che la cartella esista
        if not os.path.exists(folder_path):
            raise HTTPException(status_code=400, detail=f"La cartella {folder_path} non esiste")
        
        if not os.path.isdir(folder_path):
            raise HTTPException(status_code=400, detail=f"Il percorso {folder_path} non è una cartella")
        
        # Crea le sottocartelle se non esistono
        processed_folder = os.path.join(folder_path, "processati")
        error_folder = os.path.join(folder_path, "errori")
        
        os.makedirs(processed_folder, exist_ok=True)
        os.makedirs(error_folder, exist_ok=True)
        
        # Salva la configurazione nel database
        setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "auto_import_folder").first()
        if setting:
            setting.value = folder_path
            setting.updated_at = datetime.utcnow()
        else:
            setting = models.SystemSetting(
                key="auto_import_folder",
                value=folder_path,
                description="Cartella monitorata per import automatico ordini"
            )
            db.add(setting)
        
        db.commit()
        
        return {
            "message": "Cartella configurata con successo",
            "folder_path": folder_path,
            "processed_folder": processed_folder,
            "error_folder": error_folder
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore nella configurazione: {str(e)}")

@router.get("/auto-import/folder-config")
def get_auto_import_config(db: Session = Depends(get_db)):
    """Recupera la configurazione attuale della cartella di import."""
    setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "auto_import_folder").first()
    
    if not setting:
        return {"configured": False, "folder_path": None}
    
    folder_exists = os.path.exists(setting.value) and os.path.isdir(setting.value)
    
    return {
        "configured": True,
        "folder_path": setting.value,
        "folder_exists": folder_exists,
        "last_updated": setting.updated_at.isoformat() if setting.updated_at else None
    }

@router.post("/auto-import/from-folder")
def auto_import_from_folder(db: Session = Depends(get_db)):
    """Esegue l'import automatico di tutti i file dalla cartella configurata."""
    try:
        # Recupera la configurazione della cartella
        setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "auto_import_folder").first()
        if not setting:
            raise HTTPException(status_code=400, detail="Cartella di import non configurata")
        
        folder_path = setting.value
        if not os.path.exists(folder_path):
            raise HTTPException(status_code=400, detail=f"Cartella {folder_path} non trovata")
        
        processed_folder = os.path.join(folder_path, "processati")
        error_folder = os.path.join(folder_path, "errori")
        
        # Assicurati che le cartelle esistano
        os.makedirs(processed_folder, exist_ok=True)
        os.makedirs(error_folder, exist_ok=True)
        
        # Cerca file TXT e CSV nella cartella
        supported_extensions = ['.txt', '.csv']
        files_found = []
        
        for file_path in Path(folder_path).iterdir():
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                files_found.append(file_path)
        
        if not files_found:
            return {
                "message": "Nessun file da processare",
                "files_processed": 0,
                "files_with_errors": 0,
                "details": []
            }
        
        # Processa ogni file
        results = []
        files_processed = 0
        files_with_errors = 0
        
        for file_path in files_found:
            try:
                # Leggi il file con gestione BOM e caratteri invisibili
                file_content = _read_file_with_bom_handling(file_path)
                
                # Processa il file usando la logica esistente
                result = _process_orders_file_content(file_content, str(file_path), db)
                
                if result["success"]:
                    # Sposta il file nella cartella processati
                    destination = os.path.join(processed_folder, file_path.name)
                    shutil.move(str(file_path), destination)
                    files_processed += 1
                    results.append({
                        "file": file_path.name,
                        "status": "processed",
                        "message": result["message"],
                        "orders_created": result.get("orders_created", 0),
                        "orders_details": result.get("orders_details", []),
                        "general_errors": result.get("general_errors", [])
                    })
                else:
                    # Sposta il file nella cartella errori
                    destination = os.path.join(error_folder, file_path.name)
                    shutil.move(str(file_path), destination)
                    files_with_errors += 1
                    results.append({
                        "file": file_path.name,
                        "status": "error",
                        "message": result["message"],
                        "errors": result.get("errors", [])
                    })
                    
            except Exception as file_error:
                # Sposta il file nella cartella errori
                try:
                    destination = os.path.join(error_folder, file_path.name)
                    shutil.move(str(file_path), destination)
                except:
                    pass  # Se non riesce a spostare, continua
                
                files_with_errors += 1
                results.append({
                    "file": file_path.name,
                    "status": "error",
                    "message": f"Errore nel processamento del file: {str(file_error)}",
                    "errors": [str(file_error)]
                })
        
        return {
            "message": f"Import completato: {files_processed} file processati, {files_with_errors} errori",
            "files_processed": files_processed,
            "files_with_errors": files_with_errors,
            "details": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'import automatico: {str(e)}")

# --- Funzioni di supporto per import automatico ---

def _read_file_with_bom_handling(file_path: Path) -> str:
    """Legge un file gestendo BOM e caratteri invisibili."""
    encodings_to_try = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
    
    for encoding in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            
            # Rimuovi caratteri invisibili comuni
            content = content.replace('\ufeff', '')  # BOM UTF-8
            content = content.replace('\u200b', '')  # Zero-width space
            content = content.replace('\u00a0', ' ')  # Non-breaking space
            
            return content.strip()
            
        except UnicodeDecodeError:
            continue
    
    raise ValueError(f"Impossibile leggere il file {file_path.name} con nessuna codifica supportata")

def _process_orders_file_content(content: str, filename: str, db: Session) -> dict:
    """Processa il contenuto di un file ordini e crea gli ordini nel database."""
    try:
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        if not lines:
            return {"success": False, "message": "File vuoto", "errors": ["Il file non contiene dati"]}
        
        orders_data = defaultdict(lambda: {"customer_name": "", "lines": [], "warnings": []})
        errors = []
        line_number = 0
        
        for line in lines:
            line_number += 1
            
            # Supporta sia CSV che formato separato da virgole
            parts = [part.strip() for part in line.split(',')]
            
            if len(parts) < 4:
                errors.append(f"Riga {line_number}: formato non valido (necessari almeno 4 campi)")
                continue
            
            order_number, customer_name, product_sku, quantity_str = parts[:4]
            
            try:
                quantity = int(quantity_str)
                if quantity <= 0:
                    errors.append(f"Riga {line_number}: quantità deve essere maggiore di 0")
                    continue
            except ValueError:
                errors.append(f"Riga {line_number}: quantità non valida '{quantity_str}'")
                continue
            
            # Verifica che il prodotto esista
            product = db.query(models.Product).filter(models.Product.sku == product_sku).first()
            if not product:
                orders_data[order_number]["warnings"].append(f"Prodotto '{product_sku}' non trovato in anagrafica")
                errors.append(f"Riga {line_number}: prodotto '{product_sku}' non trovato")
                continue
            
            # Aggiungi ai dati dell'ordine
            orders_data[order_number]["customer_name"] = customer_name
            orders_data[order_number]["lines"].append({
                "product_sku": product_sku,
                "requested_quantity": quantity
            })
        
        if errors and len(orders_data) == 0:
            return {"success": False, "message": "Nessun ordine valido trovato", "errors": errors}
        
        # Crea gli ordini nel database
        orders_created = 0
        
        for order_number, order_data in orders_data.items():
            try:
                # Verifica se l'ordine esiste già
                existing_order = db.query(models.Order).filter(models.Order.order_number == order_number).first()
                if existing_order:
                    orders_data[order_number]["warnings"].append(f"Ordine già esistente nel database")
                    errors.append(f"Ordine {order_number} già esistente")
                    continue
                
                # Crea il nuovo ordine
                new_order = models.Order(
                    order_number=order_number,
                    customer_name=order_data["customer_name"],
                    order_date=datetime.utcnow()
                )
                db.add(new_order)
                db.flush()  # Per ottenere l'ID
                
                # Crea le righe d'ordine
                for line_data in order_data["lines"]:
                    order_line = models.OrderLine(
                        order_id=new_order.id,
                        product_sku=line_data["product_sku"],
                        requested_quantity=line_data["requested_quantity"]
                    )
                    db.add(order_line)
                
                orders_created += 1
                
            except Exception as order_error:
                errors.append(f"Errore creazione ordine {order_number}: {str(order_error)}")
                db.rollback()
                continue
        
        # LOGGING: Registra l'import automatico da cartella
        if orders_created > 0:
            logger = LoggingService(db)
            
            # Logga ogni prodotto di ogni ordine creato automaticamente
            for order_number, order_data in orders_data.items():
                created_order = db.query(models.Order).filter(models.Order.order_number == order_number).first()
                if created_order:  # Solo se l'ordine è stato creato con successo
                    for line_data in order_data["lines"]:
                        logger.log_operation(
                            operation_type=OperationType.ORDINE_CREATO,
                            operation_category=OperationCategory.SYSTEM,  # Automatico
                            status=OperationStatus.SUCCESS,
                            product_sku=line_data["product_sku"],  # SKU del prodotto importato
                            quantity=line_data["requested_quantity"],  # Quantità richiesta
                            user_id="auto_import_system",
                            file_name=f"ORDER_{order_number}",  # Numero ordine nella colonna Dettagli
                            details={
                                'order_number': order_number,  # Numero ordine nei dettagli JSON
                                'customer_name': order_data["customer_name"],
                                'creation_method': 'auto_import',
                                'source_file': filename,
                                'operation_description': f"Import automatico: creato ordine {order_number}, aggiunto {line_data['requested_quantity']}x {line_data['product_sku']} per cliente {order_data['customer_name']}",
                                'auto_import_stats': {
                                    'orders_created': orders_created,
                                    'source_filename': filename
                                }
                            },
                            api_endpoint="/orders/auto-import/from-folder"
                        )
        
        if orders_created > 0:
            db.commit()
            message = f"Import completato: {orders_created} ordini creati da {filename}"
            if errors:
                message += f" (con {len(errors)} avvisi)"
            
            # Crea lista dettagliata degli ordini creati con i loro avvisi
            orders_details = []
            for order_number, order_data in orders_data.items():
                if order_number in [order_number for order_number, order_data in orders_data.items() if len(order_data.get("lines", [])) > 0]:
                    # Controlla se questo ordine è stato effettivamente creato
                    created_order = db.query(models.Order).filter(models.Order.order_number == order_number).first()
                    if created_order:
                        orders_details.append({
                            "order_number": order_number,
                            "customer_name": order_data["customer_name"],
                            "products_count": len(order_data["lines"]),
                            "warnings": order_data.get("warnings", [])
                        })
            
            return {
                "success": True, 
                "message": f"{orders_created} ordini creati",
                "orders_created": orders_created,
                "orders_details": orders_details,
                "general_errors": errors
            }
        else:
            db.rollback()
            return {"success": False, "message": "Nessun ordine creato", "errors": errors}
            
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Errore durante il processamento: {str(e)}", "errors": [str(e)]}

# --- Endpoint per Cancellazione Completa Ordini ---

@router.delete("/{order_id}/delete")
def delete_order_completely(order_id: int, db: Session = Depends(get_db)):
    """Cancella completamente un ordine che non ha ancora iniziato il picking."""
    try:
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Verifica che l'ordine non abbia picking iniziato
        has_picking = False
        for line in order.lines:
            if line.picked_quantity > 0:
                has_picking = True
                break
        
        if has_picking:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete order: picking has already started"
            )
        
        if order.is_completed:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete order: order is already completed"
            )
        
        if order.is_archived:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete order: order is archived"
            )
        
        # Verifica se ci sono prenotazioni attive (con import diretto)
        try:
            from wms_app.models.reservations import InventoryReservation
            active_reservations = db.query(InventoryReservation).filter(
                InventoryReservation.order_id == order.order_number,
                InventoryReservation.status == "active"
            ).count()
            
            if active_reservations > 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete order: active reservations exist. Cancel the order first to release reservations."
                )
        except ImportError:
            # Se il modello non esiste, continua
            pass
        
        # Verifica se ci sono OutgoingStock associati
        try:
            outgoing_stocks = db.query(models.OutgoingStock).join(models.OrderLine).filter(
                models.OrderLine.order_id == order.id
            ).count()
            
            if outgoing_stocks > 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete order: outgoing stock exists. Cancel the order first to release stock."
                )
        except Exception:
            # Se ci sono problemi con OutgoingStock, continua
            pass
        
        order_number = order.order_number
        
        # Elimina le righe dell'ordine
        db.query(models.OrderLine).filter(models.OrderLine.order_id == order.id).delete()
        
        # Elimina l'ordine
        db.delete(order)
        
        db.commit()
        
        return {
            "message": f"Order {order_number} deleted successfully",
            "order_number": order_number,
            "order_id": order_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting order: {str(e)}")

# === ENDPOINT PER PICKING IN TEMPO REALE ===

@router.post("/real-time-picking/scan-product")
async def scan_product_real_time(
    request_data: dict,
    db: Session = Depends(get_db)
):
    """
    Endpoint per processare la scansione di un prodotto durante il picking in tempo reale.
    Valida l'EAN code, verifica la corrispondenza con lo SKU richiesto e scala le giacenze.
    """
    try:
        order_id = request_data.get("order_id")
        location_name = request_data.get("location_name", "").upper()
        scanned_code = request_data.get("scanned_code", "")
        expected_sku = request_data.get("expected_sku", "")
        quantity = request_data.get("quantity", 1)
        
        if not all([order_id, location_name, scanned_code, expected_sku]):
            raise HTTPException(status_code=400, detail="Missing required parameters")
        
        # 1. Verifica che l'ordine esista e non sia completato
        order = db.query(models.Order).filter(
            models.Order.id == order_id,
            models.Order.is_completed == False
        ).first()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found or already completed")
        
        # 2. Trova la riga dell'ordine corrispondente
        order_line = db.query(models.OrderLine).filter(
            models.OrderLine.order_id == order_id,
            models.OrderLine.product_sku == expected_sku
        ).first()
        
        if not order_line:
            # Log errore prodotto non nell'ordine
            logger = LoggingService(db)
            logger.log_error(
                operation_type=OperationType.PRELIEVO_TEMPO_REALE,
                error=f"Product {expected_sku} not found in order {order.order_number}",
                operation_category=OperationCategory.PICKING,
                product_sku=expected_sku,
                file_name=f"ORDER_{order.order_number}",
                details={
                    'order_number': order.order_number,
                    'expected_sku': expected_sku,
                    'scanned_code': scanned_code,
                    'location_name': location_name,
                    'error_reason': 'product_not_in_order',
                    'operation_description': f"Errore picking tempo reale ordine {order.order_number}: prodotto {expected_sku} non presente nell'ordine"
                },
                api_endpoint="/orders/real-time-picking/scan-product"
            )
            return {
                "success": False,
                "message": f"Prodotto {expected_sku} non trovato in questo ordine"
            }
        
        # 3. Controlla se c'è ancora quantità da prelevare
        remaining_to_pick = order_line.requested_quantity - order_line.picked_quantity
        if remaining_to_pick <= 0:
            return {
                "success": False,
                "message": f"Prodotto {expected_sku} già completamente prelevato"
            }
        
        # 4. Validazione barcode: controlla se è un EAN code o direttamente lo SKU
        product_sku = None
        
        # Prima prova a vedere se il codice scansionato è direttamente lo SKU
        product = db.query(models.Product).filter(models.Product.sku == scanned_code).first()
        if product:
            product_sku = product.sku
        else:
            # Altrimenti cerca negli EAN codes
            ean_code = db.query(models.EanCode).filter(models.EanCode.ean == scanned_code).first()
            if ean_code:
                product_sku = ean_code.product_sku
        
        if not product_sku:
            # Log errore barcode non riconosciuto
            logger = LoggingService(db)
            logger.log_error(
                operation_type=OperationType.PRELIEVO_TEMPO_REALE,
                error=f"Barcode '{scanned_code}' not recognized",
                operation_category=OperationCategory.PICKING,
                product_sku=expected_sku,
                location_from=location_name,
                file_name=f"ORDER_{order.order_number}",
                details={
                    'order_number': order.order_number,
                    'expected_sku': expected_sku,
                    'scanned_code': scanned_code,
                    'location_name': location_name,
                    'error_reason': 'barcode_not_recognized',
                    'operation_description': f"Errore picking tempo reale ordine {order.order_number}: barcode '{scanned_code}' non riconosciuto"
                },
                api_endpoint="/orders/real-time-picking/scan-product"
            )
            return {
                "success": False,
                "message": f"Codice scansionato '{scanned_code}' non riconosciuto"
            }
        
        # 5. Verifica che il prodotto scansionato corrisponda a quello richiesto
        if product_sku != expected_sku:
            return {
                "success": False,
                "message": f"Prodotto errato! Richiesto: {expected_sku}, Scansionato: {product_sku}"
            }
        
        # 6. Verifica disponibilità nella specifica ubicazione
        inventory_item = db.query(models.Inventory).filter(
            models.Inventory.product_sku == product_sku,
            models.Inventory.location_name == location_name,
            models.Inventory.quantity > 0
        ).first()
        
        if not inventory_item:
            return {
                "success": False,
                "message": f"Prodotto {product_sku} non disponibile nell'ubicazione {location_name}"
            }
        
        # 7. Determina la quantità effettiva da prelevare
        actual_quantity = min(quantity, inventory_item.quantity, remaining_to_pick)
        
        # 8. Scala la giacenza in tempo reale
        inventory_item.quantity -= actual_quantity
        
        # 9. Se l'ubicazione rimane vuota, elimina il record di inventario
        if inventory_item.quantity <= 0:
            db.delete(inventory_item)
        
        # 10. Aggiorna la quantità prelevata nell'ordine
        order_line.picked_quantity += actual_quantity
        
        # 11. Sposta in OutgoingStock (come nel picking manuale)
        outgoing_item = db.query(models.OutgoingStock).filter(
            models.OutgoingStock.order_line_id == order_line.id,
            models.OutgoingStock.product_sku == product_sku
        ).first()

        if outgoing_item:
            outgoing_item.quantity += actual_quantity
        else:
            new_outgoing_item = models.OutgoingStock(
                order_line_id=order_line.id,
                product_sku=product_sku,
                quantity=actual_quantity
            )
            db.add(new_outgoing_item)

        # 11.5. NUOVO: Completa le prenotazioni relative a questo picking
        from wms_app.services.reservation_service import ReservationService
        from wms_app.models.reservations import InventoryReservation

        reservation_service = ReservationService(db)

        # Cerca prenotazioni attive per questo ordine/sku/location
        active_reservations = db.query(InventoryReservation).filter(
            and_(
                InventoryReservation.order_id == str(order.order_number),
                InventoryReservation.product_sku == product_sku,
                InventoryReservation.location_name == location_name,
                InventoryReservation.status == 'active'
            )
        ).all()

        # Completa le prenotazioni proporzionalmente alla quantità prelevata
        remaining_to_release = actual_quantity
        for reservation in active_reservations:
            if remaining_to_release <= 0:
                break

            # Quantità da rilasciare per questa prenotazione
            to_release = min(remaining_to_release, reservation.reserved_quantity)

            # Marca prenotazione come completata
            reservation_service.complete_reservation(reservation.id, to_release)

            remaining_to_release -= to_release

        # 12. LOGGING: Registra l'operazione di picking in tempo reale
        logger = LoggingService(db)
        logger.log_operation(
            operation_type=OperationType.PRELIEVO_TEMPO_REALE,
            operation_category=OperationCategory.PICKING,
            status=OperationStatus.SUCCESS,
            product_sku=product_sku,
            location_from=location_name,
            location_to=None,  # Picking: scala da inventario
            quantity=actual_quantity,
            user_id="realtime_picker",  # TODO: Sostituire con sistema auth reale
            details={
                'order_number': order.order_number,
                'order_id': order_id,
                'scanned_code': scanned_code,
                'expected_sku': expected_sku,
                'operation_description': f"Picking tempo reale: {product_sku} ({actual_quantity} pz) da {location_name} per ordine {order.order_number}",
                'picking_type': 'real_time_picking',
                'barcode_validation': 'passed',
                'customer_name': order.customer_name,
                'remaining_in_location': inventory_item.quantity if inventory_item.quantity > 0 else 0,
                'remaining_to_pick': order_line.requested_quantity - order_line.picked_quantity - actual_quantity
            },
            api_endpoint="/orders/real-time-picking/scan-product"
        )
        
        # 13. Commit delle modifiche
        db.commit()
        
        # 14. Prepara la risposta di successo
        return {
            "success": True,
            "message": f"Prodotto prelevato con successo",
            "product_sku": product_sku,
            "location_name": location_name,
            "quantity_picked": actual_quantity,
            "remaining_in_location": inventory_item.quantity if inventory_item.quantity > 0 else 0,
            "remaining_to_pick": order_line.requested_quantity - order_line.picked_quantity,
            "order_line_completed": (order_line.requested_quantity - order_line.picked_quantity) <= 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing real-time picking: {str(e)}")

# === ENDPOINT IMPORT ORDINI DA EXCEL ===

@router.post("/parse-excel-orders")
async def parse_excel_orders(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Parsing e validazione di ordini da file Excel (.xlsx).
    Formato: Colonna B = N ordine, T = Cliente, Q = SKU, S = Quantità
    
    Ritorna un recap dettagliato per conferma dell'utente prima del commit.
    """
    try:
        # Verifica che sia un file Excel
        if not file.filename.lower().endswith('.xlsx'):
            raise HTTPException(status_code=400, detail="Solo file Excel (.xlsx) sono supportati")
        
        # Leggi il contenuto del file
        content = await file.read()
        
        # Importa openpyxl dinamicamente
        try:
            from openpyxl import load_workbook
            from io import BytesIO
        except ImportError as e:
            import sys
            raise HTTPException(status_code=500, detail=f"openpyxl non disponibile. Python: {sys.executable}, Error: {str(e)}")
        
        # Carica il workbook Excel
        try:
            workbook = load_workbook(BytesIO(content), data_only=True)
            worksheet = workbook.active
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Errore lettura file Excel: {str(e)}")
        
        # Parsing dei dati dalle colonne identificate
        orders_data = defaultdict(lambda: {"customer_name": "", "lines": defaultdict(int), "errors": [], "warnings": []})
        parse_errors = []
        line_number = 1  # Riga 1 = header
        
        # Leggi gli headers per identificare le colonne corrette
        headers = []
        for row in worksheet.iter_rows(min_row=1, max_row=1, values_only=True):
            headers = [str(cell).strip() if cell is not None else '' for cell in row]
            break
        
        # Trova gli indici delle colonne che ci interessano
        column_mapping = {}
        target_headers = {
            'order_number': 'CODICE ORDINE MASTER',
            'customer_name': 'RAGIONE SOCIALE DESTINATARIO', 
            'sku': 'CODICE PADRE PRODOTTO',
            'quantity': 'Q PRODOTTO'
        }
        
        for key, target_header in target_headers.items():
            try:
                index = headers.index(target_header)
                column_mapping[key] = index
# Debug rimosso per produzione
            except ValueError:
                parse_errors.append({
                    "line": 1,
                    "message": f"Colonna '{target_header}' non trovata negli headers",
                    "field": "excel_headers",
                    "value": f"Headers disponibili: {', '.join(headers[:10])}{'...' if len(headers) > 10 else ''}"
                })
        
        # Verifica che tutte le colonne siano state trovate
        if len(column_mapping) != 4:
            missing = set(target_headers.keys()) - set(column_mapping.keys())
            raise HTTPException(
                status_code=400, 
                detail=f"Colonne mancanti nel file Excel: {', '.join(target_headers[k] for k in missing)}"
            )
        
        # Itera attraverso tutte le righe (saltando la prima che è l'header)
        for row in worksheet.iter_rows(min_row=2, values_only=True):
            line_number += 1
            
            try:
                # Estrae valori dalle colonne identificate dinamicamente
                order_number = row[column_mapping['order_number']] if len(row) > column_mapping['order_number'] and row[column_mapping['order_number']] is not None else None
                sku = row[column_mapping['sku']] if len(row) > column_mapping['sku'] and row[column_mapping['sku']] is not None else None
                quantity_raw = row[column_mapping['quantity']] if len(row) > column_mapping['quantity'] and row[column_mapping['quantity']] is not None else None
                customer_name = row[column_mapping['customer_name']] if len(row) > column_mapping['customer_name'] and row[column_mapping['customer_name']] is not None else None
                
            except Exception as e:
                parse_errors.append({
                    "line": line_number,
                    "message": f"Errore lettura riga Excel: {str(e)}",
                    "field": "excel_structure",
                    "value": f"Row length: {len(row) if row else 'None'}"
                })
                continue
            
            # Salta righe completamente vuote
            if all(v is None or str(v).strip() == '' for v in [order_number, sku, quantity_raw, customer_name]):
                continue
            
            # Validazioni base
            validation_errors = []
            
            if not order_number or str(order_number).strip() == '':
                validation_errors.append(f"Numero ordine mancante (colonna B)")
            else:
                order_number = str(order_number).strip()
            
            if not customer_name or str(customer_name).strip() == '':
                validation_errors.append(f"Nome cliente mancante (colonna T)")
            else:
                customer_name = str(customer_name).strip()
            
            if not sku or str(sku).strip() == '':
                validation_errors.append(f"SKU prodotto mancante (colonna Q)")
            else:
                sku = str(sku).strip()
            
            # Validazione quantità
            try:
                if quantity_raw is None:
                    validation_errors.append(f"Quantità mancante (colonna S)")
                    quantity = 0
                else:
                    quantity = int(float(quantity_raw))  # Gestisce sia int che float da Excel
                    if quantity <= 0:
                        validation_errors.append(f"Quantità deve essere maggiore di 0")
            except (ValueError, TypeError):
                validation_errors.append(f"Quantità non valida: '{quantity_raw}' (colonna S)")
                quantity = 0
            
            # Se ci sono errori di validazione, registra e continua
            if validation_errors:
                parse_errors.extend([{
                    "line": line_number,
                    "message": error,
                    "field": "validation",
                    "value": f"B:{order_number}, Q:{sku}, S:{quantity_raw}, T:{customer_name}"
                } for error in validation_errors])
                continue
            
            # Verifica che il prodotto esista nel database
            product = db.query(models.Product).filter(models.Product.sku == sku).first()
            if not product:
                orders_data[order_number]["errors"].append(f"Riga {line_number}: SKU '{sku}' non trovato in anagrafica")
                parse_errors.append({
                    "line": line_number,
                    "message": f"SKU '{sku}' non trovato in anagrafica",
                    "field": "sku",
                    "value": sku
                })
                continue
            
            # Verifica ordine duplicato esistente nel database
            existing_order = db.query(models.Order).filter(models.Order.order_number == order_number).first()
            if existing_order:
                orders_data[order_number]["warnings"].append(f"Ordine '{order_number}' già esistente nel database")
            
            # Aggiungi/aggiorna i dati dell'ordine
            orders_data[order_number]["customer_name"] = customer_name
            
            # Consolidamento automatico per SKU duplicati
            if sku in orders_data[order_number]["lines"]:
                old_quantity = orders_data[order_number]["lines"][sku]
                orders_data[order_number]["lines"][sku] += quantity
                orders_data[order_number]["warnings"].append(
                    f"SKU '{sku}' consolidato: {old_quantity} + {quantity} = {orders_data[order_number]['lines'][sku]}"
                )
            else:
                orders_data[order_number]["lines"][sku] = quantity
        
        # Prepara recap dettagliato
        recap_items = []
        total_orders = len(orders_data)
        total_lines = 0
        errors_count = len(parse_errors)
        warnings_count = 0
        
        # Genera recap items per ogni ordine e ogni prodotto
        for order_number, order_data in orders_data.items():
            warnings_count += len(order_data["warnings"])
            for sku, quantity in order_data["lines"].items():
                total_lines += 1
                
                # Trova il prodotto per descrizione
                product = db.query(models.Product).filter(models.Product.sku == sku).first()
                description = product.description if product else "Prodotto non trovato"
                
                # Determina lo stato
                status = "ok"
                if order_data["errors"]:
                    status = "error"
                elif order_data["warnings"]:
                    status = "warning"
                
                recap_items.append({
                    "line": len(recap_items) + 1,
                    "order_number": order_number,
                    "customer_name": order_data["customer_name"],
                    "sku": sku,
                    "description": description,
                    "quantity": quantity,
                    "status": status,
                    "consolidation_applied": any("consolidato" in w for w in order_data["warnings"])
                })
        
        # Crea gli ordini direttamente (senza recap)
        orders_created = 0
        orders_updated = 0
        orders_skipped = 0  # Ordini già presenti senza modifiche
        orders_created_list = []  # Lista numeri ordine creati
        orders_updated_list = []  # Lista numeri ordine aggiornati
        orders_skipped_list = []  # Lista numeri ordine già presenti
        logger = LoggingService(db)
        
        for order_number, order_data in orders_data.items():
            if order_data["errors"]:  # Salta ordini con errori
                continue
                
            # Controlla se l'ordine esiste già
            existing_order = db.query(models.Order).filter(models.Order.order_number == str(order_number)).first()
            is_new_order = existing_order is None
            
            if existing_order and not existing_order.is_completed:
                # Confronta righe esistenti con nuove per rilevare modifiche
                existing_lines = {line.product_sku: line.requested_quantity
                                  for line in existing_order.lines}
                new_lines = dict(order_data["lines"])

                # Verifica se l'ordine è identico (nessuna modifica necessaria)
                if existing_lines == new_lines:
                    orders_skipped += 1
                    orders_skipped_list.append(str(order_number))
                    continue  # Salta al prossimo ordine

                # Ci sono differenze, aggiorna l'ordine

                # 1. Rimuovi righe non più presenti nel file Excel
                for sku in existing_lines:
                    if sku not in new_lines:
                        db.query(models.OrderLine).filter(
                            models.OrderLine.order_id == existing_order.id,
                            models.OrderLine.product_sku == sku
                        ).delete()

                # 2. Aggiorna quantità esistenti o aggiungi nuove righe
                for sku, quantity in new_lines.items():
                    existing_line = db.query(models.OrderLine).filter(
                        models.OrderLine.order_id == existing_order.id,
                        models.OrderLine.product_sku == sku
                    ).first()

                    if existing_line:
                        # SOSTITUISCI la quantità (non sommare!)
                        existing_line.requested_quantity = quantity
                    else:
                        # Aggiungi nuova riga
                        new_line = models.OrderLine(
                            order_id=existing_order.id,
                            product_sku=sku,
                            requested_quantity=quantity
                        )
                        db.add(new_line)

                orders_updated += 1
                orders_updated_list.append(str(order_number))

            elif not existing_order:
                # Crea nuovo ordine
                new_order = models.Order(
                    order_number=str(order_number),
                    customer_name=order_data["customer_name"]
                )
                db.add(new_order)
                db.flush()  # Per ottenere l'ID
                
                # Crea le righe d'ordine
                for sku, quantity in order_data["lines"].items():
                    order_line = models.OrderLine(
                        order_id=new_order.id,
                        product_sku=sku,
                        requested_quantity=quantity
                    )
                    db.add(order_line)
                orders_created += 1
                orders_created_list.append(str(order_number))

            # LOGGING: Registra ogni prodotto dell'ordine corrente
            for sku, quantity in order_data["lines"].items():
                operation_type = OperationType.ORDINE_CREATO if is_new_order else OperationType.ORDINE_MODIFICATO
                
                logger.log_operation(
                    operation_type=operation_type,
                    operation_category=OperationCategory.FILE,
                    status=OperationStatus.SUCCESS,
                    product_sku=sku,
                    quantity=quantity,
                    user_id="excel_import_user",
                    file_name=f"ORDER_{order_number}",
                    details={
                        'order_number': str(order_number),
                        'customer_name': order_data["customer_name"],
                        'creation_method': 'excel_import_direct',
                        'source_file': file.filename,
                        'operation_description': f"Import Excel diretto: {operation_type.lower()} ordine {order_number}, aggiunto {quantity}x {sku} per cliente {order_data['customer_name']}",
                        'import_stats': {
                            'orders_created': orders_created,
                            'orders_updated': orders_updated,
                            'source_filename': file.filename
                        }
                    },
                    api_endpoint="/orders/parse-excel-orders"
                )
        
        db.commit()
        
        # Costruisci messaggio finale
        message_parts = []
        if orders_created > 0:
            message_parts.append(f"{orders_created} ordini creati")
        if orders_updated > 0:
            message_parts.append(f"{orders_updated} ordini aggiornati")
        if orders_skipped > 0:
            message_parts.append(f"{orders_skipped} ordini già presenti")
        if errors_count > 0:
            message_parts.append(f"{errors_count} errori saltati")

        message = "Import Excel completato: " + ", ".join(message_parts) if message_parts else "Nessuna operazione eseguita"

        # Risposta con risultato finale
        result = {
            "success": True,
            "file_name": file.filename,
            "orders_created": orders_created,
            "orders_updated": orders_updated,
            "orders_skipped": orders_skipped,
            "orders_created_list": orders_created_list,
            "orders_updated_list": orders_updated_list,
            "orders_skipped_list": orders_skipped_list,
            "summary": {
                "total_orders": total_orders,
                "total_lines": total_lines,
                "errors": errors_count,
                "warnings": warnings_count,
                "orders_preview": list(orders_data.keys())[:5]
            },
            "message": message
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante parsing Excel: {str(e)}")

@router.post("/commit-excel-orders")
async def commit_excel_orders(
    request_data: dict,
    db: Session = Depends(get_db)
):
    """
    Commit degli ordini Excel dopo validazione e conferma del recap.
    Riceve i dati modificati dall'utente tramite il recap overlay.
    """
    try:
        recap_items = request_data.get("recap_items", [])
        file_name = request_data.get("file_name", "excel_import.xlsx")
        
        if not recap_items:
            raise HTTPException(status_code=400, detail="Nessun dato da importare")
        
        # Riorganizza i dati per ordine
        orders_to_create = defaultdict(lambda: {"customer_name": "", "lines": []})
        
        for item in recap_items:
            if item.get("status") == "ok":  # Elabora solo elementi validi
                order_number = item["order_number"]
                orders_to_create[order_number]["customer_name"] = item["customer_name"]
                orders_to_create[order_number]["lines"].append({
                    "product_sku": item["sku"],
                    "requested_quantity": item["quantity"]
                })
        
        if not orders_to_create:
            raise HTTPException(status_code=400, detail="Nessun ordine valido da creare")
        
        # Crea gli ordini nel database con logging integrato
        orders_created_list = []  # Lista di numeri ordine creati
        orders_updated_list = []  # Lista di numeri ordine aggiornati
        logger = LoggingService(db)
        
        for order_number, order_data in orders_to_create.items():
            # Controlla se l'ordine esiste già
            existing_order = db.query(models.Order).filter(models.Order.order_number == order_number).first()
            is_new_order = existing_order is None
            
            if existing_order and not existing_order.is_completed:
                # Aggiorna ordine esistente
                for line_data in order_data["lines"]:
                    # Controlla se la riga prodotto esiste già
                    existing_line = db.query(models.OrderLine).filter(
                        models.OrderLine.order_id == existing_order.id,
                        models.OrderLine.product_sku == line_data["product_sku"]
                    ).first()
                    
                    if existing_line:
                        existing_line.requested_quantity += line_data["requested_quantity"]
                    else:
                        new_line = models.OrderLine(
                            order_id=existing_order.id,
                            product_sku=line_data["product_sku"],
                            requested_quantity=line_data["requested_quantity"]
                        )
                        db.add(new_line)
                orders_updated_list.append(order_number)
                
            elif not existing_order:
                # Crea nuovo ordine
                new_order = models.Order(
                    order_number=order_number,
                    customer_name=order_data["customer_name"]
                )
                db.add(new_order)
                db.flush()  # Per ottenere l'ID
                
                # Crea le righe d'ordine
                for line_data in order_data["lines"]:
                    order_line = models.OrderLine(
                        order_id=new_order.id,
                        product_sku=line_data["product_sku"],
                        requested_quantity=line_data["requested_quantity"]
                    )
                    db.add(order_line)
                orders_created_list.append(order_number)
            
            # LOGGING: Registra ogni prodotto dell'ordine corrente
            for line_data in order_data["lines"]:
                operation_type = OperationType.ORDINE_CREATO if is_new_order else OperationType.ORDINE_MODIFICATO
                
                logger.log_operation(
                    operation_type=operation_type,
                    operation_category=OperationCategory.FILE,
                    status=OperationStatus.SUCCESS,
                    product_sku=line_data["product_sku"],
                    quantity=line_data["requested_quantity"],
                    user_id="excel_import_user",
                    file_name=f"ORDER_{order_number}",
                    details={
                        'order_number': order_number,
                        'customer_name': order_data["customer_name"],
                        'creation_method': 'excel_import',
                        'source_file': file_name,
                        'operation_description': f"Import Excel: {operation_type.value.lower()} ordine {order_number}, aggiunto {line_data['requested_quantity']}x {line_data['product_sku']} per cliente {order_data['customer_name']}",
                        'import_stats': {
                            'orders_created': len(orders_created_list),
                            'orders_updated': len(orders_updated_list),
                            'source_filename': file_name
                        }
                    },
                    api_endpoint="/orders/commit-excel-orders"
                )
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Import Excel completato: {len(orders_created_list)} ordini creati, {len(orders_updated_list)} ordini aggiornati",
            "orders_created": len(orders_created_list),
            "orders_updated": len(orders_updated_list),
            "orders_created_list": orders_created_list,
            "orders_updated_list": orders_updated_list,
            "file_name": file_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore durante commit Excel: {str(e)}")

# === ENDPOINT MODIFICA NOME CLIENTE ===

from pydantic import BaseModel

class CustomerNameUpdateRequest(BaseModel):
    customer_name: str
    update_ddt: bool = False

@router.patch("/{order_number}/customer")
def update_customer_name(
    order_number: str, 
    update_request: CustomerNameUpdateRequest,
    db: Session = Depends(get_db)
):
    """Aggiorna il nome cliente di un ordine e opzionalmente del DDT collegato"""
    logger = LoggingService(db)
    
    try:
        # Trova l'ordine
        order = db.query(models.Order).filter(
            models.Order.order_number == order_number
        ).first()
        
        if not order:
            raise HTTPException(status_code=404, detail="Ordine non trovato")
        
        # Verifica che l'ordine non sia archiviato
        if order.is_archived:
            raise HTTPException(status_code=400, detail="Impossibile modificare ordini archiviati")
        
        old_customer_name = order.customer_name
        new_customer_name = update_request.customer_name.strip()
        
        if not new_customer_name:
            raise HTTPException(status_code=400, detail="Il nome cliente non può essere vuoto")
        
        if old_customer_name == new_customer_name:
            return {"success": True, "message": "Nessuna modifica necessaria"}
        
        # Aggiorna il nome cliente dell'ordine
        order.customer_name = new_customer_name
        
        updated_components = ["ordine"]
        
        # Se richiesto, aggiorna anche il DDT collegato
        if update_request.update_ddt:
            from wms_app.models.ddt import DDT
            
            ddt = db.query(DDT).filter(DDT.order_number == order_number).first()
            if ddt:
                ddt.customer_name = new_customer_name
                updated_components.append("DDT")
        
        # Log dell'operazione
        logger.log_operation(
            operation_type=OperationType.ORDINE_MODIFICATO,
            operation_category=OperationCategory.MANUAL,
            status=OperationStatus.SUCCESS,
            product_sku=None,
            location_from=None,
            location_to=None,
            quantity=None,
            user_id="system",
            file_name=None,
            details={
                'order_number': order_number,
                'old_customer_name': old_customer_name,
                'new_customer_name': new_customer_name,
                'updated_components': updated_components,
                'operation_description': f"Modifica nome cliente ordine {order_number}: '{old_customer_name}' → '{new_customer_name}'"
            },
            api_endpoint=f"/orders/{order_number}/customer"
        )
        
        db.commit()
        
        components_text = " e ".join(updated_components)
        return {
            "success": True,
            "message": f"Nome cliente aggiornato con successo per {components_text}",
            "old_customer_name": old_customer_name,
            "new_customer_name": new_customer_name,
            "updated_components": updated_components
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.log_operation(
            operation_type=OperationType.ORDINE_MODIFICATO,
            operation_category=OperationCategory.MANUAL,
            status=OperationStatus.ERROR,
            error_message=str(e),
            details={
                'order_number': order_number,
                'attempted_customer_name': update_request.customer_name,
                'operation_description': f"Errore modifica nome cliente ordine {order_number}"
            },
            api_endpoint=f"/orders/{order_number}/customer"
        )
        raise HTTPException(status_code=500, detail=f"Errore durante l'aggiornamento: {str(e)}")

# ============================================================================
# EDIT ORDER - Helper Function and Endpoint
# ============================================================================

def _transfer_to_terra(db: Session, product_sku: str, quantity: int, reason: str) -> Dict[str, Any]:
    """
    Helper function to transfer inventory back to TERRA location.
    Creates or updates TERRA inventory record.

    Args:
        db: Database session
        product_sku: SKU of the product to transfer
        quantity: Quantity to transfer
        reason: Reason for transfer (for logging)

    Returns:
        Dictionary with transfer details
    """
    terra_inventory = db.query(models.Inventory).filter(
        models.Inventory.product_sku == product_sku,
        models.Inventory.location_name == "TERRA"
    ).first()

    if terra_inventory:
        terra_inventory.quantity += quantity
    else:
        new_terra_inventory = models.Inventory(
            product_sku=product_sku,
            location_name="TERRA",
            quantity=quantity
        )
        db.add(new_terra_inventory)

    return {
        "product_sku": product_sku,
        "quantity": quantity,
        "location": "TERRA",
        "reason": reason
    }

@router.put("/{order_id}/edit")
def edit_order(
    order_id: int,
    edit_request: schemas.OrderEditRequest,
    db: Session = Depends(get_db)
    # TODO: Add authentication: current_user = Depends(require_permission("orders_edit"))
):
    """
    Edit an order by modifying its lines (add/remove/modify products).

    Rules:
    - Cannot edit completed, cancelled, or archived orders
    - If line has picked_quantity > 0 and is removed/reduced:
      * Transfer picked_quantity back to TERRA location
      * Delete corresponding OutgoingStock records
      * Add warning to response
    - If DDT exists, warn user but don't block operation
    - Cannot reduce requested_quantity below picked_quantity (auto-transfers excess to TERRA)

    Args:
        order_id: ID of the order to edit
        edit_request: OrderEditRequest with lines array
        db: Database session

    Returns:
        OrderEditResponse with success status, message, and warnings
    """
    logger = LoggingService(db)
    warnings = []

    try:
        # 1. FETCH AND VALIDATE ORDER
        order = db.query(models.Order).options(
            joinedload(models.Order.lines)
        ).filter(
            models.Order.id == order_id
        ).first()

        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # Validate order state
        if order.is_completed:
            raise HTTPException(status_code=400, detail="Cannot edit completed orders")
        if order.is_cancelled:
            raise HTTPException(status_code=400, detail="Cannot edit cancelled orders")
        if order.is_archived:
            raise HTTPException(status_code=400, detail="Cannot edit archived orders")

        # 2. CHECK FOR DDT (WARNING ONLY)
        from wms_app.models.ddt import DDT
        ddt = db.query(DDT).filter(DDT.order_number == order.order_number).first()
        if ddt:
            warnings.append({
                'type': 'ddt_exists',
                'product_sku': None,
                'message': f'ATTENZIONE: Questo ordine ha un DDT collegato ({ddt.ddt_number}). Modificando l\'ordine potrebbe essere necessario aggiornare anche il DDT.',
                'quantity': None
            })

        # 3. VALIDATE ALL SKUS EXIST
        requested_skus = set(line.product_sku for line in edit_request.lines)
        existing_products = db.query(models.Product).filter(
            models.Product.sku.in_(requested_skus)
        ).all()
        existing_skus = set(p.sku for p in existing_products)

        missing_skus = requested_skus - existing_skus
        if missing_skus:
            raise HTTPException(
                status_code=400,
                detail=f"Products not found: {', '.join(missing_skus)}"
            )

        # 4. BUILD OLD STATE MAP FOR COMPARISON
        old_lines_map = {line.product_sku: line for line in order.lines}

        # 5. BUILD NEW STATE MAP FROM REQUEST (consolidate duplicates)
        new_lines_map = {}
        for line_req in edit_request.lines:
            if line_req.product_sku in new_lines_map:
                new_lines_map[line_req.product_sku] += line_req.requested_quantity
            else:
                new_lines_map[line_req.product_sku] = line_req.requested_quantity

        # 5.5. DELETE ALL EXISTING RESERVATIONS FOR THIS ORDER
        # When order is edited, old reservations become invalid
        # The system will recreate them on next picking with correct quantities
        from wms_app.models.reservations import InventoryReservation
        deleted_reservations = db.query(InventoryReservation).filter(
            InventoryReservation.order_id == str(order.order_number)
        ).delete()

        if deleted_reservations > 0:
            warnings.append({
                'type': 'reservations_cleared',
                'product_sku': None,
                'message': f'Cancellate {deleted_reservations} prenotazioni obsolete. Verranno ricreate al prossimo picking.',
                'quantity': None
            })

        # 6. PROCESS CHANGES: REMOVED/REDUCED LINES
        for sku, old_line in old_lines_map.items():
            new_quantity = new_lines_map.get(sku, 0)

            if new_quantity == 0:
                # LINE REMOVED COMPLETELY
                if old_line.picked_quantity > 0:
                    # Transfer picked items back to TERRA
                    _transfer_to_terra(
                        db=db,
                        product_sku=sku,
                        quantity=old_line.picked_quantity,
                        reason=f"Order {order.order_number} line removed during edit"
                    )

                    warnings.append({
                        'type': 'terra_transfer',
                        'product_sku': sku,
                        'message': f'{old_line.picked_quantity} unità di {sku} trasferite a TERRA (riga rimossa)',
                        'quantity': old_line.picked_quantity
                    })

                    # Delete OutgoingStock records
                    db.query(models.OutgoingStock).filter(
                        models.OutgoingStock.order_line_id == old_line.id
                    ).delete()

                # Delete the order line
                db.delete(old_line)

            elif new_quantity < old_line.requested_quantity:
                # LINE QUANTITY REDUCED
                if new_quantity < old_line.picked_quantity:
                    # Cannot reduce below picked - calculate excess picked
                    excess_picked = old_line.picked_quantity - new_quantity

                    # Transfer excess back to TERRA
                    _transfer_to_terra(
                        db=db,
                        product_sku=sku,
                        quantity=excess_picked,
                        reason=f"Order {order.order_number} quantity reduced below picked"
                    )

                    warnings.append({
                        'type': 'terra_transfer',
                        'product_sku': sku,
                        'message': f'{excess_picked} unità di {sku} trasferite a TERRA (quantità ridotta da {old_line.requested_quantity} a {new_quantity}, ma {old_line.picked_quantity} già prelevate)',
                        'quantity': excess_picked
                    })

                    # Adjust OutgoingStock to match new quantity
                    outgoing_items = db.query(models.OutgoingStock).filter(
                        models.OutgoingStock.order_line_id == old_line.id
                    ).all()

                    total_outgoing = sum(item.quantity for item in outgoing_items)
                    if total_outgoing > new_quantity:
                        # Reduce outgoing stock proportionally
                        reduction_needed = total_outgoing - new_quantity
                        for outgoing_item in outgoing_items:
                            if reduction_needed <= 0:
                                break
                            reduction_amount = min(outgoing_item.quantity, reduction_needed)
                            outgoing_item.quantity -= reduction_amount
                            reduction_needed -= reduction_amount

                            if outgoing_item.quantity == 0:
                                db.delete(outgoing_item)

                    # Set picked_quantity to new requested (effectively capping it)
                    old_line.picked_quantity = new_quantity
                    old_line.requested_quantity = new_quantity
                else:
                    # Simple quantity reduction (no picked overflow)
                    old_line.requested_quantity = new_quantity

        # 7. PROCESS CHANGES: ADDED/INCREASED LINES
        for sku, new_quantity in new_lines_map.items():
            if sku in old_lines_map:
                old_line = old_lines_map[sku]
                if new_quantity > old_line.requested_quantity:
                    # LINE QUANTITY INCREASED
                    old_line.requested_quantity = new_quantity
            else:
                # NEW LINE ADDED
                new_line = models.OrderLine(
                    order_id=order.id,
                    product_sku=sku,
                    requested_quantity=new_quantity,
                    picked_quantity=0
                )
                db.add(new_line)

        # 8. LOG THE OPERATION
        before_lines = [
            f"{line.product_sku}: {line.requested_quantity} (picked: {line.picked_quantity})"
            for line in old_lines_map.values()
        ]
        after_lines = [
            f"{sku}: {qty}"
            for sku, qty in new_lines_map.items()
        ]

        logger.log_operation(
            operation_type=OperationType.ORDINE_MODIFICATO,
            operation_category=OperationCategory.MANUAL,
            status=OperationStatus.WARNING if warnings else OperationStatus.SUCCESS,
            product_sku=None,
            location_from=None,
            location_to=None,
            quantity=None,
            user_id="system",  # TODO: Replace with real auth when available
            file_name=None,
            details={
                'order_number': order.order_number,
                'order_id': order.id,
                'customer_name': order.customer_name,
                'operation_description': f"Order {order.order_number} edited: lines modified",
                'before_lines': before_lines,
                'after_lines': after_lines,
                'warnings_count': len(warnings),
                'has_ddt': ddt is not None,
                'terra_transfers': [w for w in warnings if w.get('type') == 'terra_transfer']
            },
            api_endpoint=f"/orders/{order_id}/edit"
        )

        # 9. COMMIT TRANSACTION
        db.commit()
        db.refresh(order)

        # 10. RETURN SUCCESS WITH WARNINGS
        return {
            "success": True,
            "message": f"Order {order.order_number} updated successfully" +
                      (f" ({len(warnings)} warnings)" if warnings else ""),
            "warnings": warnings,
            "order": order
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()

        # Log error
        logger.log_operation(
            operation_type=OperationType.ORDINE_MODIFICATO,
            operation_category=OperationCategory.MANUAL,
            status=OperationStatus.ERROR,
            error_message=str(e),
            details={
                'order_id': order_id,
                'attempted_lines': [
                    f"{line.product_sku}: {line.requested_quantity}"
                    for line in edit_request.lines
                ],
                'operation_description': f"Error editing order ID {order_id}"
            },
            api_endpoint=f"/orders/{order_id}/edit"
        )

        raise HTTPException(status_code=500, detail=f"Error editing order: {str(e)}")

@router.get("/{order_number}/pickup-locations")
def get_order_pickup_locations(
    order_number: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("orders_view"))
):
    """
    Recupera i dettagli delle posizioni di prelievo per un ordine completato.
    Mostra da quali ubicazioni sono stati prelevati i prodotti.
    """
    try:
        # Verifica che l'ordine esista
        order = db.query(models.Order).filter(
            models.Order.order_number == order_number
        ).first()
        
        if not order:
            raise HTTPException(status_code=404, detail=f"Ordine '{order_number}' non trovato")
        
        # Recupera i log di prelievo per questo ordine
        logger = LoggingService(db)
        pickup_logs = logger.get_logs(
            operation_types=[
                OperationType.PRELIEVO_MANUALE,
                OperationType.PRELIEVO_FILE,
                OperationType.PRELIEVO_TEMPO_REALE,
                OperationType.PICKING_CONFERMATO
            ],
            order_number=order_number,
            limit=1000,  # Recupera tutti i log di prelievo
            order_by="timestamp",
            order_direction="asc"
        )
        
        pickup_details = []
        for log in pickup_logs['logs']:
            # Estrai informazioni dettagliate dal log
            pickup_detail = {
                'product_sku': log.product_sku,
                'location_from': log.location_from,
                'quantity_picked': log.quantity,
                'timestamp': log.timestamp.strftime('%d/%m/%Y %H:%M'),
                'operator': log.user_id or 'Sistema',
                'operation_type': log.operation_type,
                'details': log.details
            }
            pickup_details.append(pickup_detail)
        
        return {
            "order_number": order_number,
            "pickup_locations": pickup_details,
            "total_operations": len(pickup_details)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel recupero posizioni prelievo: {str(e)}")


@router.get("/{order_number}/pickup-locations/export-excel")
def export_pickup_locations_excel(
    order_number: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("orders_view"))
):
    """
    Esporta le posizioni di prelievo di un ordine in formato Excel.
    """
    if not EXCEL_AVAILABLE:
        raise HTTPException(status_code=500, detail="Libreria openpyxl non disponibile")

    try:
        # Verifica che l'ordine esista
        order = db.query(models.Order).filter(
            models.Order.order_number == order_number
        ).first()

        if not order:
            raise HTTPException(status_code=404, detail=f"Ordine '{order_number}' non trovato")

        # Recupera i log di prelievo
        logger = LoggingService(db)
        pickup_logs = logger.get_logs(
            operation_types=[
                OperationType.PRELIEVO_MANUALE,
                OperationType.PRELIEVO_FILE,
                OperationType.PRELIEVO_TEMPO_REALE,
                OperationType.PICKING_CONFERMATO
            ],
            order_number=order_number,
            limit=1000,
            order_by="timestamp",
            order_direction="asc"
        )

        # Crea il workbook Excel
        wb = Workbook()
        ws = wb.active
        ws.title = f"Prelievi Ordine {order_number}"

        # Stili
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="00516E", end_color="00516E", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")

        # Intestazioni
        headers = ["SKU Prodotto", "Ubicazione", "Quantità", "Data/Ora", "Operatore"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment

        # Dati
        for row_idx, log in enumerate(pickup_logs['logs'], 2):
            ws.cell(row=row_idx, column=1, value=log.product_sku)
            ws.cell(row=row_idx, column=2, value=log.location_from or 'N/D')
            ws.cell(row=row_idx, column=3, value=log.quantity)
            ws.cell(row=row_idx, column=4, value=log.timestamp.strftime('%d/%m/%Y %H:%M'))
            ws.cell(row=row_idx, column=5, value=log.user_id or 'Sistema')

        # Larghezza colonne
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 12
        ws.column_dimensions['D'].width = 18
        ws.column_dimensions['E'].width = 15

        # Salva in buffer
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"prelievi_ordine_{order_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore export Excel: {str(e)}")


@router.get("/{order_number}/pickup-locations/export-pdf")
def export_pickup_locations_pdf(
    order_number: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("orders_view"))
):
    """
    Esporta le posizioni di prelievo di un ordine in formato PDF.
    """
    try:
        # Verifica che l'ordine esista
        order = db.query(models.Order).filter(
            models.Order.order_number == order_number
        ).first()

        if not order:
            raise HTTPException(status_code=404, detail=f"Ordine '{order_number}' non trovato")

        # Recupera i log di prelievo
        logger = LoggingService(db)
        pickup_logs = logger.get_logs(
            operation_types=[
                OperationType.PRELIEVO_MANUALE,
                OperationType.PRELIEVO_FILE,
                OperationType.PRELIEVO_TEMPO_REALE,
                OperationType.PICKING_CONFERMATO
            ],
            order_number=order_number,
            limit=1000,
            order_by="timestamp",
            order_direction="asc"
        )

        # Crea il PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=30, bottomMargin=30)
        elements = []
        styles = getSampleStyleSheet()

        # Titolo
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1  # Center
        )
        elements.append(Paragraph(f"Posizioni di Prelievo - Ordine {order_number}", title_style))

        # Info ordine
        info_style = ParagraphStyle(
            'Info',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=15,
            alignment=1
        )
        elements.append(Paragraph(f"Cliente: {order.customer_name or 'N/D'} | Data export: {datetime.now().strftime('%d/%m/%Y %H:%M')}", info_style))
        elements.append(Spacer(1, 10))

        # Tabella
        table_data = [["SKU", "Ubicazione", "Qtà", "Data/Ora", "Operatore"]]

        for log in pickup_logs['logs']:
            table_data.append([
                log.product_sku,
                log.location_from or 'N/D',
                str(log.quantity),
                log.timestamp.strftime('%d/%m/%Y %H:%M'),
                log.user_id or 'Sistema'
            ])

        # Riga totale
        total_qty = sum(log.quantity for log in pickup_logs['logs'])
        table_data.append(["TOTALE", "", str(total_qty), f"{len(pickup_logs['logs'])} operazioni", ""])

        # Stile tabella
        table = Table(table_data, colWidths=[120, 70, 50, 100, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00516E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.white),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F2F2F2')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#00516E')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#DEE2E6')),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))

        elements.append(table)

        # Build PDF
        doc.build(elements)
        buffer.seek(0)

        filename = f"prelievi_ordine_{order_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore export PDF: {str(e)}")


# ============================================================
# PRELIEVI REAL-TIME
# ============================================================

@router.get("/{order_id}/product-locations/{product_sku}")
def get_product_locations_for_picking(
    order_id: int,
    product_sku: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("orders_picking_scan"))
):
    """Tutte le ubicazioni con stock disponibile per un prodotto specifico dell'ordine."""
    from wms_app.models.reservations import InventoryReservation

    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    order_line = db.query(models.OrderLine).filter(
        models.OrderLine.order_id == order_id,
        models.OrderLine.product_sku == product_sku
    ).first()
    if not order_line:
        raise HTTPException(status_code=404, detail="Prodotto non trovato nell'ordine")

    remaining = order_line.requested_quantity - order_line.picked_quantity

    # Tutte le ubicazioni con stock per questo SKU, ordinate per quantità desc
    inventories = db.query(models.Inventory).filter(
        models.Inventory.product_sku == product_sku,
        models.Inventory.quantity > 0
    ).order_by(models.Inventory.quantity.desc()).all()

    # Ubicazioni suggerite (prenotazioni attive per questo ordine/sku)
    suggested = db.query(InventoryReservation).filter(
        InventoryReservation.order_id == str(order.order_number),
        InventoryReservation.product_sku == product_sku,
        InventoryReservation.status == 'active'
    ).all()
    suggested_location_names = {r.location_name for r in suggested}

    locations = []
    for inv in inventories:
        locations.append({
            "location_name": inv.location_name,
            "available_quantity": inv.quantity,
            "is_suggested": inv.location_name in suggested_location_names
        })

    product = db.query(models.Product).filter(models.Product.sku == product_sku).first()

    return {
        "product_sku": product_sku,
        "product_name": product.description if product else product_sku,
        "remaining_to_pick": remaining,
        "locations": locations
    }


@router.post("/{order_id}/activate-picking-session")
def activate_picking_session(
    order_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("orders_picking_scan"))
):
    """Attiva le prenotazioni per l'ordine (evitando duplicati) e restituisce il piano di picking."""
    import uuid
    from wms_app.services.reservation_service import ReservationService

    order = db.query(models.Order).options(
        joinedload(models.Order.lines).joinedload(models.OrderLine.product)
    ).filter(models.Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    if order.is_completed:
        raise HTTPException(status_code=400, detail="Ordine già completato")
    if order.is_cancelled:
        raise HTTPException(status_code=400, detail="Ordine annullato")

    reservation_service = ReservationService(db)
    reservation_service.cleanup_expired_reservations()

    # Prepara prodotti con quantità rimanente
    products_needed = []
    for line in order.lines:
        remaining = line.requested_quantity - line.picked_quantity
        if remaining > 0:
            products_needed.append({
                'sku': line.product_sku,
                'quantity': remaining,
                'line_id': line.id
            })

    # Alloca ubicazioni (il servizio evita già i duplicati)
    allocation_map = {}
    if products_needed:
        try:
            allocations = reservation_service.allocate_picking_locations(
                order_id=str(order.order_number),
                products_needed=products_needed
            )
            allocation_map = {a['sku']: a for a in allocations}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Errore allocazione picking: {str(e)}")

    # Costruisce il piano di picking
    picking_plan = []
    for line in order.lines:
        remaining = line.requested_quantity - line.picked_quantity
        ean_codes = [e.ean for e in db.query(models.EanCode).filter(
            models.EanCode.product_sku == line.product_sku
        ).all()]

        suggested_locations = []
        status = "completed" if remaining <= 0 else "out_of_stock"

        if remaining > 0:
            allocation = allocation_map.get(line.product_sku)
            if allocation:
                for loc in allocation.get('allocations', []):
                    suggested_locations.append({
                        "location_name": loc['location_name'],
                        "available_quantity": loc['quantity'],
                        "reservation_id": loc.get('reservation_id'),
                        "to_pick": loc['quantity']
                    })
                if allocation['fully_allocated']:
                    status = "full_stock"
                elif suggested_locations:
                    status = "partial_stock"

        picking_plan.append({
            "order_line_id": line.id,
            "product_sku": line.product_sku,
            "product_name": line.product.description if line.product else None,
            "ean_codes": ean_codes,
            "requested_quantity": line.requested_quantity,
            "picked_quantity": line.picked_quantity,
            "remaining": remaining,
            "suggested_locations": suggested_locations,
            "status": status
        })

    session_id = str(uuid.uuid4())

    return {
        "session_id": session_id,
        "order_id": order.id,
        "order_number": order.order_number,
        "customer_name": order.customer_name,
        "picking_plan": picking_plan
    }


@router.post("/{order_id}/validate-scan-location")
def validate_scan_location_picking(
    order_id: int,
    request: schemas.ValidateScanLocationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("orders_picking_scan"))
):
    """Valida che un'ubicazione scansionata abbia stock per almeno un prodotto dell'ordine."""
    order = db.query(models.Order).options(
        joinedload(models.Order.lines).joinedload(models.OrderLine.product)
    ).filter(models.Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    # Verifica esistenza ubicazione
    location = db.query(models.Location).filter(
        models.Location.name == request.location_name
    ).first()

    if not location:
        return {
            "valid": False,
            "location_name": request.location_name,
            "products_available": [],
            "error": f"Ubicazione '{request.location_name}' non trovata",
            "status": "location_not_found"
        }

    # Cerca prodotti dell'ordine con stock in questa ubicazione
    products_available = []
    for line in order.lines:
        remaining = line.requested_quantity - line.picked_quantity
        if remaining <= 0:
            continue

        inventory = db.query(models.Inventory).filter(
            models.Inventory.location_name == request.location_name,
            models.Inventory.product_sku == line.product_sku,
            models.Inventory.quantity > 0
        ).first()

        if inventory:
            ean_codes = [e.ean for e in db.query(models.EanCode).filter(
                models.EanCode.product_sku == line.product_sku
            ).all()]
            products_available.append({
                "product_sku": line.product_sku,
                "product_name": line.product.description if line.product else None,
                "order_line_id": line.id,
                "available_quantity": inventory.quantity,
                "needed": remaining,
                "ean_codes": ean_codes
            })

    if not products_available:
        return {
            "valid": False,
            "location_name": request.location_name,
            "products_available": [],
            "error": f"Nessun prodotto dell'ordine trovato in '{request.location_name}'",
            "status": "no_stock_for_order"
        }

    return {
        "valid": True,
        "location_name": request.location_name,
        "products_available": products_available,
        "error": None,
        "status": "ok"
    }


@router.post("/{order_id}/validate-scan-ean")
def validate_scan_ean_picking(
    order_id: int,
    request: schemas.ValidateScanEanRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("orders_picking_scan"))
):
    """Valida EAN nella location corrente. Accetta qualsiasi location con stock (picking libero)."""
    order = db.query(models.Order).options(
        joinedload(models.Order.lines).joinedload(models.OrderLine.product)
    ).filter(models.Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    # Risolvi EAN -> SKU
    product_sku = None
    product = db.query(models.Product).filter(models.Product.sku == request.ean_code).first()
    if product:
        product_sku = product.sku
    else:
        ean = db.query(models.EanCode).filter(models.EanCode.ean == request.ean_code).first()
        if ean:
            product_sku = ean.product_sku

    if not product_sku:
        return {
            "valid": False,
            "error": f"Codice '{request.ean_code}' non trovato nel database",
            "status": "ean_not_found"
        }

    # Trova la riga ordine
    order_line = next((l for l in order.lines if l.product_sku == product_sku), None)

    if not order_line:
        return {
            "valid": False,
            "product_sku": product_sku,
            "error": f"Prodotto '{product_sku}' non presente in questo ordine",
            "status": "sku_not_in_order"
        }

    remaining = order_line.requested_quantity - order_line.picked_quantity
    if remaining <= 0:
        return {
            "valid": False,
            "product_sku": product_sku,
            "error": f"Prodotto '{product_sku}' già completamente prelevato",
            "status": "no_remaining"
        }

    # Verifica stock nella location (picking libero: qualsiasi location con stock va bene)
    inventory = db.query(models.Inventory).filter(
        models.Inventory.location_name == request.location_name,
        models.Inventory.product_sku == product_sku,
        models.Inventory.quantity > 0
    ).first()

    if not inventory:
        return {
            "valid": False,
            "product_sku": product_sku,
            "error": f"Nessuno stock di '{product_sku}' in '{request.location_name}'",
            "status": "no_stock_at_location"
        }

    product_name = order_line.product.description if order_line.product else product_sku
    max_pickable = min(remaining, inventory.quantity)

    return {
        "valid": True,
        "product_sku": product_sku,
        "product_name": product_name,
        "order_line_id": order_line.id,
        "available_at_location": inventory.quantity,
        "remaining_to_pick": remaining,
        "max_pickable": max_pickable,
        "error": None,
        "status": "ok"
    }


@router.post("/{order_id}/realtime-commit-pick")
def realtime_commit_pick(
    order_id: int,
    request: schemas.RealtimeCommitPickRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("orders_picking_scan"))
):
    """Core endpoint: salva un prelievo real-time con auto-save immediato."""
    from wms_app.services.reservation_service import ReservationService
    from wms_app.models.reservations import InventoryReservation

    order = db.query(models.Order).options(
        joinedload(models.Order.lines)
    ).filter(models.Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    if order.is_completed:
        raise HTTPException(status_code=400, detail="Ordine già completato")

    order_line = db.query(models.OrderLine).filter(
        models.OrderLine.id == request.order_line_id,
        models.OrderLine.order_id == order_id
    ).first()

    if not order_line:
        raise HTTPException(status_code=404, detail="Riga ordine non trovata")

    remaining = order_line.requested_quantity - order_line.picked_quantity
    if request.quantity > remaining:
        return {
            "success": False,
            "error": f"Quantità richiesta ({request.quantity}) supera il rimanente ({remaining})",
            "status": "quantity_exceeded"
        }

    inventory = db.query(models.Inventory).filter(
        models.Inventory.product_sku == request.product_sku,
        models.Inventory.location_name == request.location_name
    ).first()

    if not inventory or inventory.quantity < request.quantity:
        available = inventory.quantity if inventory else 0
        return {
            "success": False,
            "error": f"Stock insufficiente in '{request.location_name}' per '{request.product_sku}': disponibili {available}, richiesti {request.quantity}",
            "status": "insufficient_stock"
        }

    try:
        # Aggiorna inventario
        inventory.quantity -= request.quantity

        # Aggiorna riga ordine
        order_line.picked_quantity += request.quantity

        # Aggiorna OutgoingStock
        outgoing = db.query(models.OutgoingStock).filter(
            models.OutgoingStock.order_line_id == request.order_line_id,
            models.OutgoingStock.product_sku == request.product_sku
        ).first()

        if outgoing:
            outgoing.quantity += request.quantity
        else:
            db.add(models.OutgoingStock(
                order_line_id=request.order_line_id,
                product_sku=request.product_sku,
                quantity=request.quantity
            ))

        # Gestione prenotazioni
        reservation_service = ReservationService(db)
        new_remaining = order_line.requested_quantity - order_line.picked_quantity

        if request.reservation_id:
            reservation_service.complete_reservation(request.reservation_id, request.quantity)
        else:
            active_reservation = db.query(InventoryReservation).filter(
                and_(
                    InventoryReservation.order_id == str(order.order_number),
                    InventoryReservation.product_sku == request.product_sku,
                    InventoryReservation.location_name == request.location_name,
                    InventoryReservation.status == 'active'
                )
            ).first()
            if active_reservation:
                reservation_service.complete_reservation(active_reservation.id, request.quantity)

        # Se il prodotto è completato, cancella le prenotazioni rimanenti
        if new_remaining == 0:
            remaining_reservations = db.query(InventoryReservation).filter(
                and_(
                    InventoryReservation.order_id == str(order.order_number),
                    InventoryReservation.product_sku == request.product_sku,
                    InventoryReservation.status == 'active'
                )
            ).all()
            for res in remaining_reservations:
                res.status = 'cancelled'

        # Log operazione
        logger = LoggingService(db)
        logger.log_operation(
            operation_type=OperationType.PRELIEVO_TEMPO_REALE,
            operation_category=OperationCategory.PICKING,
            status=OperationStatus.SUCCESS,
            product_sku=request.product_sku,
            location_from=request.location_name,
            quantity=request.quantity,
            user_id="realtime_picker",
            details={
                'order_number': order.order_number,
                'customer_name': order.customer_name,
                'order_line_id': request.order_line_id,
                'session_id': request.session_id,
                'operation_description': f"Prelievo real-time: {request.product_sku} ({request.quantity} pz) da {request.location_name} per ordine {order.order_number}",
                'picking_type': 'prelievo_tempo_reale'
            },
            api_endpoint=f"/orders/{order_id}/realtime-commit-pick"
        )

        # Verifica se l'ordine è completamente prelevato
        db.flush()
        order_fully_picked = all(
            line.picked_quantity >= line.requested_quantity
            for line in order.lines
        )

        db.commit()

        return {
            "success": True,
            "product_sku": request.product_sku,
            "location_name": request.location_name,
            "quantity_picked": request.quantity,
            "new_picked_quantity": order_line.picked_quantity,
            "new_remaining": new_remaining,
            "product_completed": new_remaining == 0,
            "order_fully_picked": order_fully_picked,
            "progress": f"{order_line.picked_quantity}/{order_line.requested_quantity}"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore durante il prelievo: {str(e)}")


@router.post("/{order_id}/realtime-undo-pick")
def realtime_undo_pick(
    order_id: int,
    request: schemas.RealtimeUndoPickRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("orders_picking_scan"))
):
    """Annulla un singolo prelievo real-time ripristinando inventario e picked_quantity."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    order_line = db.query(models.OrderLine).filter(
        models.OrderLine.id == request.order_line_id,
        models.OrderLine.order_id == order_id
    ).first()

    if not order_line:
        raise HTTPException(status_code=404, detail="Riga ordine non trovata")

    if order_line.picked_quantity < request.quantity:
        return {
            "success": False,
            "error": f"Non si può annullare {request.quantity} pz: prelevati {order_line.picked_quantity}",
            "status": "invalid_quantity"
        }

    try:
        # Ripristina inventario
        inventory = db.query(models.Inventory).filter(
            models.Inventory.product_sku == request.product_sku,
            models.Inventory.location_name == request.location_name
        ).first()

        if inventory:
            inventory.quantity += request.quantity
        else:
            db.add(models.Inventory(
                location_name=request.location_name,
                product_sku=request.product_sku,
                quantity=request.quantity
            ))

        # Riduci picked_quantity
        order_line.picked_quantity -= request.quantity

        # Aggiorna OutgoingStock
        outgoing = db.query(models.OutgoingStock).filter(
            models.OutgoingStock.order_line_id == request.order_line_id,
            models.OutgoingStock.product_sku == request.product_sku
        ).first()

        if outgoing:
            if outgoing.quantity <= request.quantity:
                db.delete(outgoing)
            else:
                outgoing.quantity -= request.quantity

        new_remaining = order_line.requested_quantity - order_line.picked_quantity

        # Log operazione
        logger = LoggingService(db)
        logger.log_operation(
            operation_type=OperationType.PRELIEVO_TEMPO_REALE,
            operation_category=OperationCategory.PICKING,
            status=OperationStatus.CANCELLED,
            product_sku=request.product_sku,
            location_from=request.location_name,
            quantity=request.quantity,
            user_id="realtime_picker",
            details={
                'order_number': order.order_number,
                'operation_description': f"ANNULLATO prelievo real-time: {request.product_sku} ({request.quantity} pz) da {request.location_name} per ordine {order.order_number}",
                'picking_type': 'undo_prelievo_tempo_reale'
            },
            api_endpoint=f"/orders/{order_id}/realtime-undo-pick"
        )

        db.commit()

        return {
            "success": True,
            "quantity_restored": request.quantity,
            "new_picked_quantity": order_line.picked_quantity,
            "new_remaining": new_remaining
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore durante l'annullamento: {str(e)}")
