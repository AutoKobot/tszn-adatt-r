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
    print("\n--- SCHOOL ADMINS IN public.users ---")
    try:
        res = conn.execute(text("SELECT id, username, email, school_id, password FROM public.users WHERE role='school_admin'")).all()
        for row in res:
            print(f"  ID: {row[0]}, Username: '{row[1]}', Email: '{row[2]}', School ID: {row[3]}, Password Hash: '{row[4][:30]}...'")
    except Exception as e:
        print(f"  Error reading public.users: {e}")
