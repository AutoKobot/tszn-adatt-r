import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine
from sqlalchemy import text

print("Supabase adatbázis kényszerített migrációja (Új oszlopok hozzáadása)...")

with engine.begin() as conn:
    try:
        # 1. Diákok tábla frissítése
        conn.execute(text("ALTER TABLE diakok ADD COLUMN oktatasi_azonosito VARCHAR(11);"))
        conn.execute(text("ALTER TABLE diakok ADD COLUMN diakigazolvany_szam VARCHAR(50);"))
        print("✅ Diákok tábla kiegészítve.")
    except Exception as e:
        print(f"Megjegyzés (diakok): A diák oszlopok feltehetőleg már léteznek vagy hiba történt: {e}")

    try:
        # 2. Osztályok tábla frissítése
        conn.execute(text("ALTER TABLE osztalyok ADD COLUMN elvart_szakiranyu_oraszam INTEGER DEFAULT 400;"))
        conn.execute(text("ALTER TABLE osztalyok ADD COLUMN max_hianyzas_szazalek INTEGER DEFAULT 20;"))
        print("✅ Osztályok tábla kiegészítve.")
    except Exception as e:
        print(f"Megjegyzés (osztalyok): Az osztály oszlopok feltehetőleg már léteznek vagy hiba történt: {e}")

print("\nKész! A böngészőben nyomhatsz egy F5-öt és most már jónak kell lennie az adatok listázásának!")
