import json
import os
import datetime
from sqlalchemy.orm import Session
from . import models

def seed_normativa_data(db: Session):
    """0. LÉPÉS: Alapadatok betöltése a JSON seed fájlból."""
    
    # Csak akkor fut le, ha a SzakmaTorzs még üres
    if db.query(models.SzakmaTorzs).count() > 0:
        print("[SEED] Szakmatörzs már tartalmaz adatokat, kihagyás.")
        return

    seed_path = os.path.join(os.path.dirname(__file__), "seed_data", "normativa_seed.json")
    if not os.path.exists(seed_path):
        print(f"[SEED] Hiba: A seed fájl nem található: {seed_path}")
        return

    try:
        with open(seed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        print(f"[SEED] Alapadatok betöltése a {data['tanev']} tanévhez...")

        # 1. NormativaKonfig létrehozása
        konfig = models.NormativaKonfig(
            tanev_nev=data["tanev"],
            onkoltsegi_alap_default=data["onkoltsegi_alap"],
            sikerdij_szazalek=data["sikerdij_szazalek"],
            aktiv=True
        )
        db.add(konfig)

        # 2. SzakmaTorzs feltöltése
        for s in data["szakmak"]:
            db_s = models.SzakmaTorzs(
                szakma_szam=s["szakma_szam"],
                megnevezes=s["megnevezes"],
                agazat=s["agazat"],
                szorzo=s["szorzo"],
                onkoltsegi_alap=data["onkoltsegi_alap"],
                adat_forrasa="seed"
            )
            db.add(db_s)

        # 3. TanevRendje (Munkaszüneti napok)
        for nap_str in data["munkaszuneti_napok_2025_2026"]:
            db_n = models.TanevRendje(
                tanev_nev=data["tanev"],
                datum=datetime.date.fromisoformat(nap_str),
                tipus="munkaszuneti"
            )
            db.add(db_n)

        db.commit()
        print("[SEED] Sikeresen betöltve: Szakmák, Konfiguráció és Ünnepnapok.")

    except Exception as e:
        db.rollback()
        print(f"[SEED] Hiba a betöltés során: {e}")
