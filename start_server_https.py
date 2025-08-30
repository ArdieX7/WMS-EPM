#!/usr/bin/env python3

import uvicorn
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    # Add current directory to Python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))  # Usa la stessa porta 8000
    debug = os.getenv("DEBUG", "True").lower() == "true"
    
    # Percorsi certificati SSL
    cert_file = "ssl_certs/server.crt"
    key_file = "ssl_certs/server.key"
    
    # Verifica che i certificati esistano
    if not os.path.exists(cert_file) or not os.path.exists(key_file):
        print("❌ Certificati SSL non trovati!")
        print("🔧 Esegui prima: python generate_ssl.py")
        sys.exit(1)
    
    print(f"🔒 Starting WMS EPM HTTPS server on {host}:{port}")
    print(f"📍 URL Locale: https://localhost:{port}")
    print(f"📍 URL Remoto: https://93.151.231.147:{port}")
    print(f"🌐 Host binding: {host} (0.0.0.0 = tutti gli IP)")
    print(f"🔐 Debug mode: {debug}")
    print(f"📜 Certificato: {cert_file}")
    print(f"🔑 Chiave: {key_file}")
    print("\n⚠️  Il browser mostrerà un avviso di sicurezza - è normale per certificati autofirmati")
    print("✅ Clicca 'Avanzate' → 'Procedi verso il sito (non sicuro)'")
    print("\n🎯 USA QUESTO URL: https://93.151.231.147:8000")
    print("📋 Se non funziona, prova anche: https://localhost:8000")
    
    # Forza host per accesso remoto
    if host != "0.0.0.0":
        print(f"⚠️  Host era {host}, forzo a 0.0.0.0 per accesso remoto")
        host = "0.0.0.0"
    
    print(f"\n🚀 Avvio server HTTPS...")
    print(f"   Host: {host}")
    print(f"   Porta: {port}")
    print(f"   SSL Cert: {cert_file}")
    print(f"   SSL Key: {key_file}")
    
    # Start HTTPS server
    uvicorn.run(
        "wms_app.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if not debug else "debug",
        ssl_certfile=cert_file,
        ssl_keyfile=key_file
    )