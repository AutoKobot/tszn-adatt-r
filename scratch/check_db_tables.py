import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load database URL
load_dotenv(".env")
db_url = os.getenv("DATABASE_URL")
if not db_url:
    load_dotenv("../InteractiveLearning/.env")
    db_url = os.getenv("DATABASE_URL")

if not db_url:
    db_url = "postgresql://postgres.epbyruyoblszmbcgpfvh:TiszaloK123@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"

print(f"Connecting to: {db_url.split('@')[-1]}")
engine = create_engine(db_url)
with engine.connect() as conn:
    # 1. List all tables in public schema
    print("\n--- TABLES IN PUBLIC SCHEMA ---")
    tables = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).all()
    for t in tables:
        print(f"  - {t[0]}")
        
    # 2. Check public.schools content if exists
    print("\n--- CONTENT of public.schools ---")
    try:
        schools_res = conn.execute(text("SELECT id, name FROM public.schools")).all()
        for row in schools_res:
            print(f"  ID: {row[0]}, Name: '{row[1]}'")
    except Exception as e:
        print(f"  Error reading public.schools: {e}")

    # 3. Check public.iskolak content if exists
    print("\n--- CONTENT of public.iskolak ---")
    try:
        iskolak_res = conn.execute(text("SELECT id, nev, api_key FROM public.iskolak")).all()
        for row in iskolak_res:
            print(f"  ID: {row[0]}, Nev: '{row[1]}', API Key: '{row[2]}'")
    except Exception as e:
        print(f"  Error reading public.iskolak: {e}")
