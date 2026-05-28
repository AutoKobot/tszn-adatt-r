import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_diagnostics():
    print("====================================================")
    print("📊 INTERACTIVE LEARNING -> EDUREGISTRAR SYNC DIAGNOSTICS")
    print("====================================================\n")
    
    # 1. Load Environment Variables
    load_dotenv(".env")
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        # Fallback to InteractiveLearning .env
        load_dotenv("../InteractiveLearning/.env")
        db_url = os.getenv("DATABASE_URL")
        
    if not db_url:
        print("❌ ERROR: DATABASE_URL not found in .env or parent directory .env!")
        return

    # Supabase Pooler username fix from backend/database.py
    if "pooler.supabase.com" in db_url and "@" in db_url:
        userinfo = db_url.split("@")[0].split("//")[1]
        username = userinfo.split(":")[0]
        if "." not in username:
            correct = f"{username}.epbyruyoblszmbcgpfvh"
            db_url = db_url.replace(f"//{username}:", f"//{correct}:", 1)
            print(f"🔧 Fixed Supabase Pooler username to: {correct}")

    print(f"🔌 Connecting to: {db_url.split('@')[-1]}")
    
    try:
        engine = create_engine(db_url, connect_args={"connect_timeout": 10}, pool_pre_ping=True)
        with engine.connect() as conn:
            # Check 1: Ping connection
            res = conn.execute(text("SELECT 1")).scalar()
            print(f"✅ Connection successful! Test query returned: {res}\n")
            
            # Check 2: List all tables in public schema
            print("--- 📂 TABLES IN PUBLIC SCHEMA ---")
            tables = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).all()
            table_names = [t[0] for t in tables]
            print(f"Found {len(table_names)} tables: {', '.join(table_names)}")
            
            # Check 3: Check schools table content
            print("\n--- 🏢 SCHOOLS (public.schools) ---")
            if "schools" in table_names:
                schools = conn.execute(text("SELECT id, name FROM public.schools")).all()
                print(f"Total schools in public.schools: {len(schools)}")
                for s in schools:
                    print(f"  - ID: {s[0]}, Name: '{s[1]}'")
            else:
                print("❌ Table 'public.schools' does not exist!")

            # Check 4: Check schools table content in schools_v2/iskolak
            print("\n--- 🏢 SCHOOLS (public.iskolak) ---")
            if "iskolak" in table_names:
                iskolak = conn.execute(text("SELECT id, nev FROM public.iskolak")).all()
                print(f"Total schools in public.iskolak: {len(iskolak)}")
                for i in iskolak:
                    print(f"  - ID: {i[0]}, Name: '{i[1]}'")
            else:
                print("⚠️ Table 'public.iskolak' does not exist.")

            # Check 5: Diagnose public.users (InteractiveLearning user table)
            print("\n--- 👥 PORTAL USERS (public.users) ---")
            if "users" in table_names:
                total_users = conn.execute(text("SELECT COUNT(*) FROM public.users")).scalar()
                student_users = conn.execute(text("SELECT COUNT(*) FROM public.users WHERE role='student'")).scalar()
                teacher_users = conn.execute(text("SELECT COUNT(*) FROM public.users WHERE role='teacher'")).scalar()
                admin_users = conn.execute(text("SELECT COUNT(*) FROM public.users WHERE role='school_admin'")).scalar()
                
                print(f"Total rows in public.users: {total_users}")
                print(f"  - Students: {student_users}")
                print(f"  - Teachers: {teacher_users}")
                print(f"  - School Admins: {admin_users}")
                
                # Check for school_id distribution in students
                print("\nStudent distribution by school_id in public.users:")
                school_dist = conn.execute(text(
                    "SELECT school_id, COUNT(*) FROM public.users WHERE role='student' GROUP BY school_id"
                )).all()
                for row in school_dist:
                    print(f"  - school_id: {row[0]}, Count: {row[1]}")
                
                # Print a sample of student users
                print("\nSample student users from public.users:")
                sample_students = conn.execute(text(
                    "SELECT id, username, email, first_name, last_name, school_id, class_id FROM public.users WHERE role='student' LIMIT 5"
                )).all()
                for s in sample_students:
                    print(f"  - ID: {s[0]} | Username: '{s[1]}' | Email: '{s[2]}' | Name: '{s[4]} {s[3]}' | school_id: {s[5]} | class_id: {s[6]}")
            else:
                print("❌ Table 'public.users' does not exist! This is critical because the sync depends on it.")

            # Check 6: Check local Student table (public.diakok)
            print("\n--- 🎓 LOCAL STUDENTS (public.diakok) ---")
            if "diakok" in table_names:
                total_students = conn.execute(text("SELECT COUNT(*) FROM public.diakok")).scalar()
                print(f"Total students in public.diakok: {total_students}")
                
                # Distribution of local students by school
                student_dist = conn.execute(text(
                    "SELECT iskola_id, COUNT(*) FROM public.diakok GROUP BY iskola_id"
                )).all()
                for row in student_dist:
                    print(f"  - iskola_id (school_id): {row[0]}, Count: {row[1]}")
                
                # Print sample
                print("\nSample students in public.diakok:")
                sample_local = conn.execute(text(
                    "SELECT id, nev, oktatasi_azonosito, email, iskola_id, osztaly_id FROM public.diakok LIMIT 5"
                )).all()
                for s in sample_local:
                    print(f"  - ID: {s[0]} | Name: '{s[1]}' | OM: '{s[2]}' | Email: '{s[3]}' | iskola_id: {s[4]} | osztaly_id: {s[5]}")
            else:
                print("❌ Table 'public.diakok' does not exist!")

            # Check 7: Run simulated sync
            print("\n--- 🔄 SIMULATING SYNCHRONIZATION ---")
            # Let's test for a specific school_id or None
            for test_school_id in [None, 1, 2]:
                print(f"\nSimulating sync for school_id={test_school_id}:")
                if test_school_id is not None:
                    query = text("SELECT username, email, id, school_id FROM public.users WHERE role = 'student' AND school_id = :school_id")
                    params = {"school_id": test_school_id}
                else:
                    query = text("SELECT username, email, id, school_id FROM public.users WHERE role = 'student'")
                    params = {}
                
                res_users = conn.execute(query, params).all()
                print(f"  Query returned {len(res_users)} student rows from public.users.")
                
                if len(res_users) > 0:
                    matched_existing = 0
                    new_to_insert = 0
                    for u_row in res_users[:5]: # Show analysis for first 5
                        u_username = u_row[0]
                        u_email = u_row[1]
                        u_id = u_row[2]
                        db_school_id = u_row[3] or test_school_id
                        
                        # Check if matches existing student in public.diakok
                        existing = None
                        if u_username:
                            existing = conn.execute(
                                text("SELECT id, nev, iskola_id, osztaly_id FROM public.diakok WHERE oktatasi_azonosito = :username"),
                                {"username": u_username}
                            ).first()
                        if not existing and u_email:
                            existing = conn.execute(
                                text("SELECT id, nev, iskola_id, osztaly_id FROM public.diakok WHERE email = :email"),
                                {"email": u_email}
                            ).first()
                            
                        if existing:
                            matched_existing += 1
                            print(f"    - Student '{u_username}' matches existing local student ID {existing[0]} ('{existing[1]}'). Local school_id={existing[2]}, Class_id={existing[3]}. Portal school_id={db_school_id}")
                        else:
                            new_to_insert += 1
                            print(f"    - Student '{u_username}' ({u_email}) is NEW. Will be created. Portal school_id={db_school_id}")
                    
                    if len(res_users) > 5:
                        print(f"    ... and {len(res_users) - 5} more users")
                        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR during diagnostics: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_diagnostics()
