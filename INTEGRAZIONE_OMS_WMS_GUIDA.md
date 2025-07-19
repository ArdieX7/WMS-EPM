# Guida Integrazione OMS-WMS
## Requisiti Tecnici e Documentazione Necessaria

**Data**: 17 Luglio 2025  
**Documento**: Integrazione Order Management System (OMS) con Warehouse Management System (WMS)  
**Scopo**: Sincronizzazione automatica ordini e stati tra sistemi

---

## 🎯 **OBIETTIVO INTEGRAZIONE**

Automatizzare il flusso:
1. **OMS** → **WMS**: Invio ordini per picking
2. **WMS** → **OMS**: Aggiornamento stati completamento picking

**Benefici Attesi**:
- Eliminazione inserimento manuale ordini
- Sincronizzazione stati in tempo reale
- Riduzione errori e tempi operativi
- Tracciabilità end-to-end del processo

---

## 📋 **CHECKLIST DOCUMENTAZIONE DA RICHIEDERE**

### **1. DOCUMENTAZIONE API GENERALE**

#### API Documentation
- [ ] Documentazione completa API (preferibilmente Swagger/OpenAPI)
- [ ] Base URL ambiente produzione e test
- [ ] Versioning delle API (es. v1, v2)
- [ ] Rate limits e throttling policies
- [ ] Formato dati supportati (JSON/XML)
- [ ] Timezone utilizzato per date/orari

#### Authentication & Security
- [ ] Metodo autenticazione (API Key, OAuth 2.0, JWT, Basic Auth)
- [ ] Processo per ottenere credenziali test e produzione
- [ ] Requirements IP whitelisting
- [ ] Certificati SSL/TLS necessari
- [ ] Scadenza e rotazione credenziali

### **2. ENDPOINT SPECIFICI RICHIESTI**

#### **Lettura Ordini (OMS → WMS)**
```http
GET /orders?status=new&limit=100&offset=0
GET /orders/{order_id}
GET /orders?modified_since=2025-01-01T00:00:00Z
GET /orders?date_from=2025-01-01&date_to=2025-01-31
```

**Parametri necessari**:
- Filtro per status ordini
- Paginazione (limit/offset)
- Filtro per data modifica (sync incrementale)
- Filtro per range date

#### **Aggiornamento Stati (WMS → OMS)**
```http
PATCH /orders/{order_id}/status
POST /orders/{order_id}/picking_started
POST /orders/{order_id}/picking_completed  
POST /orders/{order_id}/ready_for_shipment
POST /orders/{order_id}/partial_fulfillment
```

#### **Webhook (Opzionale ma Raccomandato)**
```http
POST /webhooks/register
GET /webhooks
DELETE /webhooks/{webhook_id}
```

**Informazioni webhook**:
- URL endpoint da configurare
- Payload esempio quando ordini cambiano
- Retry logic in caso di fallimento
- Autenticazione webhook calls

### **3. STRUTTURA DATI RICHIESTA**

#### **Esempio Response Order Completo**
```json
{
  "order_id": "ORD-2025-001234",
  "customer_code": "CUST001", 
  "customer_name": "Nome Cliente",
  "order_date": "2025-07-17T10:30:00Z",
  "priority": "high", // high/medium/low
  "status": "new", // new/processing/picking/completed/cancelled
  "shipping_deadline": "2025-07-19T18:00:00Z",
  "shipping_address": {
    "name": "Destinatario",
    "address": "Via Roma 123",
    "city": "Milano",
    "postal_code": "20100",
    "country": "IT"
  },
  "notes": "Istruzioni speciali",
  "line_items": [
    {
      "line_id": "1",
      "sku": "PROD-ABC-123",
      "description": "Descrizione Prodotto",
      "quantity_ordered": 5,
      "quantity_fulfilled": 0,
      "unit_price": 29.99,
      "total_price": 149.95
    }
  ],
  "totals": {
    "subtotal": 149.95,
    "shipping": 5.00,
    "tax": 15.49,
    "total": 170.44
  }
}
```

#### **Mapping Stati Ordine**
| Stato OMS | Descrizione | Azione WMS |
|-----------|-------------|------------|
| `new` | Ordine nuovo | Importa per picking |
| `processing` | In elaborazione OMS | Attendi |
| `ready_for_picking` | Pronto picking | Inizia picking |
| `picking` | Picking in corso | Update da WMS |
| `picked` | Picking completato | Update da WMS |
| `shipped` | Spedito | Solo lettura |
| `cancelled` | Cancellato | Rimuovi da picking |

### **4. AMBIENTE DI TEST**

#### **Accessi Sandbox/Staging**
- [ ] URL ambiente di test
- [ ] Credenziali dedicate ambiente test
- [ ] Database con ordini di esempio
- [ ] Possibilità creare ordini test via API o UI
- [ ] Reset periodico dati test

#### **Test Data Set Richiesto**
**Minimum 20 ordini di esempio con scenari**:
- [ ] 5 ordini semplici (1 SKU ciascuno)
- [ ] 5 ordini multi-line (2-5 SKU ciascuno)
- [ ] 3 ordini con SKU inesistenti (test error handling)
- [ ] 2 ordini con priority diverse (high/low)
- [ ] 2 ordini già processati/completati
- [ ] 2 ordini cancellati
- [ ] 1 ordine con caratteri speciali (àèéìòù, spazi, simboli)

#### **SKU Test Set**
- [ ] Lista completa SKU utilizzabili in test
- [ ] Mapping SKU OMS ↔ SKU WMS (se diversi)
- [ ] SKU con descrizioni lunghe/caratteri speciali
- [ ] SKU discontinued/non disponibili

