from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc
from typing import List, Dict, Optional
from datetime import datetime, date
import uuid
import io

# Import per export Excel e PDF
try:
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
from wms_app.database import get_db
from wms_app.services.logging_service import LoggingService
from wms_app.models.logs import OperationType, OperationCategory, OperationStatus


# Import templates lazy
def get_templates():
    from wms_app.main import templates
    return templates


router = APIRouter(
    prefix="/arrivals",
    tags=["arrivals"],
)


# ==================== PAGINA HTML ====================

@router.get("/manage", response_class=HTMLResponse)
async def get_arrivals_management_page(request: Request, db: Session = Depends(get_db)):
    """Pagina gestione arrivi - Desktop e Mobile"""
    # Carica documenti non completati (bozze e in lavorazione)
    arrivals = db.query(models.arrivals.Arrival).filter(
        models.arrivals.Arrival.is_completed == False
    ).options(
        joinedload(models.arrivals.Arrival.lines).joinedload(models.arrivals.ArrivalLine.product)
    ).order_by(desc(models.arrivals.Arrival.created_date)).all()

    # Storico completati ora caricato via AJAX con paginazione

    return get_templates().TemplateResponse("arrivals.html", {
        "request": request,
        "arrivals": arrivals,
        "active_page": "arrivals"
    })


# ==================== API CRUD ====================

@router.post("/", response_model=schemas.arrivals.Arrival)
def create_arrival(
    arrival: schemas.arrivals.ArrivalCreate,
    db: Session = Depends(get_db)
):
    """Crea nuovo documento arrivo (Desktop form)"""
    logger = LoggingService(db)

    # Controlla duplicato numero documento
    existing = db.query(models.arrivals.Arrival).filter(
        models.arrivals.Arrival.arrival_number == arrival.arrival_number
    ).first()

    if existing:
        logger.log_error(
            operation_type=OperationType.ARRIVO_CREATO,
            error=f"Arrival number {arrival.arrival_number} already exists",
            operation_category=OperationCategory.MANUAL,
            details={'arrival_number': arrival.arrival_number}
        )
        raise HTTPException(status_code=400, detail="Numero documento già esistente")

    # Crea documento
    new_arrival = models.arrivals.Arrival(
        arrival_number=arrival.arrival_number,
        supplier_name=arrival.supplier_name,
        arrival_date=arrival.arrival_date or datetime.now(),
        notes=arrival.notes,
        is_draft=True,
        is_completed=False
    )

    db.add(new_arrival)

    try:
        db.flush()  # Ottieni ID per le righe
    except Exception as e:
        db.rollback()
        logger.log_error(
            operation_type=OperationType.ARRIVO_CREATO,
            error=str(e),
            operation_category=OperationCategory.MANUAL,
            details={'arrival_number': arrival.arrival_number}
        )
        raise HTTPException(status_code=500, detail=f"Errore creazione documento: {str(e)}")

    # Consolida righe con stesso SKU (somma quantità)
    consolidated_lines = {}
    for line in arrival.lines:
        sku = line.product_sku

        # Verifica esistenza prodotto
        product = db.query(models.Product).filter(
            models.Product.sku == sku
        ).first()

        if not product:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Prodotto {sku} non trovato"
            )

        if sku in consolidated_lines:
            consolidated_lines[sku] += line.expected_quantity
        else:
            consolidated_lines[sku] = line.expected_quantity

    # Crea righe consolidate
    for sku, qty in consolidated_lines.items():
        arrival_line = models.arrivals.ArrivalLine(
            arrival_id=new_arrival.id,
            product_sku=sku,
            expected_quantity=qty,
            received_quantity=0
        )
        db.add(arrival_line)

    try:
        db.commit()
        db.refresh(new_arrival)
    except Exception as e:
        db.rollback()
        logger.log_error(
            operation_type=OperationType.ARRIVO_CREATO,
            error=str(e),
            operation_category=OperationCategory.MANUAL
        )
        raise HTTPException(status_code=500, detail="Errore salvataggio righe")

    # Log creazione
    logger.log_operation(
        operation_type=OperationType.ARRIVO_CREATO,
        operation_category=OperationCategory.MANUAL,
        status=OperationStatus.SUCCESS,
        details={
            'arrival_number': new_arrival.arrival_number,
            'supplier_name': new_arrival.supplier_name,
            'total_lines': len(consolidated_lines),
            'total_quantity': sum(consolidated_lines.values())
        }
    )
    db.commit()

    return new_arrival


@router.get("/", response_model=List[schemas.arrivals.Arrival])
def list_arrivals(
    include_completed: bool = False,
    db: Session = Depends(get_db)
):
    """Lista documenti arrivo"""
    query = db.query(models.arrivals.Arrival).options(
        joinedload(models.arrivals.Arrival.lines)
    )

    if not include_completed:
        query = query.filter(models.arrivals.Arrival.is_completed == False)

    return query.order_by(desc(models.arrivals.Arrival.created_date)).all()


