import json
import os
import datetime
from sqlalchemy.orm import Session
from . import models

def seed_normativa_data(db: Session):
    """0. LÉPÉS: Alapadatok betöltése."""
    
    # 1. SZAKMATÖRZS ÉS KONFIG SEED
    if db.query(models.SzakmaTorzs).count() == 0:
        seed_path = os.path.join(os.path.dirname(__file__), "seed_data", "normativa_seed.json")
        if os.path.exists(seed_path):
            try:
                with open(seed_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"[SEED] Alapadatok betöltése a {data['tanev']} tanévhez...")

                konfig = models.NormativaKonfig(
                    tanev_nev=data["tanev"],
                    onkoltsegi_alap_default=data["onkoltsegi_alap"],
                    sikerdij_szazalek=data["sikerdij_szazalek"],
                    aktiv=True
                )
                db.add(konfig)

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

                for nap_str in data["munkaszuneti_napok_2025_2026"]:
                    db_n = models.TanevRendje(
                        tanev_nev=data["tanev"],
                        datum=datetime.date.fromisoformat(nap_str),
                        tipus="munkaszuneti"
                    )
                    db.add(db_n)
                db.commit()
                print("[SEED] Alapszerkezet (Szakmák, Konfig) betöltve.")
            except Exception as e:
                db.rollback()
                print(f"[SEED] Hiba az alap seed során: {e}")

    # 2. MINTA DIÁKOK ÉS JELENLÉT SEED (KIKAPCSOLVA)
    # Az automatikus startup diák generálás ki lett kapcsolva, mert a szerver leállása/ébredése után
    # a korábban törölt fiktív tanulók mindig újragenerálódtak (ha a diákszám 0 volt).
    # A manuális tesztadat generálás továbbra is elérhető a Beállítások menüből.
    print("[SEED] Automatikus minta diákok betöltése kikapcsolva. Használd a kézi generálást ha szükséges.")
