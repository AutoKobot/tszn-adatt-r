from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")

if not db_url:
    print("FIGYELMEZTETÉS: DATABASE_URL hiányzik! Lokális módba váltás.")
    db_url = "postgresql://postgres:postgres@localhost:5432/edu_registrar"

# Fix: postgres:// -> postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Fix: Supabase Pooler felhasználónév javítása (postgres.AZONOSITO kell)
if "pooler.supabase.com" in db_url and "@postgres:" not in db_url:
    if "/postgres:" in db_url and "postgres." not in db_url.split("@")[0]:
        db_url = db_url.replace("//postgres:", "//postgres.upghcvosvrafiogfrxiq:", 1)
        print("Supabase URL javítva: projekt azonosító hozzáadva.")

# Biztonságos napló (jelszó nélkül)
try:
    masked = db_url.split("@")[1]
    print(f"Adatbázis cél: {masked}")
except Exception:
    pass

engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
