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

# Fix 2: Supabase Transaction Pooler (port 6543) megköveteli a projekt-specifikus felhasználónevet
# Format: postgres.PROJECT_REF (nem csak "postgres")
if "pooler.supabase.com" in db_url:
    parsed = urlparse(db_url)
    username = parsed.username or ""
    
    print(f"[DB] Supabase pooler észlelve. Felhasználónév: '{username}'")
    
    # Ha a felhasználónév csak "postgres" (nincs projekt-ref), automatikusan javítjuk
    if "." not in username:
        project_ref = os.getenv("SUPABASE_PROJECT_REF", "upghcvosvrafiogfrxiq")
        new_username = f"{username}.{project_ref}"
        
        # URL újraépítése a helyes felhasználónévvel
        netloc = parsed.netloc.replace(
            f"{username}:", f"{new_username}:", 1
        )
        db_url = urlunparse(parsed._replace(netloc=netloc))
        print(f"[DB] Felhasználónév javítva: '{username}' -> '{new_username}'")
    else:
        print(f"[DB] Felhasználónév már megfelelő formátumú (tartalmaz '.').")

# Biztonságos naplózás (jelszó nélkül)
try:
    parsed_log = urlparse(db_url)
    print(f"[DB] Kapcsolódás: {parsed_log.host}:{parsed_log.port}{parsed_log.path} (user: {parsed_log.username})")
except Exception:
    pass

engine = create_engine(
    db_url,
    pool_pre_ping=True,        # Hallott kapcsolatok ellenőrzése
    pool_recycle=300,          # 5 percenként megújítja a kapcsolatokat
    connect_args={"connect_timeout": 10}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
