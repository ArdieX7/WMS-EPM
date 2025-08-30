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
    OrderSerialsView, SerialParseResult, SerialRecapItem, SerialCommitRequest
)
from wms_app.services.logging_service import LoggingService
from wms_app.models.logs import OperationType, OperationCategory, OperationStatus

class SerialService:
    """
    Servizio per la gestione dei seriali prodotto
    Gestisce upload, validazione e controllo qualità seriali
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    
    def parse_serial_file(self, file_content: str, uploaded_by: str = None, file_name: str = None) -> SerialUploadResult:
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
            
            # Log delle operazioni seriali caricati con successo - una per ordine
            if result['serials_count'] > 0 and result['operations']:
                logger = LoggingService(self.db)
                
                for operation in result['operations']:
                    logger.log_operation(
                        operation_type=OperationType.SERIALI_ASSEGNATI,
                        operation_category=OperationCategory.FILE,
                        status=operation['status'],
                        product_sku=operation['product_sku'],  # None per i seriali
                        quantity=operation['quantity'],
                        user_id=uploaded_by or "file_user",
                        file_name=file_name,  # Nome file rimane per tracciabilità
                        file_line_number=operation['line_number'],
                        details=operation['details']  # Qui ci sono già i dettagli con order_number
                    )
                
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
        order_operations = {}  # Operazioni raggruppate per ordine per il logging
        
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
            
            # Traccia seriali per ordine per il logging
            if current_order not in order_operations:
                order_operations[current_order] = {
                    'success_count': 0,
                    'serials': [],
                    'first_line': line_num
                }
            
            order_operations[current_order]['success_count'] += 1
            order_operations[current_order]['serials'].append({
                'serial_number': line,
                'sku': sku,
                'ean_code': current_ean
            })
        
        # Crea operazioni per il logging - una per ordine
        operations = []
        for order_number, order_data in order_operations.items():
            operations.append({
                'status': OperationStatus.SUCCESS,
                'product_sku': None,  # Vuoto come richiesto
                'quantity': order_data['success_count'],  # Numero di seriali creati per questo ordine
                'line_number': order_data['first_line'],
                'details': {
                    'order_number': order_number,
                    'serials_created': order_data['success_count'],
                    'serials_list': order_data['serials'],
                    'upload_batch_id': upload_batch_id
                }
            })
        
        return {
            'serials_count': serials_count,
            'orders_count': len(orders_found),
            'errors': errors,
            'operations': operations
        }
    
    def _is_valid_order_number(self, order_str: str) -> bool:
        """Verifica se la stringa è un numero ordine valido (1-10 cifre)"""
        return bool(re.match(r'^\d{1,10}$', order_str))
    
    def _build_ean_to_sku_map(self) -> Dict[str, str]:
        """Costruisce mappa EAN -> SKU per performance"""
        ean_codes = self.db.query(EanCode).all()
        return {ean.ean: ean.product_sku for ean in ean_codes}
    
    def parse_serial_file_with_recap(self, file_content: str, file_name: str = None) -> SerialParseResult:
        """
        Parser del file seriali per sistema recap modificabile.
        Non esegue commit, restituisce solo il recap per validazione.
        """
        lines = [line.strip() for line in file_content.strip().split('\n') if line.strip()]
        
        # Cache per performance
        ean_to_sku_map = self._build_ean_to_sku_map()
        orders_cache = self._build_orders_cache()
        
        # Parse con validazioni complete
        result = self._parse_with_full_validation(lines, ean_to_sku_map, orders_cache)
        
        # Costruisci statistiche
        stats = {
            'total': len(result['recap_items']),
            'ok': len([item for item in result['recap_items'] if item['status'] == 'ok']),
            'warnings': len(result['warnings']),
            'errors': len(result['errors'])
        }
        
        return SerialParseResult(
            success=len(result['recap_items']) > 0,
            message=self._generate_parse_message(result, stats),
            file_name=file_name,
            total_lines_processed=len(lines),
            recap_items=[SerialRecapItem(**item) for item in result['recap_items']],
            errors=result['errors'],
            warnings=result['warnings'],
            stats=stats,
            orders_summary=result['orders_summary']
        )
    
    def _build_orders_cache(self) -> Dict[str, Dict]:
        """Costruisce cache degli ordini per validazione"""
        orders = self.db.query(Order).all()
        orders_cache = {}
        
        for order in orders:
            # Carica anche le righe ordine per validazione prodotti
            order_lines = self.db.query(OrderLine).filter(OrderLine.order_id == order.id).all()
            expected_skus = {line.product_sku: line.requested_quantity for line in order_lines}
            
            orders_cache[order.order_number] = {
                'order': order,
                'customer_name': order.customer_name,
                'expected_skus': expected_skus,
                'order_lines': order_lines
            }
        
        return orders_cache
    
    def _looks_like_ean(self, line: str) -> bool:
        """
        Verifica se una stringa sembra un EAN code più restrittivo
        Un EAN dovrebbe avere un formato riconoscibile (es: contiene trattini, 
        inizia con lettere, ha pattern specifici)
        """
        # Non deve essere un numero ordine (solo cifre 1-10)
        if self._is_valid_order_number(line):
            return False
        
        # Pattern più specifici per EAN codes
        # Deve contenere trattini E lettere (formato tipico SKU/EAN)
        has_dash = '-' in line
        has_letter = any(c.isalpha() for c in line)
        has_number = any(c.isdigit() for c in line)
        
        # Lunghezza minima e massima ragionevoli per EAN
        reasonable_length = 5 <= len(line) <= 20
        
        # Deve avere pattern EAN-like: lettere+numeri+trattini
        ean_pattern = has_dash and has_letter and has_number and reasonable_length
        
        # Esclude stringhe che sembrano seriali semplici (solo lettere+numeri senza struttura)
        looks_like_simple_serial = not has_dash and len(line) < 15 and any(c.isalpha() for c in line) and any(c.isdigit() for c in line)
        
        return ean_pattern and not looks_like_simple_serial
    
    def _parse_with_full_validation(self, lines: List[str], ean_to_sku_map: Dict[str, str], 
                                   orders_cache: Dict[str, Dict]) -> Dict:
        """
        Parser con validazioni complete per sistema recap
        Implementa tutta la logica di controllo: duplicati, confronto SKU ordine, gestione errori operatore
        """
        current_order = None
        current_ean = None
        recap_items = []
        errors = []
        warnings = []
        orders_summary = {}
        serials_in_file = set()  # Per controllo duplicati
        existing_serials_db = set()  # Cache seriali esistenti in database
        
        # Pre-carica tutti i seriali esistenti per performance
        existing_serials = self.db.query(ProductSerial.serial_number).all()
        existing_serials_db = {serial[0] for serial in existing_serials}
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # 1. CONTROLLO NUMERO ORDINE
            if self._is_valid_order_number(line):
                current_order = line
                current_ean = None  # Reset EAN quando cambia ordine
                
                # Validazione ordine esistente
                if line not in orders_cache:
                    errors.append(f"Riga {line_num}: Ordine '{line}' non trovato nel sistema")
                    current_order = None
                else:
                    # Inizializza summary ordine
                    if line not in orders_summary:
                        orders_summary[line] = {
                            'customer_name': orders_cache[line]['customer_name'],
                            'serials_count': 0,
                            'expected_products': orders_cache[line]['expected_skus'],
                            'found_skus': {}  # Traccia SKU trovati vs attesi
                        }
                continue
            
            # 2. CONTROLLO EAN CODE
            if line in ean_to_sku_map:
                if current_order is None:
                    errors.append(f"Riga {line_num}: EAN '{line}' trovato senza numero ordine precedente")
                    # Crea item per permettere correzione
                    recap_items.append({
                        'line': line_num,
                        'order_number': '',  # Campo editabile
                        'ean_code': line,
                        'serial_number': '',  # Seriale mancante
                        'sku': ean_to_sku_map[line],
                        'status': 'missing_order'
                    })
                    continue
                
                # EAN trovato nel database
                sku = ean_to_sku_map[line]
                order_data = orders_cache.get(current_order, {})
                expected_skus = order_data.get('expected_skus', {})
                
                # CONTROLLO SKU vs ORDINE - Validazione cruciale
                if sku not in expected_skus:
                    errors.append(f"Riga {line_num}: SKU '{sku}' (EAN: {line}) non previsto nell'ordine {current_order}")
                    # Item con errore per correzione
                    recap_items.append({
                        'line': line_num,
                        'order_number': current_order,
                        'ean_code': line,
                        'serial_number': '',  # Seriale che doveva seguire
                        'sku': sku,
                        'status': 'wrong_sku'
                    })
                    current_ean = None  # Non settare current_ean per EAN errato
                    continue
                
                current_ean = line
                continue
            
            # 3. GESTIONE CASI LIMITE - RICONOSCIMENTO PATTERN ERRATI
            
            # Se sembra un EAN ma non è nel database (scanner ha letto male)
            if self._looks_like_ean(line):
                warnings.append(f"Riga {line_num}: '{line}' sembra un EAN code ma non è nel database - possibile errore scanner")
                # Crea item editabile per permettere correzione o eliminazione
                recap_items.append({
                    'line': line_num,
                    'order_number': current_order or '',
                    'ean_code': line,  # EAN errato
                    'serial_number': '',  # Nessun seriale
                    'sku': f'UNKNOWN_{line}',
                    'status': 'invalid_ean'
                })
                continue
            
            # 4. GESTIONE SERIALE
            if current_order is None:
                errors.append(f"Riga {line_num}: Seriale '{line}' trovato senza numero ordine valido")
                # Item per correzione
                recap_items.append({
                    'line': line_num,
                    'order_number': '',  # Campo editabile
                    'ean_code': '',     # Campo editabile
                    'serial_number': line,
                    'sku': '',
                    'status': 'missing_context'
                })
                continue
            
            if current_ean is None:
                errors.append(f"Riga {line_num}: Seriale '{line}' trovato senza EAN code (operatore ha dimenticato di sparare l'EAN)")
                # CASO LIMITE: EAN SERIALE EAN SERIALE SERIALE <- questo ultimo seriale
                recap_items.append({
                    'line': line_num,
                    'order_number': current_order,
                    'ean_code': '',  # Campo editabile per inserire EAN mancante
                    'serial_number': line,
                    'sku': '',  # Sarà determinato dall'EAN che l'utente inserirà
                    'status': 'missing_ean'
                })
                continue
            
            # 5. VALIDAZIONI SERIALE COMPLETO
            sku = ean_to_sku_map[current_ean]
            status = 'warning'  # Default warning, sarà ok solo se tutte le validazioni passano
            
            # Controllo duplicati nel file corrente
            if line in serials_in_file:
                errors.append(f"Riga {line_num}: Seriale '{line}' duplicato nel file corrente")
                status = 'error'
            
            # Controllo duplicati nel database esistente
            elif line in existing_serials_db:
                # Trova dettagli del seriale esistente
                existing = self.db.query(ProductSerial).filter(ProductSerial.serial_number == line).first()
                errors.append(f"Riga {line_num}: Seriale '{line}' già esistente nel sistema (SKU: {existing.product_sku}, Ordine: {existing.order_number})")
                status = 'error'
            
            else:
                # Seriale potenzialmente valido, aggiungi al set e aggiorna conteggi
                serials_in_file.add(line)
                
                # Aggiorna statistiche ordine per controllo quantità
                if current_order in orders_summary:
                    orders_summary[current_order]['serials_count'] += 1
                    # Traccia SKU trovati
                    if sku not in orders_summary[current_order]['found_skus']:
                        orders_summary[current_order]['found_skus'][sku] = 0
                    orders_summary[current_order]['found_skus'][sku] += 1
                    
                    # CONTROLLO QUANTITÀ IN TEMPO REALE
                    expected_qty = orders_summary[current_order]['expected_products'].get(sku, 0)
                    found_qty = orders_summary[current_order]['found_skus'][sku]
                    
                    if found_qty > expected_qty:
                        # Quantità eccessiva - ERRORE o WARNING
                        excess = found_qty - expected_qty
                        warnings.append(f"Riga {line_num}: SKU '{sku}' eccedente per ordine {current_order} - trovati {found_qty}/{expected_qty} (+{excess} in eccesso)")
                        status = 'excess_quantity'  # Nuovo status per quantità eccessive
                    elif found_qty == expected_qty:
                        status = 'ok'  # Quantità corretta
                    else:
                        status = 'ok'  # Ancora sotto il limite, ok per ora
            
            # Crea recap item
            recap_items.append({
                'line': line_num,
                'order_number': current_order,
                'ean_code': current_ean,
                'serial_number': line,
                'sku': sku,
                'status': status
            })
            
            # RESET CURRENT_EAN DOPO OGNI SERIALE
            # Un EAN dovrebbe essere seguito da UN SOLO seriale per evitare associazioni errate
            current_ean = None
        
        # 6. VALIDAZIONE FINALE: CONTROLLO COMPLETEZZA ORDINI
        for order_number, summary in orders_summary.items():
            expected_skus = summary['expected_products']
            found_skus = summary['found_skus']
            
            # Verifica SKU mancanti
            for expected_sku, expected_qty in expected_skus.items():
                found_qty = found_skus.get(expected_sku, 0)
                
                if found_qty < expected_qty:
                    missing_qty = expected_qty - found_qty
                    warnings.append(f"Ordine {order_number}: SKU '{expected_sku}' incompleto - trovati {found_qty}/{expected_qty} ({missing_qty} mancanti)")
                    
                    # Crea items per seriali/EAN mancanti
                    for i in range(missing_qty):
                        recap_items.append({
                            'line': len(lines) + len(recap_items) + 1,  # Riga virtuale
                            'order_number': order_number,
                            'ean_code': expected_sku,  # Usa SKU come placeholder per EAN
                            'serial_number': '',  # Campo editabile per seriale mancante
                            'sku': expected_sku,
                            'status': 'missing_serial'
                        })
        
        return {
            'recap_items': recap_items,
            'errors': errors,
            'warnings': warnings,
            'orders_summary': orders_summary
        }
    
    def _generate_parse_message(self, result: Dict, stats: Dict) -> str:
        """Genera messaggio appropriato per il risultato del parsing"""
        total = stats['total']
        ok = stats['ok'] 
        errors = stats['errors']
        warnings = stats['warnings']
        
        if ok == 0:
            return f"Nessun seriale valido trovato. {errors} errori trovati."
        elif errors > 0 or warnings > 0:
            return f"Parsing completato con problemi. {ok}/{total} seriali validi, {errors} errori, {warnings} warning."
        else:
            return f"File elaborato con successo. {total} seriali trovati per {len(result['orders_summary'])} ordini."
    
    def commit_serial_operations(self, request: SerialCommitRequest) -> SerialUploadResult:
        """
        Esegue il commit delle operazioni seriali dopo validazione recap
        IMPORTANTE: Solo operazioni con status 'ok' vengono processate
        """
        upload_batch_id = str(uuid.uuid4())
        valid_items = [item for item in request.recap_items if item.status == 'ok']
        
        # Contiamo tutti i diversi tipi di status per il messaggio
        status_counts = {}
        for item in request.recap_items:
            status_counts[item.status] = status_counts.get(item.status, 0) + 1
        
        if not valid_items:
            error_msg = f"Nessuna operazione valida da eseguire. "
            if status_counts:
                error_details = ", ".join([f"{count} {status}" for status, count in status_counts.items()])
                error_msg += f"Status trovati: {error_details}"
            
            return SerialUploadResult(
                success=False,
                message=error_msg,
                total_lines_processed=len(request.recap_items),
                total_serials_found=0,
                total_orders_found=0,
                errors=["Tutte le operazioni devono avere status 'ok' per essere processate. Correggi gli errori nel recap."]
            )
        
        try:
            # Inserisci seriali validi
            operations = []
            orders_found = set()
            
            for item in valid_items:
                # Crea record seriale
                product_serial = ProductSerial(
                    order_number=item.order_number,
                    product_sku=item.sku,
                    ean_code=item.ean_code,
                    serial_number=item.serial_number,
                    upload_batch_id=upload_batch_id,
                    uploaded_by=request.uploaded_by,
                    validation_status="pending"
                )
                
                self.db.add(product_serial)
                orders_found.add(item.order_number)
            
            # Commit seriali
            self.db.commit()
            
            # Prepara operazioni per logging - una per ordine
            order_operations = {}
            for item in valid_items:
                order_num = item.order_number
                if order_num not in order_operations:
                    order_operations[order_num] = {
                        'success_count': 0,
                        'serials': [],
                        'first_line': item.line
                    }
                
                order_operations[order_num]['success_count'] += 1
                order_operations[order_num]['serials'].append({
                    'serial_number': item.serial_number,
                    'sku': item.sku,
                    'ean_code': item.ean_code
                })
            
            # Log operazioni
            logger = LoggingService(self.db)
            for order_number, order_data in order_operations.items():
                logger.log_operation(
                    operation_type=OperationType.SERIALI_ASSEGNATI,
                    operation_category=OperationCategory.FILE,
                    status=OperationStatus.SUCCESS,
                    product_sku=None,  # Vuoto per seriali
                    quantity=order_data['success_count'],
                    user_id=request.uploaded_by,
                    file_name=request.file_name,
                    file_line_number=order_data['first_line'],
                    details={
                        'order_number': order_number,
                        'serials_created': order_data['success_count'],
                        'serials_list': order_data['serials'],
                        'upload_batch_id': upload_batch_id
                    }
                )
            
            self.db.commit()
            
            return SerialUploadResult(
                success=True,
                message=f"Operazioni completate con successo. {len(valid_items)} seriali caricati per {len(orders_found)} ordini.",
                upload_batch_id=upload_batch_id,
                total_lines_processed=len(request.recap_items),
                total_serials_found=len(valid_items),
                total_orders_found=len(orders_found),
                errors=[],
                warnings=[]
            )
            
        except Exception as e:
            self.db.rollback()
            return SerialUploadResult(
                success=False,
                message=f"Errore durante il commit: {str(e)}",
                total_lines_processed=len(request.recap_items),
                total_serials_found=0,
                total_orders_found=0,
                errors=[str(e)]
            )
    
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
        # Query per ottenere ordini con seriali - ordina dal più recente al più vecchio
        orders_with_serials = self.db.query(ProductSerial.order_number).distinct().order_by(ProductSerial.order_number.desc()).all()
        
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