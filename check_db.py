import sqlite3
import os

# Percorso al tuo file del database
db_path = os.path.join(os.path.dirname(__file__), 'wms.db')

conn = None
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Contenuto della tabella 'inventory':")
    cursor.execute("SELECT * FROM inventory;")
    rows = cursor.fetchall()
    
    if not rows:
        print("La tabella 'inventory' è vuota.")
    else:
        # Stampa gli header delle colonne
        col_names = [description[0] for description in cursor.description]
        print(col_names)
        for row in rows:
            print(row)

    print("\nContenuto della tabella 'products':")
    cursor.execute("SELECT * FROM products;")
    rows = cursor.fetchall()
    
    if not rows:
        print("La tabella 'products' è vuota.")
    else:
        col_names = [description[0] for description in cursor.description]
        print(col_names)
        for row in rows:
            print(row)

    print("\nContenuto della tabella 'ean_codes':")
    cursor.execute("SELECT * FROM ean_codes;")
    rows = cursor.fetchall()
    
    if not rows:
        print("La tabella 'ean_codes' è vuota.")
    else:
        col_names = [description[0] for description in cursor.description]
        print(col_names)
        for row in rows:
            print(row)

except sqlite3.Error as e:
    print(f"Errore del database: {e}")
finally:
    if conn:
        conn.close()
