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

# Fix 1: postgres:// -> postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Fix 2: Supabase Pooler - egyszerű szöveges felhasználónév javítás
if "pooler.supabase.com" in db_url:
    # A felhasználónév a :// és az első : között van
    after_prefix = db_url[len("postgresql://"):]
    username = after_prefix.split(":")[0]
    if username == "postgres":
        db_url = db_url.replace("://postgres:", "://postgres.upghcvosvrafiogfrxiq:", 1)
        print("Supabase felhasználónév javítva: postgres.upghcvosvrafiogfrxiq")

# Biztonságos naplózás (jelszó nélkül)
try:
    host_part = db_url.split("@")[1]
    user_part = db_url.split("//")[1].split(":")[0]
    print(f"Kapcsolódás: {host_part} (user: {user_part})")
except Exception:
    pass

engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
