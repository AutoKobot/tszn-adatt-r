import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Lépjünk vissza egy szintet, hogy elérjük a backend mappát és a .env fájlt
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

db_url = os.getenv("DATABASE_URL")
print(f"Loaded DATABASE_URL: {db_url.split('@')[-1] if db_url else 'None'}")

if not db_url:
    print("[FAIL] DATABASE_URL is not set in the environment or .env file!")
    sys.exit(1)

# Supabase Pooler - felhasználónév javítás a backend/database.py logikája szerint
if "pooler.supabase.com" in db_url and "@" in db_url:
    userinfo = db_url.split("@")[0].split("//")[1]
    username = userinfo.split(":")[0]
    if "." not in username:
        correct = f"{username}.epbyruyoblszmbcgpfvh"
        db_url = db_url.replace(f"//{username}:", f"//{correct}:", 1)
        print(f"[DB] Supabase felhasználónév javítva: {correct}")

try:
    engine = create_engine(db_url, connect_args={"connect_timeout": 5})
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 1")).scalar()
        print(f"[OK] Adatbázis kapcsolat sikeres! Teszt lekérdezés eredménye: {res}")
        
        # Ellenőrizzük a táblákat
        for table in ["iskolak", "felhasznalok", "diakok", "osztalyok", "jelenlet", "kulso_jegyek"]:
            try:
                count = conn.execute(text(f"SELECT COUNT(*) FROM public.{table}")).scalar()
                print(f"  - Tábla 'public.{table}' létezik, sorok száma: {count}")
            except Exception as tbl_err:
                print(f"  - [HIBA] Tábla 'public.{table}' lekérdezése sikertelen: {tbl_err}")
                
except Exception as e:
    print(f"[FAIL] Kapcsolódási hiba az adatbázishoz: {e}")
