import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load env from parent directory or local .env
load_dotenv(".env")
db_url = os.getenv("DATABASE_URL")
if not db_url:
    # Try InteractiveLearning .env
    load_dotenv("../InteractiveLearning/.env")
    db_url = os.getenv("DATABASE_URL")

if not db_url:
    db_url = "postgresql://postgres.epbyruyoblszmbcgpfvh:TiszaloK123@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"

print(f"Connecting to: {db_url.split('@')[-1]}")
engine = create_engine(db_url)
with engine.connect() as conn:
    try:
        res = conn.execute(text("SELECT id, nev, api_key FROM public.iskolak")).all()
        print("\nRegistered schools in 'public.iskolak':")
        for row in res:
            print(f"ID: {row[0]}, Nev: '{row[1]}', API Key/Password: '{row[2]}'")
    except Exception as e:
        print(f"Error querying table: {e}")
