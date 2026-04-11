import os
from sqlalchemy import create_all_engines, create_engine
from sqlalchemy.orm import sessionmaker
from backend import models, database

# Adatbázis elérés
DATABASE_URL = "postgresql://postgres.itpivsqitjscfdfswvuy:Kobot20242024@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    count = db.query(models.Student).count()
    print(f"Összes tanuló az adatbázisban: {count}")
    
    first_few = db.query(models.Student).limit(5).all()
    for s in first_few:
        print(f"ID: {s.id}, Név: {s.nev}, Email: {s.email}, OM: {s.oktatasi_azonosito}")
        
    # Ellenőrizzük a tagozatokat
    nappali = db.query(models.Student).filter(models.Student.tagozat == 'nappali').count()
    felnott = db.query(models.Student).filter(models.Student.tagozat == 'felnott').count()
    print(f"Nappali: {nappali}, Felnőtt: {felnott}")

finally:
    db.close()