@router.get("/completed/paginated")
def list_completed_arrivals_paginated(
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db)
):
    """Lista arrivi completati con paginazione"""
    # Conta totale per calcolare pagine
    total = db.query(models.arrivals.Arrival).filter(
        models.arrivals.Arrival.is_completed == True
    ).count()

    # Calcola offset
    offset = (page - 1) * per_page

    # Query paginata
    arrivals = db.query(models.arrivals.Arrival).filter(
        models.arrivals.Arrival.is_completed == True
    ).options(
        joinedload(models.arrivals.Arrival.lines)
    ).order_by(
        desc(models.arrivals.Arrival.completed_date)
    ).offset(offset).limit(per_page).all()

    # Calcola numero totale pagine
    total_pages = (total + per_page - 1) // per_page

    # Converti a dizionari per serializzazione JSON
    arrivals_data = []
    for arrival in arrivals:
        arrivals_data.append({
            "id": arrival.id,
            "arrival_number": arrival.arrival_number,
            "supplier_name": arrival.supplier_name,
            "completed_date": arrival.completed_date.isoformat() if arrival.completed_date else None,
            "lines": [
                {
                    "id": line.id,
                    "product_sku": line.product_sku,
                    "expected_quantity": line.expected_quantity,
                    "received_quantity": line.received_quantity
                }
                for line in arrival.lines
            ]
        })

    return {
        "arrivals": arrivals_data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages
        }
    }


# ==================== EXPORT ENDPOINTS ====================

