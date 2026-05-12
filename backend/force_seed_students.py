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

        # Biztosítsuk, hogy létezik osztály a diákoknak
        teszt_osztaly = db.query(models.ClassRoom).filter(models.ClassRoom.megnevezes == "12.A").first()
        if not teszt_osztaly:
            teszt_osztaly = models.ClassRoom(megnevezes="12.A", statusz="aktív")
            db.add(teszt_osztaly)
            db.flush()

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
            
            # Kockázati profilok beállítása teszteléshez
            orvosi = ma + datetime.timedelta(days=365)
            munkavedelmi = ma - datetime.timedelta(days=30)
            
            if i == 1: # Minta Beáta: Lejárt orvosi
                orvosi = ma - datetime.timedelta(days=10)
            elif i == 2: # Próba Cecil: Nincs munkavédelmi
                munkavedelmi = None
                
            diak = models.Student(
                nev=nev,
                email=f"force_teszt{i}@pelda.hu",
                oktatasi_azonosito=str(78900000000 + i),
                osztaly_id=teszt_osztaly.id,
                tagozat="nappali",
                szakma_torzs_id=szakma.id,
                szerzodes_kezdet=datetime.date(2023, 9, 1),
                szerzodes_vege=datetime.date(2025, 6, 15),
                orvosi_alkalmassagi_lejarat=orvosi,
                munkavedelmi_oktatas_datum=munkavedelmi,
                metadata_json={
                    "havi_osztondij": 60000 + (i * 1500),
                    "szakma": szakma.megnevezes
                }
            )
            db.add(diak)
            db.flush()

            # Jelenlét és érdemjegy generálás
            hianyzas_suly = 25
            if i == 3: # Demo Dénes: Sok hiányzás (>15%)
                hianyzas_suly = 4 
            
            for nap in range(1, ma.day + 1):
                datum = honap_eleje.replace(day=nap)
                if datum.weekday() >= 5: continue

                # Véletlenszerű státusz
                if (i + nap) % hianyzas_suly == 0: statusz = "igazolatlan" if i == 3 else "betegszabadsag"
                elif (i + nap) % 18 == 0: statusz = "igazolt_hianyzas"
                else: statusz = "dualis_nap" if (nap % 2 == 0) else "jelen"

                jelenlet = models.Attendance(
                    diak_id=diak.id,
                    datum=datum,
                    statusz=statusz,
                    oraszam=8,
                    tipus="cég" if "dualis" in statusz else "iskola"
                )
                db.add(jelenlet)
                
            # Érdemjegy (Demo Dénes rossz jegyeket is kap)
            jegy_ertek = 2 if i == 4 else 5 # Fiktív Eleonóra bukásra áll (átlag: 2.0)
            jegy = models.ExternalGrade(
                diak_id=diak.id,
                tantargy="Szakmai gyakorlat",
                jegy=jegy_ertek,
                datum=ma
            )
            db.add(jegy)
        
        db.commit()
        print(f"Sikeresen létrehozva {len(nevek)} diák, jelenlétek és érdemjegyek (kockázati profilokkal).")
        print("Most már tesztelheted az AI Riasztásokat a felületen!")

    except Exception as e:
        db.rollback()
        print(f"Hiba történt: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    force_seed()
