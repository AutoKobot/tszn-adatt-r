import os
import sys
import traceback
from sqlalchemy import text

# Add the parent directory to sys.path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import database, models

def test_sync():
    print("Starting sync simulation with full error logging...")
    db = database.SessionLocal()
    
    try:
        # 0. Sync schools to satisfy Foreign Keys
        db.execute(text("""
            INSERT INTO public.iskolak (id, nev, created_at)
            SELECT id, name, created_at FROM public.schools
            ON CONFLICT (id) DO UPDATE SET nev = EXCLUDED.nev;
        """))
        db.commit()
        print("✅ Pre-synced schools from public.schools to public.iskolak.")

        # Sync classes to satisfy Foreign Keys
        db.execute(text("""
            INSERT INTO public.osztalyok (id, megnevezes, statusz, iskola_id)
            SELECT id, name, 'aktív', school_id FROM public.classes
            ON CONFLICT (id) DO UPDATE SET megnevezes = EXCLUDED.megnevezes, iskola_id = EXCLUDED.iskola_id;
        """))
        db.commit()
        print("✅ Pre-synced classes from public.classes to public.osztalyok.")

        # Simulate school_id = None (global admin)
        school_id = None
        
        users_res = db.execute(
            text("SELECT username, email, id, school_id FROM public.users WHERE role = 'student'")
        ).all()
        
        print(f"Found {len(users_res)} student users in public.users.")
        
        for idx, u_row in enumerate(users_res):
            u_username = u_row[0] # OM id vagy username
            u_email = u_row[1]
            u_id = u_row[2]
            db_school_id = u_row[3] or school_id
            
            print(f"\nProcessing user {idx+1}/{len(users_res)}: {u_username} (email: {u_email}, id: {u_id})")
            
            # Check existing
            existing = None
            if u_username:
                existing = db.query(models.Student).filter(models.Student.oktatasi_azonosito == u_username).first()
            if not existing and u_email:
                existing = db.query(models.Student).filter(models.Student.email == u_email).first()
                
            if not existing:
                nev = "Ismeretlen Diák"
                try:
                    name_row = db.execute(
                        text("SELECT last_name, first_name FROM public.users WHERE id = :user_id"),
                        {"user_id": u_id}
                    ).first()
                    
                    if name_row:
                        l_name = name_row[0] or ""
                        f_name = name_row[1] or ""
                        if l_name or f_name:
                            nev = f"{l_name} {f_name}".strip()
                except Exception as e_name:
                    print(f"  ⚠️ Warning getting name: {e_name}")
                    nev = u_username or (u_email.split('@')[0] if u_email else "Ismeretlen Diák")
                
                db_class_id = None
                try:
                    class_id_row = db.execute(
                        text("SELECT class_id FROM public.users WHERE id = :user_id"),
                        {"user_id": u_id}
                    ).first()
                    db_class_id = class_id_row[0] if class_id_row else None
                except Exception as e_class:
                    print(f"  ⚠️ Warning getting class: {e_class}")
                
                print(f"  -> Creating new student: name='{nev}', email='{u_email}', OM='{u_username}', school_id={db_school_id}, class_id={db_class_id}")
                
                new_s = models.Student(
                    nev=nev,
                    email=u_email if u_email else None,
                    oktatasi_azonosito=u_username if (u_username and len(u_username) == 11 and u_username.isdigit()) else None,
                    iskola_id=db_school_id,
                    osztaly_id=db_class_id,
                    tagozat="nappali",
                    metadata_json={
                        "forras": "InteractiveLearning",
                        "portal_id": u_id
                    }
                )
                db.add(new_s)
                # Flush to trigger database constraints check for this specific record
                db.flush()
                print("  ✅ Successfully added & flushed.")
            else:
                print(f"  -> Student already exists.")
                
        # Commit the transaction
        db.commit()
        print("\n🎉 SUCCESS: All students processed and committed without exceptions!")
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR during sync: {e}")
        traceback.print_exc()
        db.rollback()
        print("Transaction rolled back.")
    finally:
        db.close()

if __name__ == "__main__":
    test_sync()