### **5. GESTIONE ERRORI & EDGE CASES**

#### **Error Handling**
- [ ] Lista completa codici errore HTTP e significato
- [ ] Retry policies raccomandate per ogni tipo errore
- [ ] Timeout raccomandati per chiamate API
- [ ] Gestione rate limiting (status 429)
- [ ] Fallback quando API non disponibile

**Esempi errori da gestire**:
```json
{
  "error_code": "INVALID_SKU",
  "message": "SKU PROD-999 not found",
  "details": {
    "order_id": "ORD-123",
    "line_id": "2"
  }
}
```

#### **Business Logic Edge Cases**
- [ ] Come gestire ordini modificati dopo invio WMS
- [ ] Processo cancellazione ordini già in picking
- [ ] Gestione partial fulfillment/backorder
- [ ] Priorità ordini e gestione code
- [ ] Cosa fare con ordini duplicati
- [ ] Gestione merge/split ordini

### **6. SINCRONIZZAZIONE BIDIREZIONALE**

#### **Aggiornamenti WMS → OMS**
- [ ] Formato payload per update stati
- [ ] Frequenza massima aggiornamenti
- [ ] Gestione batch updates vs singoli
- [ ] Required fields per ogni tipo update

**Esempio Update Payload**:
```json
{
  "order_id": "ORD-2025-001234",
  "status": "picking_completed",
  "timestamp": "2025-07-17T14:30:00Z",
  "line_items": [
    {
      "line_id": "1",
      "quantity_picked": 5,
      "location": "1A1P1",
      "picker_id": "USER001"
    }
  ]
}
```

#### **Frequenza Sincronizzazione**
- [ ] Rate limits per chiamate API (requests/minute)
- [ ] Batch size raccomandato per bulk operations  
- [ ] Differenza tra sync full vs incremental
- [ ] Orari preferiti per sync massive (fuori orario)
- [ ] SLA response time per webhook

### **7. MONITORAGGIO & SUPPORTO**

#### **Durante Sviluppo**
- [ ] Canale supporto tecnico (email/Slack/Teams)
- [ ] Disponibilità team per troubleshooting
- [ ] Timeline response per bug reports
- [ ] Processo per richieste modifica API
- [ ] Calendario release e maintenance windows

#### **Go-Live Support**  
- [ ] Monitoraggio primi giorni produzione
- [ ] Escalation path per problemi critici
- [ ] Performance monitoring e alerting setup
- [ ] Backup plan in caso problemi integrazione

### **8. DELIVERABLE FINALI RICHIESTI**

1. **📁 Postman Collection** 
   - Esempi funzionanti tutti gli endpoint
   - Environment variables per test/prod
   - Pre-request scripts per auth

2. **🔑 Test Credentials Package**
   - API keys ambiente sandbox
   - Username/password se necessario
   - Scadenza credenziali test

3. **📊 Sample Data Export**
   - Export ordini esempio in formato utilizzabile
   - CSV/JSON con struttura completa
   - Database dump ambiente test

4. **✅ Integration Checklist**
   - Step-by-step validation process
   - Test cases da eseguire prima go-live
   - Acceptance criteria per ogni funzionalità

5. **📞 Contact Directory**
   - Lista sviluppatori responsabili API
   - Contatti business per requirements
   - Supporto tecnico 24/7 se disponibile

---

## 📧 **TEMPLATE EMAIL DA INVIARE**

```
Oggetto: Richiesta Documentazione API per Integrazione WMS-OMS

Gentile Team [Nome OMS],

La nostra azienda sta pianificando l'integrazione del nostro Warehouse Management System (WMS) con il vostro Order Management System.

L'obiettivo è automatizzare il flusso di:
• Sincronizzazione ordini OMS → WMS per il picking
• Aggiornamento stati picking WMS → OMS

Per procedere con lo sviluppo, avremmo bisogno di:

**DOCUMENTAZIONE TECNICA:**
1. Documentazione API completa (preferibilmente Swagger/OpenAPI)
2. Credenziali ambiente test/sandbox + sample data
3. Specifiche autenticazione e rate limits
4. Esempi payload ordini in formato JSON
5. Mapping stati ordine e workflow aggiornamento
6. Processo gestione errori e retry logic

**AMBIENTE TEST:**
• Accesso sandbox con ordini di esempio
• Possibilità creare ordini test per validazione
• Set di SKU utilizzabili per test

**SUPPORTO:**
• Contatto tecnico per troubleshooting durante sviluppo
• Timeline per go-live e supporto post-implementazione

Siamo disponibili per una call di allineamento tecnico per discutere dettagli implementazione e tempistiche.

Grazie per la collaborazione.

Cordiali saluti,
[Nome] - [Azienda]
[Email] - [Telefono]
```

---

## 🚀 **FASI IMPLEMENTAZIONE SUGGERITE**

### **Fase 1: Discovery & Setup (Settimana 1-2)**
- Ottenere documentazione e accessi
- Setup ambiente test
- Validare connectivity e autenticazione

### **Fase 2: Core Integration (Settimana 3-4)**  
- Implementare lettura ordini (OMS → WMS)
- Sviluppare mapping dati e validazione
- Test con ordini esempio

### **Fase 3: Bidirectional Sync (Settimana 5-6)**
- Implementare aggiornamenti stati (WMS → OMS)
- Error handling e retry logic
- Test scenari edge cases

### **Fase 4: Production Readiness (Settimana 7-8)**
- Performance testing e ottimizzazione
- Monitoring e alerting setup
- Go-live con supporto dedicato

---

**Ultimo aggiornamento**: 17 Luglio 2025  
**Versione documento**: 1.0  
**Prossima revisione**: Post-meeting con team OMS