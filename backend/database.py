from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from urllib.parse import urlparse, urlunparse
import os
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")

if not db_url:
    print("FIGYELMEZTETÉS: DATABASE_URL hiányzik! Lokális módba váltás.")
    db_url = "postgresql://postgres:postgres@localhost:5432/edu_registrar"

# Fix 1: postgres:// -> postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Fix 2: Supabase Pooler - javítjuk a felhasználónevet urlparse-szal
if "pooler.supabase.com" in db_url:
    parsed = urlparse(db_url)
    username = parsed.username or ""
    
    # Ha a felhasználónév csak "postgres" (nincs benne pont), hozzáadjuk az azonosítót
    if username == "postgres":
        new_username = "postgres.upghcvosvrafiogfrxiq"
        netloc = parsed.netloc.replace(f"{username}:", f"{new_username}:", 1)
        parsed = parsed._replace(netloc=netloc)
        db_url = urlunparse(parsed)
        print(f"Supabase felhasználónév javítva: {new_username}")

# Biztonságos naplózás (jelszó nélkül)
try:
    parsed_log = urlparse(db_url)
    print(f"Kapcsolódás: {parsed_log.hostname}:{parsed_log.port} (user: {parsed_log.username})")
except Exception:
    pass

engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
