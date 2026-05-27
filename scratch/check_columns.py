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

engine = create_engine(db_url)
with engine.connect() as conn:
    # 1. Print schools columns
    print("\n--- COLUMNS IN public.schools ---")
    res = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='schools' AND table_schema='public'")).all()
    for row in res:
        print(f"  Column: {row[0]}, Type: {row[1]}")

    # 2. Print iskolak columns
    print("\n--- COLUMNS IN public.iskolak ---")
    res = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='iskolak' AND table_schema='public'")).all()
    for row in res:
        print(f"  Column: {row[0]}, Type: {row[1]}")
