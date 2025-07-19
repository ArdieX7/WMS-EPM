#!/usr/bin/env python3

import subprocess
import sys

def install_openpyxl():
    """Installa openpyxl se non è presente"""
    try:
        import openpyxl
        print("openpyxl è già installato")
        return True
    except ImportError:
        print("openpyxl non trovato, installazione in corso...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
            print("openpyxl installato con successo")
            return True
        except subprocess.CalledProcessError:
            print("Errore nell'installazione di openpyxl")
            return False

if __name__ == "__main__":
    install_openpyxl()