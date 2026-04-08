from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/edu_registrar")

# Fix 1: postgres:// -> postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Fix 2: Supabase Pooler - felhasználónév javítás CSAK string műveletekkel
# (sem urllib, sem ipaddress nem hívódik meg)
if "pooler.supabase.com" in db_url and "@" in db_url:
    userinfo = db_url.split("@")[0].split("//")[1]   # pl: "postgres:jelszo"
    username = userinfo.split(":")[0]                 # pl: "postgres"
    if "." not in username:
        correct = f"{username}.upghcvosvrafiogfrxiq"
        db_url = db_url.replace(f"//{username}:", f"//{correct}:", 1)
        print(f"[DB] Supabase felhasználónév javítva: {correct}")
    else:
        print(f"[DB] Supabase felhasználónév OK: {username}")

print(f"[DB] Kapcsolódás indítása...")

engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

