import datetime
from . import models, database

def force_seed():
    db = database.SessionLocal()
    print("--- Kényszerített Tesztadat Generálás Indítása ---")
    
    try:
        # Ellenőrizzük, vannak-e szakmák
        szakmak = db.query(models.SzakmaTorzs).all()
        if not szakmak:
            print("Hiba: Nincsenek szakmák az adatbázisban. Kérlek indítsd el a szervert egyszer a normál seedhez!")
            return

        ma = datetime.date.today()
        honap_eleje = ma.replace(day=1)
        
        nevek = [
            "Teszt Aladár", "Minta Beáta", "Próba Cecil", "Demo Dénes", 
            "Fiktív Eleonóra", "Szoftver Szabolcs", "Hegesztő Hugó", 
            "Kalkulátor Klára", "ROI Róbert", "Adat-Iker Adél"
        ]
        
        print(f"{len(nevek)} új diák létrehozása...")
        
        for i, nev in enumerate(nevek):
            szakma = szakmak[i % len(szakmak)]
            diak = models.Student(
                nev=nev,
                email=f"force_teszt{i}@pelda.hu",
                om_azonosito=str(78900000000 + i),
                osztaly="12.TEST",
                tagozat="nappali",
                szakma_torzs_id=szakma.id,
                szerzodes_kezdet=datetime.date(2023, 9, 1),
                szerzodes_vege=datetime.date(2025, 6, 15),
                havi_osztondij=60000 + (i * 1500)
            )
            db.add(diak)
            db.flush()

            # Jelenlét generálás az aktuális hónapra
            for nap in range(1, ma.day + 1):
                datum = honap_eleje.replace(day=nap)
                if datum.weekday() >= 5: continue

                # Véletlenszerű státusz
                if (i + nap) % 25 == 0: statusz = "beteg"
                elif (i + nap) % 18 == 0: statusz = "igazolt"
                else: statusz = "jelen"

                jelenlet = models.Presence(
                    student_id=diak.id,
                    datum=datum,
                    statusz=statusz,
                    dualis_nap=True if (nap % 2 == 0) else False
                )
                db.add(jelenlet)
        
        db.commit()
        print(f"Sikeresen létrehozva {len(nevek)} diák és havi jelenléti íveik.")
        print("Most már látnod kell az adatokat a Normatíva & ROI fülön!")

    except Exception as e:
        db.rollback()
        print(f"Hiba történt: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    force_seed()
