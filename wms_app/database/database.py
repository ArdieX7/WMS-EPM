from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Percorso del file del database SQLite
# Il database verrà creato nella cartella principale del progetto
SQLALCHEMY_DATABASE_URL = "sqlite:///./wms.db"

# Crea il "motore" di SQLAlchemy per connettersi al database
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Crea una sessione per le transazioni con il database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Una classe base per i nostri modelli di dati (le tabelle)
Base = declarative_base()

# Funzione per ottenere una sessione del database
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
