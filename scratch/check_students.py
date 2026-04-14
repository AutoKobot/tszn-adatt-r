
import os
import sys

# Add the current directory to sys.path to import backend modules
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend import models, database

def check_data():
    db = database.SessionLocal()
    try:
        students = db.query(models.Student).all()
        print(f"Tanulók száma: {len(students)}")
        for s in students:
            print(f"ID: {s.id}, Név: {s.nev}, OM: {s.oktatasi_azonosito}, Email: {s.email}")
            
        users = db.query(models.User).all()
        print(f"\nFelhasználók száma: {len(users)}")
        for u in users:
            print(f"ID: {u.id}, Név: {u.full_name}, Felhasználónév: {u.username}, Szerep: {u.role}")

        classes = db.query(models.ClassRoom).all()
        print(f"\nOsztályok száma: {len(classes)}")
        for c in classes:
            print(f"ID: {c.id}, Név: {c.megnevezes}")

    except Exception as e:
        print(f"Hiba: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_data()
