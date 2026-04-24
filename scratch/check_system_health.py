import sys
import os
from sqlalchemy import text

# Add the project root to sys.path to allow importing from backend
sys.path.append(os.getcwd())

from backend import database, models

def check_health():
    print("--- System Health Check ---")
    try:
        db = database.SessionLocal()
        # 1. Test Connection
        print("[1] Testing database connection...")
        db.execute(text("SELECT 1"))
        print("    SUCCESS: Database connection is alive.")

        # 2. Check Tables
        print("[2] Checking core tables and data count...")
        tables = {
            "Students": models.Student,
            "Users": models.User,
            "ClassRooms": models.ClassRoom,
            "Attendance": models.Attendance
        }
        for name, model in tables.items():
            count = db.query(model).count()
            print(f"    - {name}: {count} records")

        # 3. Check for obvious errors in data
        print("[3] Basic data validation...")
        students_without_class = db.query(models.Student).filter(models.Student.osztaly_id == None).count()
        if students_without_class > 0:
            print(f"    WARNING: {students_without_class} students have no class assigned.")
        else:
            print("    OK: All students have a class assigned.")

        db.close()
        print("\nSUMMARY: System appears STABLE.")
        return True
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        return False

if __name__ == "__main__":
    success = check_health()
    sys.exit(0 if success else 1)
