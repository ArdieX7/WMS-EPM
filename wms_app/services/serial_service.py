import re
import uuid
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from wms_app.models.serials import ProductSerial, SerialValidationReport
from wms_app.models.products import Product, EanCode
from wms_app.models.orders import Order, OrderLine
from wms_app.schemas.serials import (
    SerialUploadResult, SerialValidationSummary, SerialValidationError,
    OrderSerialsView
)

class SerialService:
    """
    Servizio per la gestione dei seriali prodotto
    Gestisce upload, validazione e controllo qualità seriali
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    
    def parse_serial_file(self, file_content: str, uploaded_by: str = None) -> SerialUploadResult:
        """
        Parser del file seriali con formato scanner: ogni elemento su una riga
        
        Formato:
        ORDINE
        EAN
        SERIALE
        EAN  
        SERIALE
        ORDINE
        EAN
        SERIALE
        ...
        
        Args:
            file_content: Contenuto del file come stringa
            uploaded_by: Utente che ha caricato il file
            
        Returns:
            SerialUploadResult con esito parsing e eventuali errori
        """
        upload_batch_id = str(uuid.uuid4())
        lines = [line.strip() for line in file_content.strip().split('\n') if line.strip()]
        
        total_serials_found = 0
        total_orders_found = 0
        errors = []
        warnings = []
        
        # Cache per EAN codes per performance
        ean_to_sku_map = self._build_ean_to_sku_map()
        
        try:
            result = self._parse_scanner_format(lines, ean_to_sku_map, upload_batch_id, uploaded_by)
            
            # Commit sempre i seriali validi, anche se ci sono errori
            self.db.commit()
            
            # Determina successo basato su se almeno alcuni seriali sono stati inseriti
            success = result['serials_count'] > 0
            
            if result['errors'] and not success:
                # Nessun seriale inserito a causa di errori critici
                message = f"Nessun seriale caricato. {len(result['errors'])} errori critici trovati."
            elif result['errors'] and success:
                # Alcuni seriali inseriti, ma con avvisi
                message = f"Upload parziale completato. {result['serials_count']} seriali caricati, {len(result['errors'])} problemi trovati. Verificare la validazione per ordine."
            else:
                # Tutto ok
                message = f"File elaborato con successo. {result['serials_count']} seriali trovati per {result['orders_count']} ordini."
            
            return SerialUploadResult(
                success=success,
                message=message,
                upload_batch_id=upload_batch_id,
                total_lines_processed=len(lines),
                total_serials_found=result['serials_count'],
                total_orders_found=result['orders_count'],
                errors=result['errors'],
                warnings=warnings
            )
            
        except Exception as e:
            self.db.rollback()
            return SerialUploadResult(
                success=False,
                message=f"Errore critico durante il parsing: {str(e)}",
                total_lines_processed=len(lines),
                total_serials_found=0,
                total_orders_found=0,
                errors=[str(e)]
            )
    
    def _parse_scanner_format(self, lines: List[str], ean_to_sku_map: Dict[str, str], 
                             upload_batch_id: str, uploaded_by: str) -> Dict:
        """
        Parser specifico per formato scanner (ogni elemento su una riga)
        
        Logica:
        - Se la riga è un numero ordine (1-10 cifre), diventa il current_order
        - Se la riga è un EAN esistente, diventa il current_ean
        - Altrimenti è un seriale da associare al current_ean e current_order
        """
        current_order = None
        current_ean = None
        serials_count = 0
        orders_found = set()
        errors = []
        serials_in_file = set()  # Traccia seriali già processati in questo file
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Verifica se è un numero ordine
            if self._is_valid_order_number(line):
                current_order = line
                current_ean = None  # Reset EAN quando cambia ordine
                orders_found.add(line)
                continue
            
            # Verifica se è un EAN code esistente
            if line in ean_to_sku_map:
                if current_order is None:
                    errors.append(f"Riga {line_num}: EAN '{line}' trovato senza numero ordine precedente")
                    continue
                current_ean = line
                continue
            
            # Altrimenti è un seriale
            if current_order is None:
                errors.append(f"Riga {line_num}: Seriale '{line}' trovato senza numero ordine")
                continue
            
            if current_ean is None:
                errors.append(f"Riga {line_num}: Seriale '{line}' trovato senza EAN code")
                continue
            
            # Crea il seriale
            sku = ean_to_sku_map[current_ean]
            
            # Verifica duplicati seriali (globalmente univoci)
            existing_serial = self.db.query(ProductSerial).filter(
                ProductSerial.serial_number == line
            ).first()
            
            if existing_serial:
                errors.append(f"Riga {line_num}: Seriale '{line}' già esistente nel sistema (SKU: {existing_serial.product_sku}, Ordine: {existing_serial.order_number})")
                continue
            
            # Verifica duplicati nel file corrente
            if line in serials_in_file:
                errors.append(f"Riga {line_num}: Seriale '{line}' duplicato nel file corrente")
                continue
            
            # Crea record seriale
            product_serial = ProductSerial(
                order_number=current_order,
                product_sku=sku,
                ean_code=current_ean,
                serial_number=line,
                upload_batch_id=upload_batch_id,
                uploaded_by=uploaded_by,
                validation_status="pending"
            )
            
            self.db.add(product_serial)
            serials_in_file.add(line)  # Traccia il seriale come processato
            serials_count += 1
        
        return {
            'serials_count': serials_count,
            'orders_count': len(orders_found),
            'errors': errors
        }
    
    def _is_valid_order_number(self, order_str: str) -> bool:
        """Verifica se la stringa è un numero ordine valido (1-10 cifre)"""
        return bool(re.match(r'^\d{1,10}$', order_str))
    
    def _build_ean_to_sku_map(self) -> Dict[str, str]:
        """Costruisce mappa EAN -> SKU per performance"""
        ean_codes = self.db.query(EanCode).all()
        return {ean.ean: ean.product_sku for ean in ean_codes}
    
    def _find_duplicate_serials_for_order(self, order_number: str, upload_batch_id: str = None) -> List[Dict]:
        """Trova seriali duplicati per un ordine specifico"""
        # Query per duplicati nell'ordine
        query = self.db.query(
            ProductSerial.serial_number,
            ProductSerial.product_sku,
            func.count(ProductSerial.id).label('count')
        ).filter(
            ProductSerial.order_number == order_number
        )
        
        if upload_batch_id:
            query = query.filter(ProductSerial.upload_batch_id == upload_batch_id)
        
        duplicates = query.group_by(
            ProductSerial.serial_number,
            ProductSerial.product_sku
        ).having(
            func.count(ProductSerial.id) > 1
        ).all()
        
        return [
            {
                'serial_number': serial_number,
                'sku': sku,
                'count': count
            }
            for serial_number, sku, count in duplicates
        ]
    
    def validate_serials_for_order(self, order_number: str, upload_batch_id: str = None) -> SerialValidationSummary:
        """
        Valida i seriali di un ordine confrontandoli con l'ordine originale
        """
        # Trova ordine nel sistema
        order = self.db.query(Order).filter(Order.order_number == order_number).first()
        
        # Trova seriali caricati
        serials_query = self.db.query(ProductSerial).filter(
            ProductSerial.order_number == order_number
        )
        if upload_batch_id:
            serials_query = serials_query.filter(ProductSerial.upload_batch_id == upload_batch_id)
        
        serials = serials_query.all()
        
        # Raggruppa seriali per SKU
        found_serials_by_sku = {}
        for serial in serials:
            if serial.product_sku not in found_serials_by_sku:
                found_serials_by_sku[serial.product_sku] = []
            found_serials_by_sku[serial.product_sku].append(serial.serial_number)
        
        # Ottieni quantità attese dall'ordine
        expected_quantities = {}
        if order:
            for line in order.lines:
                expected_quantities[line.product_sku] = line.requested_quantity
        
        # Calcola statistiche
        total_serials_found = len(serials)
        total_serials_expected = sum(expected_quantities.values()) if expected_quantities else 0
        
        # Analizza errori
        errors = []
        missing_products = []
        extra_products = []
        quantity_mismatches = {}
        
        has_quantity_mismatch = False
        has_wrong_products = False
        has_duplicate_serials = False
        
        # Verifica prodotti mancanti
        for sku, expected_qty in expected_quantities.items():
            found_qty = len(found_serials_by_sku.get(sku, []))
            
            if found_qty == 0:
                missing_products.append(sku)
                errors.append(SerialValidationError(
                    error_type="missing_product",
                    order_number=order_number,
                    sku=sku,
                    expected_quantity=expected_qty,
                    found_quantity=0,
                    message=f"Prodotto {sku} mancante. Attesi {expected_qty} seriali, trovati 0."
                ))
            elif found_qty != expected_qty:
                has_quantity_mismatch = True
                quantity_mismatches[sku] = {"expected": expected_qty, "found": found_qty}
                errors.append(SerialValidationError(
                    error_type="quantity_mismatch",
                    order_number=order_number,
                    sku=sku,
                    expected_quantity=expected_qty,
                    found_quantity=found_qty,
                    message=f"Quantità errata per {sku}. Attesi {expected_qty}, trovati {found_qty}."
                ))
        
        # Verifica prodotti extra (non nell'ordine)
        for sku in found_serials_by_sku.keys():
            if sku not in expected_quantities:
                has_wrong_products = True
                extra_products.append(sku)
                errors.append(SerialValidationError(
                    error_type="wrong_product",
                    order_number=order_number,
                    sku=sku,
                    found_quantity=len(found_serials_by_sku[sku]),
                    message=f"Prodotto {sku} non presente nell'ordine originale."
                ))
        
        # Verifica duplicati per questo ordine specifico
        duplicate_serials = self._find_duplicate_serials_for_order(order_number, upload_batch_id)
        if duplicate_serials:
            has_duplicate_serials = True
            for duplicate in duplicate_serials:
                errors.append(SerialValidationError(
                    error_type="duplicate_serial",
                    order_number=order_number,
                    sku=duplicate['sku'],
                    message=f"Seriale '{duplicate['serial_number']}' duplicato {duplicate['count']} volte per prodotto {duplicate['sku']}"
                ))
        
        # Determina stato generale
        if not order:
            overall_status = "invalid"
            errors.append(SerialValidationError(
                error_type="order_not_found",
                order_number=order_number,
                message=f"Ordine {order_number} non trovato nel sistema."
            ))
        elif errors:
            overall_status = "invalid"
        elif has_quantity_mismatch or has_wrong_products or has_duplicate_serials:
            overall_status = "warning"
        else:
            overall_status = "valid"
        
        return SerialValidationSummary(
            order_number=order_number,
            total_serials_found=total_serials_found,
            total_serials_expected=total_serials_expected,
            valid_serials=total_serials_found if overall_status == "valid" else 0,
            invalid_serials=total_serials_found if overall_status == "invalid" else 0,
            overall_status=overall_status,
            has_quantity_mismatch=has_quantity_mismatch,
            has_unknown_ean=False,  # Già controllato durante upload
            has_wrong_products=has_wrong_products,
            has_duplicate_serials=has_duplicate_serials,
            errors=errors,
            missing_products=missing_products,
            extra_products=extra_products,
            quantity_mismatches=quantity_mismatches
        )
    
    def get_orders_with_serials(self) -> List[OrderSerialsView]:
        """
        Ottiene lista ordini con seriali caricati
        """
        # Query per ottenere ordini con seriali
        orders_with_serials = self.db.query(ProductSerial.order_number).distinct().all()
        
        results = []
        for (order_number,) in orders_with_serials:
            order_view = self.get_order_serials_view(order_number)
            results.append(order_view)
        
        return results
    
    def check_serial_exists(self, serial_number: str) -> Optional[ProductSerial]:
        """
        Verifica se un seriale esiste già nel sistema
        
        Returns:
            ProductSerial se esiste, None altrimenti
        """
        return self.db.query(ProductSerial).filter(
            ProductSerial.serial_number == serial_number
        ).first()
    
    def get_duplicate_serials_in_system(self) -> List[Dict]:
        """
        Trova tutti i seriali duplicati nel sistema
        """
        # Query per trovare seriali duplicati
        duplicate_serials = self.db.query(
            ProductSerial.serial_number,
            func.count(ProductSerial.id).label('count')
        ).group_by(
            ProductSerial.serial_number
        ).having(
            func.count(ProductSerial.id) > 1
        ).all()
        
        result = []
        for serial_number, count in duplicate_serials:
            # Ottieni dettagli di tutti i record con questo seriale
            records = self.db.query(ProductSerial).filter(
                ProductSerial.serial_number == serial_number
            ).all()
            
            result.append({
                'serial_number': serial_number,
                'duplicate_count': count,
                'records': [
                    {
                        'id': r.id,
                        'order_number': r.order_number,
                        'product_sku': r.product_sku,
                        'ean_code': r.ean_code,
                        'upload_batch_id': r.upload_batch_id,
                        'uploaded_at': r.uploaded_at
                    } for r in records
                ]
            })
        
        return result
    
    def get_order_serials_view(self, order_number: str) -> OrderSerialsView:
        """
        Vista dettagliata seriali per un ordine specifico
        """
        # Trova ordine nel sistema
        order = self.db.query(Order).filter(Order.order_number == order_number).first()
        
        # Trova seriali
        serials = self.db.query(ProductSerial).filter(
            ProductSerial.order_number == order_number
        ).all()
        
        # Raggruppa seriali per SKU
        found_serials = {}
        last_upload_date = None
        for serial in serials:
            if serial.product_sku not in found_serials:
                found_serials[serial.product_sku] = []
            found_serials[serial.product_sku].append(serial.serial_number)
            
            if last_upload_date is None or serial.uploaded_at > last_upload_date:
                last_upload_date = serial.uploaded_at
        
        # Ottieni quantità attese
        expected_products = {}
        order_status = None
        if order:
            order_status = "completed" if order.is_completed else "open"
            for line in order.lines:
                expected_products[line.product_sku] = line.requested_quantity
        
        # Genera validazione
        validation_summary = None
        if serials:
            validation_summary = self.validate_serials_for_order(order_number)
        
        return OrderSerialsView(
            order_number=order_number,
            order_exists=order is not None,
            order_status=order_status,
            expected_products=expected_products,
            found_serials=found_serials,
            validation_summary=validation_summary,
            last_upload_date=last_upload_date
        )