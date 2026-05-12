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

    # 2. MINTA DIÁKOK ÉS JELENLÉT SEED (Külön csekk, ha a DB üres)
    if db.query(models.Student).count() == 0:
        try:
            print("[SEED] Minta diákok generálása a teszteléshez...")
            # ... (itt folytatódik a diák generáló kód amit az előbb írtam)
            print("[SEED] Minta diákok generálása a teszteléshez...")
            szakmak = db.query(models.SzakmaTorzs).all()
            if not szakmak: return

            # Biztosítsuk, hogy létezik osztály a diákoknak
            teszt_osztaly = db.query(models.ClassRoom).filter(models.ClassRoom.megnevezes == "12.C").first()
            if not teszt_osztaly:
                teszt_osztaly = models.ClassRoom(megnevezes="12.C", statusz="aktív")
                db.add(teszt_osztaly)
                db.flush()

            ma = datetime.date.today()
            honap_eleje = ma.replace(day=1)
            
            nevek = ["Kovács Adél", "Nagy Barnabás", "Szabó Csenge", "Tóth Dániel", "Kiss Enikő", "Molnár Ferenc", "Varga Gábor", "Fekete Hanna", "Németh Imre", "Papp Júlia"]
            
            for i, nev in enumerate(nevek):
                szakma = szakmak[i % len(szakmak)]
                diak = models.Student(
                    nev=nev,
                    email=f"teszt{i}@iskola.hu",
                    oktatasi_azonosito=str(78600000000 + i),
                    osztaly_id=teszt_osztaly.id,
                    tagozat="nappali",
                    szakma_torzs_id=szakma.id,
                    szerzodes_kezdet=datetime.date(2023, 9, 1),
                    szerzodes_vege=datetime.date(2025, 6, 15),
                    metadata_json={
                        "havi_osztondij": 50000 + (i * 2000),
                        "szakma": szakma.megnevezes
                    }
                )
                db.add(diak)
                db.flush() # Hogy megkapjuk a diák ID-ját

                # Generáljunk jelenlétet a hónap eddigi napjaira
                for nap in range(1, ma.day + 1):
                    datum = honap_eleje.replace(day=nap)
                    # Hétvégéket hagyjuk ki
                    if datum.weekday() >= 5: continue

                    # Véletlenszerű státusz
                    rand = i + nap
                    if rand % 20 == 0: statusz = "betegszabadsag"
                    elif rand % 15 == 0: statusz = "igazolt_hianyzas"
                    else: statusz = "dualis_nap" if (nap % 2 == 0) else "jelen"

                    jelenlet = models.Attendance(
                        diak_id=diak.id,
                        datum=datum,
                        statusz=statusz,
                        oraszam=8,
                        tipus="cég" if "dualis" in statusz else "iskola"
                    )
                    db.add(jelenlet)
            
            db.commit()
            print(f"[SEED] {len(nevek)} minta diák és jelenléti adatok sikeresen létrehozva.")

        except Exception as e:
            db.rollback()
            print(f"[SEED] Hiba a betöltés során: {e}")
