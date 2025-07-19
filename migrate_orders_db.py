#!/usr/bin/env python3
"""
Script di migrazione per aggiungere le nuove colonne alla tabella orders.
Questo script aggiunge le colonne per gestire archiviazione e annullamento ordini.
"""

import sqlite3
import os
from datetime import datetime

def migrate_orders_table():
    """Aggiunge le nuove colonne alla tabella orders se non esistono già."""
    
    # Path del database
    db_path = "wms.db"
    
    if not os.path.exists(db_path):
        print(f"[ERROR] Database non trovato: {db_path}")
        return False
    
    print(f"[INFO] Connessione al database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verifica se le colonne esistono già
        cursor.execute("PRAGMA table_info(orders)")
        columns = [column[1] for column in cursor.fetchall()]
        
        print(f"[INFO] Colonne attuali nella tabella orders: {columns}")
        
        # Lista delle nuove colonne da aggiungere
        new_columns = [
            ("is_archived", "BOOLEAN DEFAULT 0"),
            ("is_cancelled", "BOOLEAN DEFAULT 0"),
            ("archived_date", "DATETIME"),
            ("cancelled_date", "DATETIME")
        ]
        
        changes_made = False
        
        for column_name, column_def in new_columns:
            if column_name not in columns:
                print(f"[ADD] Aggiungendo colonna: {column_name}")
                cursor.execute(f"ALTER TABLE orders ADD COLUMN {column_name} {column_def}")
                changes_made = True
            else:
                print(f"[OK] Colonna {column_name} già esistente")
        
        if changes_made:
            conn.commit()
            print("[SUCCESS] Migrazione completata con successo!")
            
            # Verifica finale
            cursor.execute("PRAGMA table_info(orders)")
            updated_columns = [column[1] for column in cursor.fetchall()]
            print(f"[INFO] Colonne aggiornate: {updated_columns}")
            
        else:
            print("[INFO] Nessuna migrazione necessaria - tutte le colonne sono già presenti")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"[ERROR] Errore durante la migrazione: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Errore generico: {e}")
        return False

def verify_migration():
    """Verifica che la migrazione sia stata completata correttamente."""
    
    db_path = "wms.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Test query per verificare che le nuove colonne funzionino
        cursor.execute("""
            SELECT 
                id, order_number, is_completed, is_archived, is_cancelled,
                archived_date, cancelled_date
            FROM orders 
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        print("[SUCCESS] Test query eseguita con successo!")
        
        if result:
            print(f"[INFO] Esempio di record: {result}")
        else:
            print("[INFO] Tabella orders vuota")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"[ERROR] Errore durante la verifica: {e}")
        return False

if __name__ == "__main__":
    print("Avvio migrazione database ordini...")
    print("=" * 50)
    
    # Esegui migrazione
    if migrate_orders_table():
        print("\nVerifica migrazione...")
        verify_migration()
        print("\nMigrazione completata! Il server ora dovrebbe funzionare correttamente.")
    else:
        print("\nMigrazione fallita!")
    
    print("=" * 50)