@router.get("/export-excel")
async def export_arrivals_excel(
    from_date: Optional[date] = Query(None, description="Data inizio (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="Data fine (YYYY-MM-DD)"),
    include_drafts: bool = Query(False, description="Includi bozze non completate"),
    db: Session = Depends(get_db)
):
    """
    Esporta arrivi in formato Excel (sommario - una riga per documento).
    Di default filtra su completed_date, con include_drafts usa anche created_date.
    """
    if not EXCEL_AVAILABLE:
        raise HTTPException(status_code=500, detail="Export Excel non disponibile. Installare openpyxl.")

    try:
        # Query base con righe
        query = db.query(models.arrivals.Arrival).options(
            joinedload(models.arrivals.Arrival.lines)
        )

        # Applica filtri
        if include_drafts:
            # Includi bozze: filtra su created_date per le bozze
            if from_date:
                query = query.filter(
                    (models.arrivals.Arrival.completed_date >= from_date) |
                    ((models.arrivals.Arrival.completed_date == None) & (models.arrivals.Arrival.created_date >= from_date))
                )
            if to_date:
                query = query.filter(
                    (models.arrivals.Arrival.completed_date <= to_date) |
                    ((models.arrivals.Arrival.completed_date == None) & (models.arrivals.Arrival.created_date <= to_date))
                )
        else:
            # Solo completati: filtra su completed_date
            query = query.filter(models.arrivals.Arrival.is_completed == True)
            if from_date:
                query = query.filter(models.arrivals.Arrival.completed_date >= from_date)
            if to_date:
                query = query.filter(models.arrivals.Arrival.completed_date <= to_date)

        arrivals = query.order_by(desc(models.arrivals.Arrival.completed_date)).all()

        # Crea workbook Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Export Arrivi"

        # Headers
        headers = [
            "N° Documento", "Fornitore", "Data Arrivo", "Data Completamento",
            "N° Referenze", "Qtà Attesa", "Qtà Ricevuta", "Stato"
        ]

        # Styling headers
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="28a745", end_color="28a745", fill_type="solid")
        header_alignment = Alignment(horizontal="center")

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment

        # Popola dati
        for row, arrival in enumerate(arrivals, 2):
            # Calcola totali
            total_expected = sum(line.expected_quantity for line in arrival.lines)
            total_received = sum(line.received_quantity for line in arrival.lines)

            # Determina stato
            if arrival.is_completed:
                status = "Completato"
            elif arrival.is_draft:
                status = "Bozza"
            else:
                status = "In Lavorazione"

            # Popola riga
            ws.cell(row=row, column=1, value=arrival.arrival_number)
            ws.cell(row=row, column=2, value=arrival.supplier_name or "")
            ws.cell(row=row, column=3, value=arrival.arrival_date.strftime("%d/%m/%Y") if arrival.arrival_date else "")
            ws.cell(row=row, column=4, value=arrival.completed_date.strftime("%d/%m/%Y") if arrival.completed_date else "")
            ws.cell(row=row, column=5, value=len(arrival.lines))
            ws.cell(row=row, column=6, value=total_expected)
            ws.cell(row=row, column=7, value=total_received)
            ws.cell(row=row, column=8, value=status)

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

        filename = f"export_arrivi{date_suffix}.xlsx"

        return Response(
            content=buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'export Excel: {str(e)}")


@router.get("/export-pdf")
async def export_arrivals_pdf(
    from_date: Optional[date] = Query(None, description="Data inizio (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="Data fine (YYYY-MM-DD)"),
    include_drafts: bool = Query(False, description="Includi bozze non completate"),
    db: Session = Depends(get_db)
):
    """
    Esporta arrivi in formato PDF (sommario - una riga per documento).
    """
    try:
        # Query base con righe
        query = db.query(models.arrivals.Arrival).options(
            joinedload(models.arrivals.Arrival.lines)
        )

        # Applica filtri
        if include_drafts:
            if from_date:
                query = query.filter(
                    (models.arrivals.Arrival.completed_date >= from_date) |
                    ((models.arrivals.Arrival.completed_date == None) & (models.arrivals.Arrival.created_date >= from_date))
                )
            if to_date:
                query = query.filter(
                    (models.arrivals.Arrival.completed_date <= to_date) |
                    ((models.arrivals.Arrival.completed_date == None) & (models.arrivals.Arrival.created_date <= to_date))
                )
        else:
            query = query.filter(models.arrivals.Arrival.is_completed == True)
            if from_date:
                query = query.filter(models.arrivals.Arrival.completed_date >= from_date)
            if to_date:
                query = query.filter(models.arrivals.Arrival.completed_date <= to_date)

        arrivals = query.order_by(desc(models.arrivals.Arrival.completed_date)).all()

        # Crea PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=30)

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

        title = Paragraph(f"Export Arrivi{date_range}", title_style)
        story.append(title)
        story.append(Spacer(1, 12))

        # Prepara dati tabella
        table_data = []
        table_data.append(["N° Doc", "Fornitore", "Data Arrivo", "Completato", "Ref", "Attesa", "Ricevuta", "Stato"])

        for arrival in arrivals:
            total_expected = sum(line.expected_quantity for line in arrival.lines)
            total_received = sum(line.received_quantity for line in arrival.lines)

            if arrival.is_completed:
                status = "Completato"
            elif arrival.is_draft:
                status = "Bozza"
            else:
                status = "In Lav."

            table_data.append([
                arrival.arrival_number[:15] + "..." if len(arrival.arrival_number or "") > 18 else (arrival.arrival_number or ""),
                arrival.supplier_name[:15] + "..." if len(arrival.supplier_name or "") > 18 else (arrival.supplier_name or ""),
                arrival.arrival_date.strftime("%d/%m/%Y") if arrival.arrival_date else "",
                arrival.completed_date.strftime("%d/%m/%Y") if arrival.completed_date else "",
                str(len(arrival.lines)),
                str(total_expected),
                str(total_received),
                status
            ])

        # Crea tabella
        table = Table(table_data, colWidths=[1.0*inch, 1.2*inch, 0.8*inch, 0.8*inch, 0.4*inch, 0.5*inch, 0.6*inch, 0.7*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.16, 0.65, 0.27)),  # Verde
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
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

        filename = f"export_arrivi{date_suffix}.pdf"

        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'export PDF: {str(e)}")


@router.get("/export-products-excel")
async def export_arrivals_products_excel(
    from_date: Optional[date] = Query(None, description="Data inizio (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="Data fine (YYYY-MM-DD)"),
    include_drafts: bool = Query(False, description="Includi bozze non completate"),
    db: Session = Depends(get_db)
):
    """
    Esporta prodotti arrivati in formato Excel (dettagliato - una riga per prodotto-arrivo).
    """
    if not EXCEL_AVAILABLE:
        raise HTTPException(status_code=500, detail="Export Excel non disponibile. Installare openpyxl.")

    try:
        # Query base con righe e prodotti
        query = db.query(models.arrivals.Arrival).options(
            joinedload(models.arrivals.Arrival.lines).joinedload(models.arrivals.ArrivalLine.product)
        )

        # Applica filtri
        if include_drafts:
            if from_date:
                query = query.filter(
                    (models.arrivals.Arrival.completed_date >= from_date) |
                    ((models.arrivals.Arrival.completed_date == None) & (models.arrivals.Arrival.created_date >= from_date))
                )
            if to_date:
                query = query.filter(
                    (models.arrivals.Arrival.completed_date <= to_date) |
                    ((models.arrivals.Arrival.completed_date == None) & (models.arrivals.Arrival.created_date <= to_date))
                )
        else:
            query = query.filter(models.arrivals.Arrival.is_completed == True)
            if from_date:
                query = query.filter(models.arrivals.Arrival.completed_date >= from_date)
            if to_date:
                query = query.filter(models.arrivals.Arrival.completed_date <= to_date)

        arrivals = query.order_by(desc(models.arrivals.Arrival.completed_date)).all()

        if not arrivals:
            raise HTTPException(status_code=404, detail="Nessun arrivo trovato per il periodo specificato.")

        # Estrai tutte le righe prodotto
        product_lines = []
        for arrival in arrivals:
            for line in arrival.lines:
                product_lines.append({
                    'arrival_number': arrival.arrival_number,
                    'supplier_name': arrival.supplier_name,
                    'arrival_date': arrival.arrival_date,
                    'completed_date': arrival.completed_date,
                    'is_completed': arrival.is_completed,
                    'is_draft': arrival.is_draft,
                    'product_sku': line.product_sku,
                    'expected_quantity': line.expected_quantity,
                    'received_quantity': line.received_quantity,
                    'description': line.product.description if line.product else ""
                })

        if not product_lines:
            raise HTTPException(status_code=404, detail="Nessun prodotto trovato negli arrivi del periodo specificato.")

        # Crea workbook Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Prodotti Arrivati"

        # Headers
        headers = [
            "N° Documento", "Fornitore", "Data Arrivo", "Data Complet.",
            "SKU", "Descrizione", "Qtà Attesa", "Qtà Ricevuta", "Differenza", "Stato"
        ]

        # Styling headers
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="28a745", end_color="28a745", fill_type="solid")

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill

        # Popola dati
        for row, pl in enumerate(product_lines, 2):
            # Calcola differenza
            difference = pl['received_quantity'] - pl['expected_quantity']

            # Determina stato riga
            if pl['received_quantity'] == 0:
                riga_status = "Non Ricevuto"
            elif pl['received_quantity'] >= pl['expected_quantity']:
                riga_status = "Completo"
            else:
                riga_status = "Parziale"

            ws.cell(row=row, column=1, value=pl['arrival_number'])
            ws.cell(row=row, column=2, value=pl['supplier_name'] or "")
            ws.cell(row=row, column=3, value=pl['arrival_date'].strftime("%d/%m/%Y") if pl['arrival_date'] else "")
            ws.cell(row=row, column=4, value=pl['completed_date'].strftime("%d/%m/%Y") if pl['completed_date'] else "")
            ws.cell(row=row, column=5, value=pl['product_sku'])
            ws.cell(row=row, column=6, value=pl['description'] or "")
            ws.cell(row=row, column=7, value=pl['expected_quantity'])
            ws.cell(row=row, column=8, value=pl['received_quantity'])
            ws.cell(row=row, column=9, value=difference)
            ws.cell(row=row, column=10, value=riga_status)

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

        # Nome file
        filename = "export_prodotti_arrivi"
        if from_date or to_date:
            filename += f"_{from_date or 'inizio'}_{to_date or 'fine'}"
        filename += ".xlsx"

        return Response(
            content=buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'export Excel prodotti: {str(e)}")


@router.get("/export-products-pdf")
async def export_arrivals_products_pdf(
    from_date: Optional[date] = Query(None, description="Data inizio (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="Data fine (YYYY-MM-DD)"),
    include_drafts: bool = Query(False, description="Includi bozze non completate"),
    db: Session = Depends(get_db)
):
    """
    Esporta prodotti arrivati in formato PDF (dettagliato - una riga per prodotto-arrivo).
    """
    try:
        # Query base con righe e prodotti
        query = db.query(models.arrivals.Arrival).options(
            joinedload(models.arrivals.Arrival.lines).joinedload(models.arrivals.ArrivalLine.product)
        )

        # Applica filtri
        if include_drafts:
            if from_date:
                query = query.filter(
                    (models.arrivals.Arrival.completed_date >= from_date) |
                    ((models.arrivals.Arrival.completed_date == None) & (models.arrivals.Arrival.created_date >= from_date))
                )
            if to_date:
                query = query.filter(
                    (models.arrivals.Arrival.completed_date <= to_date) |
                    ((models.arrivals.Arrival.completed_date == None) & (models.arrivals.Arrival.created_date <= to_date))
                )
        else:
            query = query.filter(models.arrivals.Arrival.is_completed == True)
            if from_date:
                query = query.filter(models.arrivals.Arrival.completed_date >= from_date)
            if to_date:
                query = query.filter(models.arrivals.Arrival.completed_date <= to_date)

        arrivals = query.order_by(desc(models.arrivals.Arrival.completed_date)).all()

        if not arrivals:
            raise HTTPException(status_code=404, detail="Nessun arrivo trovato per il periodo specificato.")

        # Estrai tutte le righe prodotto
        product_lines = []
        for arrival in arrivals:
            for line in arrival.lines:
                product_lines.append({
                    'arrival_number': arrival.arrival_number,
                    'supplier_name': arrival.supplier_name,
                    'arrival_date': arrival.arrival_date,
                    'completed_date': arrival.completed_date,
                    'product_sku': line.product_sku,
                    'expected_quantity': line.expected_quantity,
                    'received_quantity': line.received_quantity,
                    'description': line.product.description if line.product else ""
                })

        if not product_lines:
            raise HTTPException(status_code=404, detail="Nessun prodotto trovato negli arrivi del periodo specificato.")

        # Crea PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=30)

        # Stili
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=14,
            spaceAfter=20,
            alignment=1
        )

        # Contenuto PDF
        story = []

        # Titolo
        period_text = ""
        if from_date or to_date:
            period_text = f" ({from_date or 'inizio'} - {to_date or 'fine'})"
        title = Paragraph(f"Report Prodotti Arrivati{period_text}", title_style)
        story.append(title)
        story.append(Spacer(1, 15))

        # Tabella
        table_data = [
            ['N° Doc', 'Fornitore', 'Data', 'SKU', 'Descrizione', 'Attesa', 'Ricevuta', 'Diff', 'Stato']
        ]

        for pl in product_lines:
            difference = pl['received_quantity'] - pl['expected_quantity']

            if pl['received_quantity'] == 0:
                riga_status = "Non Ric."
            elif pl['received_quantity'] >= pl['expected_quantity']:
                riga_status = "OK"
            else:
                riga_status = "Parziale"

            table_data.append([
                pl['arrival_number'][:10] + "..." if len(pl['arrival_number'] or "") > 13 else (pl['arrival_number'] or ""),
                pl['supplier_name'][:12] + "..." if len(pl['supplier_name'] or "") > 15 else (pl['supplier_name'] or ""),
                pl['arrival_date'].strftime("%d/%m/%y") if pl['arrival_date'] else "",
                pl['product_sku'][:10] + "..." if len(pl['product_sku'] or "") > 13 else (pl['product_sku'] or ""),
                (pl['description'][:15] + "..." if len(pl['description'] or "") > 18 else pl['description'] or ""),
                str(pl['expected_quantity']),
                str(pl['received_quantity']),
                str(difference) if difference != 0 else "0",
                riga_status
            ])

        # Crea tabella
        table = Table(table_data, colWidths=[55, 70, 45, 60, 90, 35, 40, 30, 45])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.16, 0.65, 0.27)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        story.append(table)

        # Genera PDF
        doc.build(story)
        pdf_content = buffer.getvalue()
        buffer.close()

        # Nome file
        filename = "export_prodotti_arrivi"
        if from_date or to_date:
            filename += f"_{from_date or 'inizio'}_{to_date or 'fine'}"
        filename += ".pdf"

        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'export PDF prodotti: {str(e)}")


@router.get("/{arrival_id}", response_model=schemas.arrivals.Arrival)
def get_arrival(
    arrival_id: int,
    db: Session = Depends(get_db)
):
    """Dettaglio documento arrivo"""
    arrival = db.query(models.arrivals.Arrival).filter(
        models.arrivals.Arrival.id == arrival_id
    ).options(
        joinedload(models.arrivals.Arrival.lines).joinedload(models.arrivals.ArrivalLine.product)
    ).first()

    if not arrival:
        raise HTTPException(status_code=404, detail="Documento non trovato")

    return arrival


@router.put("/{arrival_id}", response_model=schemas.arrivals.Arrival)
def update_arrival(
    arrival_id: int,
    update_data: schemas.arrivals.ArrivalUpdate,
    db: Session = Depends(get_db)
):
    """Modifica documento arrivo (solo se bozza)"""
    arrival = db.query(models.arrivals.Arrival).filter(
        models.arrivals.Arrival.id == arrival_id
    ).first()

    if not arrival:
        raise HTTPException(status_code=404, detail="Documento non trovato")

    if not arrival.is_draft:
        raise HTTPException(status_code=400, detail="Documento già confermato, non modificabile")

    # Aggiorna campi base
    if update_data.supplier_name:
        arrival.supplier_name = update_data.supplier_name
    if update_data.arrival_date:
        arrival.arrival_date = update_data.arrival_date
    if update_data.notes is not None:
        arrival.notes = update_data.notes

    # Aggiorna righe se fornite
    if update_data.lines:
        # Rimuovi righe esistenti
        db.query(models.arrivals.ArrivalLine).filter(
            models.arrivals.ArrivalLine.arrival_id == arrival_id
        ).delete()

        # Consolida nuove righe
        consolidated = {}
        for line in update_data.lines:
            if line.product_sku in consolidated:
                consolidated[line.product_sku] += line.expected_quantity
            else:
                consolidated[line.product_sku] = line.expected_quantity

        # Crea nuove righe
        for sku, qty in consolidated.items():
            new_line = models.arrivals.ArrivalLine(
                arrival_id=arrival_id,
                product_sku=sku,
                expected_quantity=qty,
                received_quantity=0
            )
            db.add(new_line)

    db.commit()
    db.refresh(arrival)

    # Log modifica
    logger = LoggingService(db)
    logger.log_operation(
        operation_type=OperationType.ARRIVO_MODIFICATO,
        operation_category=OperationCategory.MANUAL,
        status=OperationStatus.SUCCESS,
        details={'arrival_id': arrival_id, 'arrival_number': arrival.arrival_number}
    )
    db.commit()

    return arrival


@router.delete("/{arrival_id}")
def delete_arrival(
    arrival_id: int,
    db: Session = Depends(get_db)
):
    """Elimina documento arrivo (solo se bozza)"""
    arrival = db.query(models.arrivals.Arrival).filter(
        models.arrivals.Arrival.id == arrival_id
    ).first()

    if not arrival:
        raise HTTPException(status_code=404, detail="Documento non trovato")

    if not arrival.is_draft:
        raise HTTPException(status_code=400, detail="Documento già confermato, non eliminabile")

    arrival_number = arrival.arrival_number

    # Cancella (cascade elimina anche le righe)
    db.delete(arrival)
    db.commit()

    # Log eliminazione
    logger = LoggingService(db)
    logger.log_operation(
        operation_type=OperationType.ARRIVO_ELIMINATO,
        operation_category=OperationCategory.MANUAL,
        status=OperationStatus.SUCCESS,
        details={'arrival_id': arrival_id, 'arrival_number': arrival_number}
    )
    db.commit()

    return {"success": True, "message": f"Documento {arrival_number} eliminato"}


# ==================== CONFERMA DOCUMENTO (DESKTOP) ====================

@router.post("/confirm", response_model=schemas.arrivals.ArrivalConfirmResponse)
def confirm_arrival(
    confirm_request: schemas.arrivals.ArrivalConfirmRequest,
    db: Session = Depends(get_db)
):
    """
    Conferma documento arrivo:
    1. Applica modifiche se fornite (recap modificato)
    2. Carica tutte le quantità a ubicazione TERRA
    3. Logging completo operazione
    4. Marca documento come completato
    """
    logger = LoggingService(db)
    arrival_id = confirm_request.arrival_id

    # Carica documento
    arrival = db.query(models.arrivals.Arrival).filter(
        models.arrivals.Arrival.id == arrival_id
    ).options(
        joinedload(models.arrivals.Arrival.lines).joinedload(models.arrivals.ArrivalLine.product)
    ).first()

    if not arrival:
        raise HTTPException(status_code=404, detail="Documento non trovato")

    if not arrival.is_draft:
        raise HTTPException(status_code=400, detail="Documento già confermato")

    # Applica modifiche se fornite
    if confirm_request.modified_lines:
        for modified_line in confirm_request.modified_lines:
            line = db.query(models.arrivals.ArrivalLine).filter(
                and_(
                    models.arrivals.ArrivalLine.arrival_id == arrival_id,
                    models.arrivals.ArrivalLine.product_sku == modified_line.product_sku
                )
            ).first()

            if line:
                line.expected_quantity = modified_line.expected_quantity

        db.flush()

    # Ricarica righe aggiornate
    lines = db.query(models.arrivals.ArrivalLine).filter(
        models.arrivals.ArrivalLine.arrival_id == arrival_id
    ).all()

    # Consolida SKU duplicati (non dovrebbero esserci, ma per sicurezza)
    consolidated = {}
    for line in lines:
        if line.product_sku in consolidated:
            consolidated[line.product_sku] += line.expected_quantity
        else:
            consolidated[line.product_sku] = line.expected_quantity

    # Carica a TERRA con consolidamento
    terra_location = db.query(models.Location).filter(
        models.Location.name == "TERRA"
    ).first()

    if not terra_location:
        raise HTTPException(status_code=500, detail="Ubicazione TERRA non trovata")

    operations_logged = []
    operation_id = str(uuid.uuid4())

    for sku, qty in consolidated.items():
        # Trova o crea record inventario TERRA
        inventory = db.query(models.Inventory).filter(
            and_(
                models.Inventory.location_name == "TERRA",
                models.Inventory.product_sku == sku
            )
        ).first()

        if inventory:
            inventory.quantity += qty
        else:
            inventory = models.Inventory(
                location_name="TERRA",
                product_sku=sku,
                quantity=qty
            )
            db.add(inventory)

        # Log singola operazione
        operations_logged.append({
            'product_sku': sku,
            'location_to': 'TERRA',
            'quantity': qty,
            'status': OperationStatus.SUCCESS
        })

    # Log batch operazioni
    logger.log_file_operations(
        operation_type=OperationType.CARICO_ARRIVO,
        operation_category=OperationCategory.MANUAL,
        operations=operations_logged,
        file_name=f"ARRIVO_{arrival.arrival_number}",
        user_id="system"
    )

    # Marca documento come completato
    arrival.is_draft = False
    arrival.is_completed = True
    arrival.completed_date = datetime.now()

    # Aggiorna received_quantity = expected_quantity per tutte le righe
    for line in lines:
        line.received_quantity = line.expected_quantity

    try:
        db.commit()
        db.refresh(arrival)
    except Exception as e:
        db.rollback()
        logger.log_error(
            operation_type=OperationType.ARRIVO_CONFERMATO,
            error=str(e),
            operation_category=OperationCategory.MANUAL,
            details={'arrival_id': arrival_id}
        )
        raise HTTPException(status_code=500, detail="Errore conferma documento")

    # Log conferma documento
    logger.log_operation(
        operation_type=OperationType.ARRIVO_CONFERMATO,
        operation_category=OperationCategory.MANUAL,
        status=OperationStatus.SUCCESS,
        details={
            'arrival_id': arrival_id,
            'arrival_number': arrival.arrival_number,
            'supplier_name': arrival.supplier_name,
            'total_products': len(consolidated),
            'total_quantity': sum(consolidated.values())
        },
        operation_id=operation_id
    )
    db.commit()

    return schemas.arrivals.ArrivalConfirmResponse(
        success=True,
        message=f"Documento {arrival.arrival_number} confermato. {len(operations_logged)} prodotti caricati a TERRA.",
        operations_logged=len(operations_logged),
        arrival=arrival
    )


# ==================== MOBILE SCANNER REAL-TIME ====================

@router.post("/validate-ean", response_model=schemas.arrivals.ArrivalScanValidationResponse)
def validate_ean_for_arrival(
    validation: schemas.arrivals.ArrivalScanValidation,
    db: Session = Depends(get_db)
):
    """
    Valida EAN scansionato da mobile:
    - Converte EAN → SKU
    - Verifica se SKU è nel documento arrivo
    - Ritorna info prodotto e progress
    """
    arrival_id = validation.arrival_id
    ean_code = validation.ean_code.strip()

    # Carica documento
    arrival = db.query(models.arrivals.Arrival).filter(
        models.arrivals.Arrival.id == arrival_id
    ).options(
        joinedload(models.arrivals.Arrival.lines).joinedload(models.arrivals.ArrivalLine.product)
    ).first()

    if not arrival:
        return schemas.arrivals.ArrivalScanValidationResponse(
            valid=False,
            message="Documento non trovato"
        )

    if not arrival.is_draft:
        return schemas.arrivals.ArrivalScanValidationResponse(
            valid=False,
            message="Documento già confermato"
        )

    # Converti EAN → SKU
    product_sku = None

    # Prova come SKU diretto
    product = db.query(models.Product).filter(
        models.Product.sku == ean_code
    ).first()

    if product:
        product_sku = product.sku
    else:
        # Prova come EAN
        ean = db.query(models.EanCode).filter(
            models.EanCode.ean == ean_code
        ).first()

        if ean:
            product_sku = ean.product_sku
            product = db.query(models.Product).filter(
                models.Product.sku == product_sku
            ).first()

    if not product_sku:
        return schemas.arrivals.ArrivalScanValidationResponse(
            valid=False,
            message=f"EAN {ean_code} non trovato nel database"
        )

    # Verifica se SKU è nel documento
    line = None
    for arrival_line in arrival.lines:
        if arrival_line.product_sku == product_sku:
            line = arrival_line
            break

    unexpected_code = False
    new_line_created = False

    if not line:
        # Se allow_unexpected, crea nuova riga
        if validation.allow_unexpected:
            # Crea nuova ArrivalLine per questo prodotto non atteso
            line = models.arrivals.ArrivalLine(
                arrival_id=arrival.id,
                product_sku=product_sku,
                expected_quantity=0,  # Non era atteso
                received_quantity=0   # Non ancora ricevuto
            )
            db.add(line)
            db.commit()
            db.refresh(line)

            unexpected_code = True
            new_line_created = True

            # Log operazione
            from wms_app.services.logging_service import LoggingService
            from wms_app.models.logs import OperationType, OperationCategory

            logging_service = LoggingService(db)
            logging_service.log_operation(
                operation_type=OperationType.ARRIVO_CODE_UNEXPECTED_ADDED,
                category=OperationCategory.MANUAL,
                product_sku=product_sku,
                quantity=0,
                details={
                    "arrival_id": arrival.id,
                    "arrival_number": arrival.arrival_number,
                    "product_description": product.description if product else ""
                }
            )
        else:
            return schemas.arrivals.ArrivalScanValidationResponse(
                valid=False,
                product_sku=product_sku,
                message=f"Prodotto {product_sku} NON previsto in questo documento"
            )

    # Calcola progress
    progress = (line.received_quantity / line.expected_quantity * 100) if line.expected_quantity > 0 else 0

    return schemas.arrivals.ArrivalScanValidationResponse(
        valid=True,
        product_sku=product_sku,
        product_description=product.description if product else "",
        expected_quantity=line.expected_quantity,
        received_quantity=line.received_quantity,
        progress_percentage=round(progress, 1),
        message=f"OK - {line.received_quantity}/{line.expected_quantity}",
        unexpected_code=unexpected_code,
        new_line_created=new_line_created
    )


@router.post("/scan-confirm", response_model=schemas.arrivals.ArrivalScanConfirmResponse)
def confirm_scan(
    scan_confirm: schemas.arrivals.ArrivalScanConfirm,
    db: Session = Depends(get_db)
):
    """
    Conferma quantità scansionata da mobile:
    - Incrementa received_quantity
    - Auto-save a database
    - Ritorna progress aggiornato
    """
    logger = LoggingService(db)
    arrival_id = scan_confirm.arrival_id
    product_sku = scan_confirm.product_sku
    quantity = scan_confirm.quantity

    # Trova riga documento
    line = db.query(models.arrivals.ArrivalLine).filter(
        and_(
            models.arrivals.ArrivalLine.arrival_id == arrival_id,
            models.arrivals.ArrivalLine.product_sku == product_sku
        )
    ).first()

    if not line:
        raise HTTPException(status_code=404, detail="Riga documento non trovata")

    # Incrementa received_quantity
    line.received_quantity += quantity

    # Calcola progress
    progress = (line.received_quantity / line.expected_quantity * 100) if line.expected_quantity > 0 else 0

    # Verifica se tutto il documento è completato
    arrival = db.query(models.arrivals.Arrival).filter(
        models.arrivals.Arrival.id == arrival_id
    ).options(
        joinedload(models.arrivals.Arrival.lines)
    ).first()

    all_completed = all(
        line.received_quantity >= line.expected_quantity
        for line in arrival.lines
    )

    try:
        db.commit()
        db.refresh(line)
    except Exception as e:
        db.rollback()
        logger.log_error(
            operation_type=OperationType.ARRIVO_SCAN_MOBILE,
            error=str(e),
            operation_category=OperationCategory.MANUAL,
            product_sku=product_sku,
            details={'arrival_id': arrival_id, 'quantity': quantity}
        )
        raise HTTPException(status_code=500, detail="Errore salvataggio scansione")

    # Log scansione mobile
    logger.log_operation(
        operation_type=OperationType.ARRIVO_SCAN_MOBILE,
        operation_category=OperationCategory.MANUAL,
        status=OperationStatus.SUCCESS,
        product_sku=product_sku,
        quantity=quantity,
        details={
            'arrival_id': arrival_id,
            'arrival_number': arrival.arrival_number,
            'received_quantity': line.received_quantity,
            'expected_quantity': line.expected_quantity,
            'progress': round(progress, 1)
        }
    )
    db.commit()

    return schemas.arrivals.ArrivalScanConfirmResponse(
        success=True,
        message=f"Scansionato {quantity} unità",
        received_quantity=line.received_quantity,
        expected_quantity=line.expected_quantity,
        progress_percentage=round(progress, 1),
        all_completed=all_completed
    )


@router.post("/{arrival_id}/update-quantity", response_model=schemas.arrivals.ManualQuantityUpdateResponse)
def update_manual_quantity(
    arrival_id: int,
    update: schemas.arrivals.ManualQuantityUpdate,
    db: Session = Depends(get_db)
):
    """
    Aggiorna manualmente la quantità ricevuta per un prodotto:
    - Trova ArrivalLine per SKU
    - Aggiorna received_quantity con row lock
    - Logga operazione ARRIVO_QUANTITY_MANUAL_UPDATE
    - Ritorna nuovo totale
    """
    logger = LoggingService(db)
    product_sku = update.product_sku
    new_quantity = update.received_quantity

    # Trova riga documento con pessimistic lock per concorrenza
    line = db.query(models.arrivals.ArrivalLine).filter(
        and_(
            models.arrivals.ArrivalLine.arrival_id == arrival_id,
            models.arrivals.ArrivalLine.product_sku == product_sku
        )
    ).with_for_update().first()

    if not line:
        raise HTTPException(status_code=404, detail="Riga documento non trovata")

    # Salva valore precedente per log
    old_quantity = line.received_quantity

    # Aggiorna quantità
    line.received_quantity = new_quantity

    # Calcola progress
    progress = (line.received_quantity / line.expected_quantity * 100) if line.expected_quantity > 0 else 0

    # Ottieni info arrival per log
    arrival = db.query(models.arrivals.Arrival).filter(
        models.arrivals.Arrival.id == arrival_id
    ).first()

    try:
        db.commit()
        db.refresh(line)
    except Exception as e:
        db.rollback()
        logger.log_error(
            operation_type=OperationType.ARRIVO_QUANTITY_MANUAL_UPDATE,
            error=str(e),
            operation_category=OperationCategory.MANUAL,
            product_sku=product_sku,
            details={'arrival_id': arrival_id, 'new_quantity': new_quantity}
        )
        raise HTTPException(status_code=500, detail="Errore salvataggio quantità")

    # Log modifica manuale
    logger.log_operation(
        operation_type=OperationType.ARRIVO_QUANTITY_MANUAL_UPDATE,
        operation_category=OperationCategory.MANUAL,
        status=OperationStatus.SUCCESS,
        product_sku=product_sku,
        quantity=new_quantity,
        details={
            'arrival_id': arrival_id,
            'arrival_number': arrival.arrival_number if arrival else None,
            'old_quantity': old_quantity,
            'new_quantity': new_quantity,
            'expected_quantity': line.expected_quantity,
            'progress': round(progress, 1)
        }
    )
    db.commit()

    return schemas.arrivals.ManualQuantityUpdateResponse(
        success=True,
        message=f"Quantità aggiornata a {new_quantity}",
        product_sku=product_sku,
        received_quantity=line.received_quantity,
        expected_quantity=line.expected_quantity,
        progress_percentage=round(progress, 1)
    )


@router.post("/{arrival_id}/finalize", response_model=schemas.arrivals.FinalizeResponse)
def finalize_arrival(
    arrival_id: int,
    request: schemas.arrivals.FinalizeRequest = schemas.arrivals.FinalizeRequest(),
    db: Session = Depends(get_db)
):
    """
    Finalizza precarico con controllo discrepanze:
    - Calcola discrepanze (received != expected per ogni riga)
    - Se discrepanze > 0 E force=False: ritorna lista warnings + ask_confirmation=True
    - Se confermato O no discrepanze: conferma documento e carica a TERRA
    - Ritorna success con totali caricati
    """
    # Carica documento con righe
    arrival = db.query(models.arrivals.Arrival).filter(
        models.arrivals.Arrival.id == arrival_id
    ).options(
        joinedload(models.arrivals.Arrival.lines).joinedload(models.arrivals.ArrivalLine.product)
    ).first()

    if not arrival:
        raise HTTPException(status_code=404, detail="Documento non trovato")

    if not arrival.is_draft:
        raise HTTPException(status_code=400, detail="Documento già confermato")

    # Calcola discrepanze
    discrepancies = []
    for line in arrival.lines:
        if line.received_quantity != line.expected_quantity:
            discrepancy = schemas.arrivals.DiscrepancyInfo(
                product_sku=line.product_sku,
                product_description=line.product.description if line.product else "",
                expected=line.expected_quantity,
                received=line.received_quantity,
                difference=line.received_quantity - line.expected_quantity
            )
            discrepancies.append(discrepancy)

    # Se ci sono discrepanze e non è forzato, chiedi conferma
    if discrepancies and not request.force:
        return schemas.arrivals.FinalizeResponse(
            success=False,
            message="Discrepanze rilevate",
            ask_confirmation=True,
            discrepancies=discrepancies
        )

    # Conferma documento (usa endpoint esistente)
    confirm_request = schemas.arrivals.ArrivalConfirmRequest(
        arrival_id=arrival_id,
        modified_lines=None  # Usa quantità attuali
    )

    try:
        # Chiama logica di conferma esistente
        confirm_response = confirm_arrival(confirm_request, db)

        return schemas.arrivals.FinalizeResponse(
            success=True,
            message="Precarico finalizzato e caricato a TERRA",
            ask_confirmation=False,
            discrepancies=discrepancies,  # Includi anche se confermato
            operations_logged=confirm_response.operations_logged,
            total_loaded_to_terra=sum(line.received_quantity for line in arrival.lines)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore finalizzazione: {str(e)}")
