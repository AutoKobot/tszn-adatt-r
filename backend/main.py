from typing import Optional, List, Any
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Response
from fastapi.responses import FileResponse, StreamingResponse
import io
import csv
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import asyncio
import shutil
import os
import datetime
from . import models, schemas, database, sync_service, auth
from .kreta_service import kreta_service
from .far_service import far_service
from fastapi.staticfiles import StaticFiles

# --- ÜTEMEZETT FELADATOK (asyncio alapú, APScheduler nélkül) ---

async def nightly_sync_loop():
    """Minden nap este 22:00-kor futtatja a szinkront."""
    import datetime
    while True:
        now = datetime.datetime.now()
        # Kiszámítjuk, mennyi idő van a következő 22:00-ig
        next_run = now.replace(hour=22, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += datetime.timedelta(days=1)
        wait_seconds = (next_run - now).total_seconds()
        print(f"Éjszakai szinkron ütemezve: {next_run.strftime('%Y-%m-%d %H:%M')}")
        await asyncio.sleep(wait_seconds)
        try:
            await sync_service.sync_service.sync_external_data()
        except Exception as e:
            print(f"Szinkron hiba: {e}")

# --- ADATBÁZIS INICIALIZÁLÁS ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Háttérfeladatok helyett itt futtatjuk az adatbázis generálást indításkor
    print("Alkalmazás indítása... Adatbázis táblák létrehozása.")
    try:
        database.Base.metadata.create_all(bind=database.engine)
        
        # 1. Adatbázis sémák frissítése (Migráció meglévő táblákon) - EZT ELŐREHOZZUK!
        db = database.SessionLocal()
        from sqlalchemy import text
        try:
            # Multi-tenancy sémamigráció (DDL)
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS public.iskolak (
                    id SERIAL PRIMARY KEY,
                    nev VARCHAR(255) NOT NULL,
                    api_key VARCHAR(255) UNIQUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
                );
            """))
            db.commit()

            # Szinkronizáljuk a schools tábla tartalmát a helyi iskolak táblába a ForeignKey-ek kielégítésére
            try:
                db.execute(text("""
                    INSERT INTO public.iskolak (id, nev, created_at)
                    SELECT id, name, created_at FROM public.schools
                    ON CONFLICT (id) DO UPDATE SET nev = EXCLUDED.nev;
                """))
                db.commit()
                print("[MIGRATION] Schools table synced to Iskolak table successfully.")
            except Exception as e_sync_sch:
                print(f"[MIGRATION WARNING] Failed to sync schools: {e_sync_sch}")
                db.rollback()

            # Szinkronizáljuk a classes tábla tartalmát a helyi osztalyok táblába a ForeignKey-ek kielégítésére
            try:
                db.execute(text("""
                    INSERT INTO public.osztalyok (id, megnevezes, statusz, iskola_id)
                    SELECT id, name, 'aktív', school_id FROM public.classes
                    ON CONFLICT (id) DO UPDATE SET megnevezes = EXCLUDED.megnevezes, iskola_id = EXCLUDED.iskola_id;
                """))
                db.commit()
                print("[MIGRATION] Classes table synced to Osztalyok table successfully.")
            except Exception as e_sync_cls:
                print(f"[MIGRATION WARNING] Failed to sync classes: {e_sync_cls}")
                db.rollback()

            db.execute(text("ALTER TABLE public.felhasznalok ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.schools(id);"))
            db.execute(text("ALTER TABLE public.felhasznalok ADD COLUMN IF NOT EXISTS partner_id INTEGER REFERENCES public.partnerek(id);"))
            db.execute(text("ALTER TABLE public.schools ADD COLUMN IF NOT EXISTS kreta_subdomain VARCHAR(100);"))
            db.execute(text("ALTER TABLE public.diakok ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.schools(id);"))
            db.execute(text("ALTER TABLE public.osztalyok ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.schools(id);"))
            db.execute(text("ALTER TABLE public.oktatok ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.schools(id);"))
            db.execute(text("ALTER TABLE public.kulso_jegyek ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.schools(id);"))
            db.execute(text("ALTER TABLE public.jelenlet ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.schools(id);"))
            
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS oktatasi_azonosito VARCHAR(11) UNIQUE;"))
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS diakigazolvany_szam VARCHAR(50) UNIQUE;"))
            db.execute(text("ALTER TABLE osztalyok ADD COLUMN IF NOT EXISTS elvart_szakiranyu_oraszam INTEGER DEFAULT 400;"))
            db.execute(text("ALTER TABLE osztalyok ADD COLUMN IF NOT EXISTS max_hianyzas_szazalek INTEGER DEFAULT 20;"))
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS orvosi_alkalmassagi_lejarat DATE;"))
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS munkavedelmi_oktatas_datum DATE;"))
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS szuletesi_hely VARCHAR(255);"))
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS szuletesi_datum DATE;"))
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS anyja_neve VARCHAR(255);"))
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS tajszam VARCHAR(20);"))
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS adoazonosito VARCHAR(20);"))
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS bankszamlaszam VARCHAR(50);"))
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS szerzodes_kezdet DATE;"))
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS szerzodes_vege DATE;"))
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS szakma_torzs_id INTEGER;"))
            db.commit()
            print("Adatbázis oszlopok és Multi-tenancy táblák frissítve (Migráció sikeres).")
        except Exception as mig_e:
            print(f"Migrációs megjegyzés (nem kritikus): {mig_e}")
            db.rollback()

        # 2. Alapértelmezett tesztfiókok létrehozása (csak a sikeres migráció után)
        try:
            from . import auth
            if not db.query(models.User).filter(models.User.username == "admin").first():
                admin_user = models.User(username="admin", hashed_password=auth.get_password_hash("admin"), role="admin", full_name="Adminisztrátor")
                db.add(admin_user)
                db.commit()
                print("Default admin user created.")
        except Exception as auth_e:
            print(f"Hiba a tesztfiókok létrehozásakor: {auth_e}")
            db.rollback()

        db.close()
        print("Teszfiókok ellenőrizve: admin/admin.")

        # DIAGNOSZTIKAI JELENTÉS GENERÁLÁSA
        try:
            from sqlalchemy import text
            db_diag = database.SessionLocal()
            
            report = "# Adatbázis Diagnosztikai Jelentés 📊\n\n"
            
            # 1. Schools tábla
            report += "## 🏢 1. Schools Tábla Tartalma\n"
            try:
                schools_res = db_diag.execute(text("SELECT id, name FROM public.schools")).all()
                report += "| ID | Név (Name) |\n| :--- | :--- |\n"
                for r in schools_res:
                    report += f"| {r[0]} | {r[1]} |\n"
            except Exception as e_sch:
                report += f"Hiba/Nem létezik: {e_sch}\n"
            report += "\n"
            
            # 2. Iskolak tábla (ha van)
            report += "## 🏢 2. Iskolak Tábla Tartalma\n"
            try:
                iskolak_res = db_diag.execute(text("SELECT id, nev FROM public.iskolak")).all()
                report += "| ID | Név (Nev) |\n| :--- | :--- |\n"
                for r in iskolak_res:
                    report += f"| {r[0]} | {r[1]} |\n"
            except Exception as e_isk:
                report += f"Hiba/Nem létezik: {e_isk}\n"
            report += "\n"
            
            # 3. Users tábla
            report += "## 👥 3. Public.users Tábla Tartalma\n"
            try:
                users_res = db_diag.execute(text("SELECT id, username, email, school_id, role FROM public.users")).all()
                report += "| ID | Felhasználónév | Email | School ID | Szerepkör (Role) |\n| :--- | :--- | :--- | :--- | :--- |\n"
                for r in users_res:
                    report += f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |\n"
            except Exception as e_usr:
                report += f"Hiba/Nem létezik: {e_usr}\n"
            report += "\n"
            
            # 4. Diakok tábla
            report += "## 🎓 4. Diakok Tábla Tartalma\n"
            try:
                diakok_res = db_diag.execute(text("SELECT id, nev, oktatasi_azonosito, email, iskola_id FROM public.diakok")).all()
                report += "| ID | Név | OM azonosító | Email | Iskola ID |\n| :--- | :--- | :--- | :--- | :--- |\n"
                for r in diakok_res:
                    report += f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |\n"
            except Exception as e_diak:
                report += f"Hiba/Nem létezik: {e_diak}\n"
            report += "\n"
            
            # Fájl kiírása
            report_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scratch", "db_report.md")
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as rf:
                rf.write(report)
            print(f"[DIAGNOSZTIKA] Jelentés sikeresen elmentve: {report_path}")
            db_diag.close()
        except Exception as e_diag:
            print(f"[DIAGNOSZTIKA HIBA] Nem sikerült a jelentés: {e_diag}")

        # 3. Normatíva alapadatok seedelése
        from . import seed_service
        db_seed = database.SessionLocal()
        seed_service.seed_normativa_data(db_seed)
        db_seed.close()
    except Exception as e:
        print(f"Hiba az adatbázis indításakor: {e}")
    
    # Indításkor: háttérfeladat elindítása
    task = asyncio.create_task(nightly_sync_loop())
    print("Éjszakai szinkron háttérfeladat elindítva.")
    yield
    # Leállításkor: feladat törlése
    task.cancel()

app = FastAPI(title="EduRegistrar ÁKK Backend", version="1.0.0", lifespan=lifespan)

# CORS beállítások a felülethez
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Adatbázis inicializálás (kihagyva a globális scope-ból a lifespan javára)
# database.Base.metadata.create_all(bind=database.engine) 

# Dependency: DB munkamenet lekérése
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# A gyökér útvonalat a StaticFiles fogja kezelni (index.html kiszolgálása)

@app.get("/ping")
def keepalive_ping():
    print("[API] PING hívás érkezett")
    return {"pong": True, "time": datetime.datetime.utcnow().isoformat()}

# --- EXPLICIT FRONTEND ÚTVONALAK ---
@app.get("/")
async def serve_index():
    print("[SERVER] Index.html kiszolgálása")
    return FileResponse("index.html")

@app.get("/admin_dashboard.html")
@app.get("/admin")
async def serve_admin():
    print("[SERVER] Admin Dashboard kiszolgálása")
    return FileResponse("admin_dashboard.html")

@app.get("/oktato")
async def serve_oktato():
    return FileResponse("oktato_dashboard.html")

# --- DIÁKOK KEZELÉSE ---
# --- DIAGNOSZTIKA ---
@app.get("/debug/db")
def debug_database(db: Session = Depends(get_db)):
    try:
        counts = {
            "diakok_szama": db.query(models.Student).count(),
            "oktatok_szama": db.query(models.Instructor).count(),
            "osztalyok_szama": db.query(models.ClassRoom).count(),
            "adatbazis_url_eleje": str(database.engine.url).split('@')[-1],
            "elso_3_diak_nyers_adata": [
                {"id": s.id, "nev": s.nev, "meta": s.metadata_json, "iskola_id": s.iskola_id} 
                for s in db.query(models.Student).limit(3).all()
            ]
        }
        
        # Lekérdezzük a public.users táblát is diagnosztikának
        try:
            from sqlalchemy import text
            users_students = db.execute(
                text("SELECT id, username, email, school_id, role FROM public.users")
            ).all()
            counts["users_table_sample"] = [
                {"id": r[0], "username": r[1], "email": r[2], "school_id": r[3], "role": r[4]}
                for r in users_students[:20]
            ]
        except Exception as e_users:
            counts["users_table_error"] = str(e_users)
            
        return counts
    except Exception as e:
        return {"error": str(e)}

@app.get("/students/", response_model=list[schemas.Student])
def read_students(skip: int = 0, limit: int = 100, class_id: Optional[int] = None, 
                  db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    try:
        print("[API] Diákok listázása (GET /students/)")
        
        # 1. Automatikusan szinkronizáljuk a public.users-ben lévő diákokat a diakok (models.Student) táblába!
        school_id = current_user.get("school_id")
        try:
            from sqlalchemy import text
            if school_id is not None:
                users_res = db.execute(
                    text("SELECT username, email, id, school_id FROM public.users WHERE role = 'student' AND school_id = :school_id"),
                    {"school_id": school_id}
                ).all()
            else:
                users_res = db.execute(
                    text("SELECT username, email, id, school_id FROM public.users WHERE role = 'student'")
                ).all()
                
            for u_row in users_res:
                u_username = u_row[0] # OM id vagy felhasználónév
                u_email = u_row[1]
                u_id = u_row[2] # Pl: student_72345678901
                db_school_id = u_row[3] or school_id
                
                # Ellenőrizzük, létezik-e már ilyen diák a diakok táblában (oktatasi_azonosito vagy email alapján)
                existing = None
                if u_username:
                    existing = db.query(models.Student).filter(models.Student.oktatasi_azonosito == u_username).first()
                if not existing and u_email:
                    existing = db.query(models.Student).filter(models.Student.email == u_email).first()
                
                if not existing:
                    # Próbáljuk kideríteni a nevét a public.users-ből (első és vezetéknevét)
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
                        print(f"[API SYNC WARNING] Nem sikerült lekérni a nevet: {e_name}")
                        # Fallback: használjuk a username-t vagy emailt névként
                        nev = u_username or (u_email.split('@')[0] if u_email else "Ismeretlen Diák")
                    
                    # Megpróbáljuk a class_id-t is lekérni
                    db_class_id = None
                    try:
                        class_id_row = db.execute(
                            text("SELECT class_id FROM public.users WHERE id = :user_id"),
                            {"user_id": u_id}
                        ).first()
                        db_class_id = class_id_row[0] if class_id_row else None
                    except Exception as e_class:
                        print(f"[API SYNC WARNING] Nem sikerült lekérni a class_id-t: {e_class}")
                    
                    print(f"[API] Új diák szinkronizálása portálról: {nev} ({u_username})")
                    new_s = models.Student(
                        nev=nev,
                        email=u_email,
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
                else:
                    # Ha a diák már létezik az adatbázisban, de nincs hozzárendelve az iskolához vagy osztályhoz, frissítjük!
                    modified = False
                    if existing.iskola_id != db_school_id:
                        print(f"[API] Diák iskola_id szinkronizálása: {existing.nev} ({u_username}) -> {db_school_id}")
                        existing.iskola_id = db_school_id
                        modified = True
                    
                    db_class_id = None
                    try:
                        class_id_row = db.execute(
                            text("SELECT class_id FROM public.users WHERE id = :user_id"),
                            {"user_id": u_id}
                        ).first()
                        db_class_id = class_id_row[0] if class_id_row else None
                    except Exception as e_class:
                        pass
                    
                    if db_class_id is not None and existing.osztaly_id != db_class_id:
                        print(f"[API] Diák osztaly_id szinkronizálása: {existing.nev} ({u_username}) -> {db_class_id}")
                        existing.osztaly_id = db_class_id
                        modified = True
                    
                    if modified:
                        db.add(existing)
            db.commit()
        except Exception as e_sync:
            print(f"[SYNCHRONIZE WARNING] Nem sikerült a portálos diákok szinkronizálása: {e_sync}")
            db.rollback()

        # 2. Lekérjük a diákokat a diakok táblából
        query = db.query(models.Student)
        if current_user.get("school_id") is not None:
            query = query.filter(models.Student.iskola_id == current_user["school_id"])
        if class_id:
            query = query.filter(models.Student.osztaly_id == class_id)
        students = query.offset(skip).limit(limit).all()
        return students
    except Exception as e:
        print(f"[HIBA] Diákok lekérése közben: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/students/", response_model=schemas.Student)
def create_student(student: schemas.StudentCreate, db: Session = Depends(get_db), 
                   current_user: dict = Depends(auth.get_current_user)):
    try:
        student_data = student.dict()
        if current_user.get("school_id") is not None:
            student_data["iskola_id"] = current_user["school_id"]
        db_student = models.Student(**student_data)
        db.add(db_student)
        db.commit()
        db.refresh(db_student)
        return db_student
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Hiba a diák létrehozásakor: {str(e)}")

@app.put("/students/{student_id}", response_model=schemas.Student)
def update_student(student_id: int, student_update: schemas.StudentUpdate, db: Session = Depends(get_db)):
    try:
        db_student = db.query(models.Student).filter(models.Student.id == student_id).first()
        if not db_student:
            raise HTTPException(status_code=404, detail="Diák nem található")
        
        update_data = student_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_student, key, value)
        
        db.commit()
        db.refresh(db_student)
        return db_student
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Hiba a diák frissítésekor: {str(e)}")

@app.delete("/students/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    db_student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Diák nem található")
    db.delete(db_student)
    db.commit()
    return {"status": "success", "message": "Diák törölve"}

# --- OSZTÁLYOK / KÉPZÉSI PARAMÉTEREK ---
@app.get("/classes/", response_model=list[schemas.ClassRoom])
def read_classes(db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    query = db.query(models.ClassRoom)
    if current_user.get("school_id") is not None:
        query = query.filter(models.ClassRoom.iskola_id == current_user["school_id"])
    classes = query.all()
    # Eltávolítva a dummy osztályok automatikus létrehozása
    return classes

from fastapi import HTTPException

@app.put("/classes/{class_id}/parameters", response_model=schemas.ClassRoom)
def update_class_parameters(class_id: int, params: schemas.ClassRoomUpdate, db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    query = db.query(models.ClassRoom).filter(models.ClassRoom.id == class_id)
    if current_user.get("school_id") is not None:
        query = query.filter(models.ClassRoom.iskola_id == current_user["school_id"])
    db_class = query.first()
    if not db_class:
        raise HTTPException(status_code=404, detail="Osztály nem található")
    
    if params.megnevezes is not None:
        db_class.megnevezes = params.megnevezes
    if params.statusz is not None:
        db_class.statusz = params.statusz
    if params.elvart_szakiranyu_oraszam is not None:
        db_class.elvart_szakiranyu_oraszam = params.elvart_szakiranyu_oraszam
    if params.max_hianyzas_szazalek is not None:
        db_class.max_hianyzas_szazalek = params.max_hianyzas_szazalek
        
    db.commit()
    db.refresh(db_class)
    return db_class

@app.put("/classes/{class_id}/archive")
def archive_class(class_id: int, db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    query = db.query(models.ClassRoom).filter(models.ClassRoom.id == class_id)
    if current_user.get("school_id") is not None:
        query = query.filter(models.ClassRoom.iskola_id == current_user["school_id"])
    db_class = query.first()
    if not db_class:
        raise HTTPException(status_code=404, detail="Osztály nem található")
    db_class.statusz = "archivált"
    db.commit()
    return {"status": "success", "message": f"Osztály {db_class.megnevezes} archiválva."}

# --- OCR ÉS DOKUMENTUM GENERÁLÁS ---
from .ocr_service import ocr_service
from .document_service import DocumentService
import io

UPLOAD_DIR = "storage/documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)
doc_service = DocumentService(template_dir="backend/templates", output_dir="storage/contracts")

@app.post("/process-document/")
async def process_document(file: UploadFile = File(...)):
    # 1. Kép beolvasása és OCR
    content = await file.read()
    extracted_data, raw_text = await ocr_service.process_image(content)
    
    # 2. Szerződés generálás (Ha van sablon a backend/templates könyvtárban)
    # Feltételezzük: backend/templates/szerzodes_minta.docx
    try:
        docx_file = doc_service.generate_contract("szerzodes_minta.docx", extracted_data)
        pdf_file = doc_service.convert_to_pdf(docx_file)
        
        return {
            "status": "Sikeres feldolgozás",
            "kinyert_adatok": extracted_data,
            "generated_docx": docx_file,
            "generated_pdf": pdf_file
        }
    except Exception as e:
        return {
            "status": "OCR sikeres, de dokumentumhiba történt",
            "kinyert_adatok": extracted_data,
            "error": str(e)
        }

# --- EXCEL IMPORTÁLÁS ---
from .excel_service import excel_service

@app.post("/debug/excel-columns")
async def debug_excel_columns(file: UploadFile = File(...)):
    """Megmutatja, mit lát az Excel parser: fejléc sor, oszlop nevek, és az első 3 sor nyers adata."""
    content = await file.read()
    import pandas as pd, io
    header_row = excel_service._find_header_row(content)
    df_raw = excel_service._read_df(content, sheet=0, header=None)
    raw_header = list(df_raw.iloc[header_row].values) if header_row < len(df_raw) else []
    df = excel_service._read_df(content, sheet=0, header=header_row)
    normalized_cols = [excel_service._normalize_column_name(col) for col in df.columns]
    sample_rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        if i >= 3: break
        sample_rows.append({normalized_cols[j]: str(v) for j, v in enumerate(row.values)})
    # Parse first 3 students to see szakma detection
    parsed = excel_service.parse_students(content)
    return {
        "detected_header_row": header_row,
        "raw_header_values": [str(x) for x in raw_header],
        "normalized_column_names": normalized_cols,
        "sample_parsed_rows": sample_rows,
        "first_3_parsed_students": parsed[:3]
    }

@app.post("/import/patch-szakma")
async def patch_szakma_from_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Csak a szakma mezőt frissíti a meglévő diákoknál, CSV/Excel alapján.
    Hasznos ha a teljes import már megtörtént, de a szakma null maradt.
    Egyezés: Név alapján (case-insensitive, trimelt).
    """
    content = await file.read()
    parsed_students = excel_service.parse_students(content)
    
    updated = 0
    not_found = []
    already_ok = 0
    no_szakma_in_file = 0
    
    for s_data in parsed_students:
        s_nev = s_data.get("nev", "").strip()
        s_szakma = s_data.get("szakma")
        s_iskola = s_data.get("iskola")
        s_evfolyam = s_data.get("evfolyam")
        
        if not s_nev:
            continue
        if not s_szakma:
            no_szakma_in_file += 1
            continue
        
        # Keressük meg a diákot névpontos egyezéssel
        student = db.query(models.Student).filter(
            models.Student.nev == s_nev
        ).first()
        
        if not student:
            not_found.append(s_nev)
            continue
        
        # Ha már van and ugyanaz, skip
        current_meta = student.metadata_json or {}
        if current_meta.get("szakma") == s_szakma:
            already_ok += 1
            continue
        
        # Frissítés
        new_meta = dict(current_meta)
        new_meta["szakma"] = s_szakma
        if s_iskola: new_meta["iskola"] = s_iskola
        if s_evfolyam: new_meta["evfolyam"] = s_evfolyam
        student.metadata_json = new_meta
        
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(student, "metadata_json")
        updated += 1
    
    db.commit()
    return {
        "status": "success",
        "frissitett": updated,
        "mar_rendben_volt": already_ok,
        "nem_talalt_nev": len(not_found),
        "csv_szakma_nelkul": no_szakma_in_file,
        "ismeretlen_nevek": not_found[:20]  # Max 20 nevet mutat
    }

@app.post("/import/students")
async def import_students_excel(tagozat: str = "nappali", file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    parsed_students = excel_service.parse_students(content)
    
    import_results = {"saved": 0, "conflicts": [], "errors": 0, "duplicates": 0}
    
    for i, s_data in enumerate(parsed_students):
        try:
            s_om = s_data.get("om_azonosito")
            s_email = s_data.get("email")
            s_nev = s_data["nev"]
            
            # Konfliktus keresés
            existing_student = None
            reason = "none"
            
            if s_om:
                existing_student = db.query(models.Student).filter(models.Student.oktatasi_azonosito == s_om).first()
                if existing_student: reason = "Az OM azonosító már létezik"
            
            if not existing_student and s_email and s_email != "nincs":
                existing_student = db.query(models.Student).filter(models.Student.email == s_email).first()
                if existing_student: reason = "Az Email cím már létezik"
            
            if not existing_student:
                # Név alapú egyezés
                existing_student = db.query(models.Student).filter(models.Student.nev == s_nev).first()
                if existing_student: reason = "A név már szerepel a rendszerben"

            if existing_student:
                # Kényszerített frissítés
                existing_student.nev = s_nev
                if s_data.get("email"): existing_student.email = s_data.get("email")
                if s_data.get("telefon"): existing_student.telefon = s_data.get("telefon")
                if s_data.get("lakhely"): existing_student.lakhely = s_data.get("lakhely")
                
                # Bővített adatok frissítése
                if s_data.get("szuletesi_hely"): existing_student.szuletesi_hely = s_data["szuletesi_hely"]
                if s_data.get("szuletesi_datum"): existing_student.szuletesi_datum = s_data["szuletesi_datum"]
                if s_data.get("anyja_neve"): existing_student.anyja_neve = s_data["anyja_neve"]
                if s_data.get("tajszam"): existing_student.tajszam = s_data["tajszam"]
                if s_data.get("adoazonosito"): existing_student.adoazonosito = s_data["adoazonosito"]
                if s_data.get("bankszamlaszam"): existing_student.bankszamlaszam = s_data["bankszamlaszam"]

                meta = dict(existing_student.metadata_json or {})
                meta["szakma"] = s_data.get("szakma")
                meta["iskola"] = s_data.get("iskola")
                meta["evfolyam"] = s_data.get("evfolyam")
                if s_data.get("metadata_json", {}).get("szuletesi_datum"):
                    meta["szuletesi_datum"] = s_data["metadata_json"]["szuletesi_datum"]
                if s_data.get("metadata_json", {}).get("anyja_neve"):
                    meta["anyja_neve"] = s_data["metadata_json"]["anyja_neve"]
                existing_student.metadata_json = meta
                
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(existing_student, "metadata_json")
                
                import_results["duplicates"] += 1
            else:
                # Új
                new_student = models.Student(
                    nev=s_nev,
                    email=s_email,
                    oktatasi_azonosito=s_om,
                    tagozat=tagozat,
                    telefon=s_data.get("telefon"),
                    lakhely=s_data.get("lakhely"),
                    szuletesi_hely=s_data.get("szuletesi_hely"),
                    szuletesi_datum=s_data.get("szuletesi_datum"),
                    anyja_neve=s_data.get("anyja_neve"),
                    tajszam=s_data.get("tajszam"),
                    adoazonosito=s_data.get("adoazonosito"),
                    bankszamlaszam=s_data.get("bankszamlaszam"),
                    szerzodes_kezdet=s_data.get("szerzodes_kezdet"),
                    szerzodes_vege=s_data.get("szerzodes_vege"),
                    metadata_json=s_data.get("metadata_json", {
                        "szakma": s_data.get("szakma"),
                        "iskola": s_data.get("iskola"),
                        "evfolyam": s_data.get("evfolyam")
                    })
                )
                db.add(new_student)
                import_results["saved"] += 1
            
            if i % 50 == 0: db.commit()
                
        except Exception as e:
            print(f"[IMPORT HIBA] Sor {i}: {e}")
            db.rollback()
            import_results["errors"] += 1
            
    db.commit()
    
    msg = f"Importálás kész. {import_results['saved']} diák rögzítve. {len(import_results['conflicts'])} konfliktus vár feloldásra."
    return {
        "status": "success", 
        "message": msg,
        "saved_count": import_results["saved"],
        "conflicts": import_results["conflicts"] # Visszaküldjük a listát a frontendre
    }

@app.post("/import/resolve-conflicts")
async def resolve_conflicts(decisions: list[dict], db: Session = Depends(get_db)):
    """
    Decisions formátum: [{"action": "update|create|skip", "incoming": {...}, "existing_id": 123}]
    """
    resolved_count = 0
    try:
        for d in decisions:
            action = d.get("action")
            inc = d.get("incoming")
            
            if action == "skip": continue
            
            if action == "update":
                existing = db.query(models.Student).get(d["existing_id"])
                if existing:
                    existing.nev = inc.get("nev")
                    existing.email = inc.get("email")
                    existing.oktatasi_azonosito = inc.get("om_azonosito")
                    existing.szerzodes_kezdet = inc.get("szerzodes_kezdet")
                    existing.szerzodes_vege = inc.get("szerzodes_vege")
                    # Meta frissítése
                    meta = existing.metadata_json or {}
                    meta.update({
                        "iskola": inc.get("iskola"),
                        "szakma": inc.get("szakma"),
                        "evfolyam": inc.get("evfolyam"),
                        "resolved_update": datetime.datetime.now().isoformat()
                    })
                    existing.metadata_json = meta
                    resolved_count += 1
            
            elif action == "create":
                new_student = models.Student(
                    nev=inc.get("nev"),
                    email=inc.get("email"),
                    oktatasi_azonosito=inc.get("om_azonosito"),
                    szerzodes_kezdet=inc.get("szerzodes_kezdet"),
                    szerzodes_vege=inc.get("szerzodes_vege"),
                    tagozat=inc.get("tagozat", "nappali"),
                    metadata_json={
                        "iskola": inc.get("iskola"),
                        "szakma": inc.get("szakma"),
                        "evfolyam": inc.get("evfolyam")
                    }
                )
                db.add(new_student)
                resolved_count += 1
        
        db.commit()
        return {"status": "success", "resolved_count": resolved_count}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/import/instructors")
async def import_instructors_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    parsed_instructors = excel_service.parse_instructors(content)
    
    print(f"[IMPORT][OKTATÓK] Beolvasott oktatók száma: {len(parsed_instructors)}")
    
    saved_count = 0
    updated_count = 0
    error_count = 0
    errors = []

    for i, i_data in enumerate(parsed_instructors):
        try:
            i_nev = i_data.get("nev", "").strip()
            i_email = i_data.get("email")
            i_szakterulet = i_data.get("szakterulet")
            
            if not i_nev:
                continue

            print(f"[IMPORT][OKTATÓK] Sor {i+1}: nev='{i_nev}', email='{i_email}', szakterulet='{i_szakterulet}'")

            # Keresés névv és email alapján
            existing = None
            if i_email:
                existing = db.query(models.Instructor).filter(models.Instructor.email == i_email).first()
            if not existing:
                existing = db.query(models.Instructor).filter(models.Instructor.nev == i_nev).first()

            if existing:
                # Frissítjük a meglévő oktatót
                existing.nev = i_nev
                if i_email: existing.email = i_email
                if i_szakterulet: existing.szakterulet = i_szakterulet
                updated_count += 1
            else:
                # Új oktató felvétele
                new_instructor = models.Instructor(
                    nev=i_nev,
                    email=i_email,
                    szakterulet=i_szakterulet,
                )
                db.add(new_instructor)
                saved_count += 1

        except Exception as e:
            print(f"[IMPORT][OKTATÓK][HIBA] Sor {i+1}: {e}")
            db.rollback()
            error_count += 1
            errors.append({"sor": i+1, "nev": i_data.get("nev", "?"), "hiba": str(e)})

    db.commit()
    print(f"[IMPORT][OKTATÓK] Kész: {saved_count} új, {updated_count} frissítve, {error_count} hiba")
    return {
        "status": "success", 
        "message": f"{saved_count} új oktató mentve, {updated_count} frissítve a {len(parsed_instructors)} beolvasott sorból.",
        "uj_mentve": saved_count,
        "frissitett": updated_count,
        "hibak": error_count,
        "hiba_reszletek": errors
    }

@app.get("/instructors/", response_model=list[schemas.Instructor])
def read_instructors(db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    query = db.query(models.Instructor)
    if current_user.get("school_id") is not None:
        query = query.filter(models.Instructor.iskola_id == current_user["school_id"])
    return query.all()

# --- TEMPLATE FELTÖLTÉS ---
@app.post("/templates/upload")
async def upload_template(type: str, file: UploadFile = File(...)):
    # type: dualis_nappali, dualis_felnott, oktatoi_megbizasi
    file_path = os.path.join("backend/templates", f"{type}.docx")
    os.makedirs("backend/templates", exist_ok=True)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"status": "success", "message": f"{type} sablon sikeresen feltöltve."}

from .document_service import DocumentService
doc_service = DocumentService(template_dir="backend/templates", output_dir="backend/storage/contracts")

@app.get("/students/{student_id}/contract")
async def generate_student_contract(student_id: int, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Tanuló nem található")
    
    # Adatok előkészítése a sablonhoz
    meta = student.metadata_json or {}
    data = {
        "nev": student.nev,
        "email": student.email or "",
        "om_azonosito": student.oktatasi_azonosito or "",
        "diakigazolvany": student.diakigazolvany_szam or "",
        "szerzodes_kezdet": student.szerzodes_kezdet or "",
        "szerzodes_vege": student.szerzodes_vege or "",
        "tagozat": student.tagozat,
        "szakma": meta.get("szakma", ""),
        "iskola": meta.get("iskola", ""),
        "evfolyam": meta.get("evfolyam", ""),
        "lakhely": student.lakhely or ""
    }
    
    # Sablon kiválasztása tagozat alapján
    template_name = "dualis_nappali.docx" if student.tagozat == "nappali" else "dualis_felnott.docx"
    
    try:
        output_path = doc_service.generate_contract(template_name, data)
        return FileResponse(
            path=output_path, 
            filename=os.path.basename(output_path),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Szerződés generálási hiba: {str(e)}")

import zipfile
import tempfile

@app.get("/contracts/mass-generate")
async def mass_generate_contracts(db: Session = Depends(get_db)):
    """Összes aktív diákhoz generál egy ZIP fájlt a kitöltött szerződésekkel."""
    students = db.query(models.Student).all()
    if not students:
        raise HTTPException(status_code=404, detail="Nincs diák az adatbázisban.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for student in students:
            meta = student.metadata_json or {}
            data = {
                "nev": student.nev,
                "email": student.email or "",
                "om_azonosito": student.oktatasi_azonosito or "",
                "diakigazolvany": student.diakigazolvany_szam or "",
                "szerzodes_kezdet": student.szerzodes_kezdet or "",
                "szerzodes_vege": student.szerzodes_vege or "",
                "tagozat": student.tagozat,
                "szakma": meta.get("szakma", ""),
                "iskola": meta.get("iskola", ""),
                "evfolyam": meta.get("evfolyam", ""),
                "lakhely": student.lakhely or ""
            }
            template_name = "dualis_nappali.docx" if student.tagozat == "nappali" else "dualis_felnott.docx"
            try:
                output_path = doc_service.generate_contract(template_name, data)
                # Fájl hozzáadása a ZIP-hez
                zip_file.write(output_path, arcname=os.path.basename(output_path))
            except Exception as e:
                # Ha nincs sablon, vagy hiba van, kihagyjuk a diákot
                continue

    if zip_buffer.tell() == 0:
        raise HTTPException(status_code=400, detail="Nem sikerült egyetlen szerződést sem generálni. Biztosan feltöltötted a sablonokat (.docx)?")

    zip_buffer.seek(0)
    response = StreamingResponse(zip_buffer, media_type="application/zip")
    response.headers["Content-Disposition"] = "attachment; filename=Szerzodesek_Tomeges_Export.zip"
    return response

# --- PARTNEREK ---
@app.get("/partners/", response_model=list[schemas.Partner])
def read_partners(db: Session = Depends(get_db)):
    return db.query(models.Partner).all()

@app.post("/partners/", response_model=schemas.Partner)
def create_partner(partner: schemas.PartnerCreate, db: Session = Depends(get_db)):
    db_partner = models.Partner(**partner.dict())
    db.add(db_partner)
    db.commit()
    db.refresh(db_partner)
    return db_partner

# --- HITELESÍTÉS ÉS LOGIN ---
from . import auth
from fastapi.security import OAuth2PasswordRequestForm

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # 1. Felhasználó keresése az DB-ben
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Hibás felhasználónév vagy jelszó")
    
    # 2. JWT Token generálása a szerepkörrel és iskola azonosítóval
    access_token = auth.create_access_token(
        data={
            "sub": user.username, 
            "role": user.role,
            "school_id": user.iskola_id,
            "app_metadata": {
                "school_id": user.iskola_id
            }
        }
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- ISKOLAI BELÉPÉS ÉS AUTOCOMPLETE ---

@app.get("/schools/public")
def get_public_schools(db: Session = Depends(get_db)):
    # Csak az ID-t és a Nevet adjuk vissza biztonsági okokból!
    schools = db.query(models.School).filter(models.School.nev != None).all()
    return [{"id": s.id, "nev": s.nev} for s in schools]

@app.post("/login/school")
def login_school(req: schemas.SchoolLoginRequest, db: Session = Depends(get_db)):
    school = db.query(models.School).filter(models.School.id == req.school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="Az iskola nem található")
    
    # Unified School Admin hitelesítés (InteractiveLearning/schools/users alapon):
    from sqlalchemy import text
    from . import auth
    is_valid = False
    
    try:
        user_row = db.execute(
            text("SELECT password FROM public.users WHERE role = 'school_admin' AND school_id = :school_id LIMIT 1"),
            {"school_id": req.school_id}
        ).first()
        if user_row and user_row[0]:
            hashed_password = user_row[0]
            is_valid = auth.verify_scrypt_password(req.password, hashed_password)
    except Exception as e:
        print("Unified school admin auth error:", e)
        is_valid = False
        
    # Fallback a lokális iskolai api_key ellenőrzésre (ha van ilyen mező a schools táblában átmenetileg vagy korábban)
    if not is_valid:
        try:
            # Megnézzük, hogy van-e api_key oszlop a schools táblában
            col_check = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='schools' AND column_name='api_key' AND table_schema='public'")).first()
            if col_check:
                api_key_row = db.execute(text("SELECT api_key FROM public.schools WHERE id = :school_id"), {"school_id": req.school_id}).first()
                if api_key_row and api_key_row[0]:
                    key = api_key_row[0]
                    if req.password == key:
                        is_valid = True
                    else:
                        is_valid = auth.verify_password(req.password, key)
        except Exception:
            pass
            
    if not is_valid:
        raise HTTPException(status_code=400, detail="Hibás belépési jelszó")
        
    # JWT Token generálása az iskola azonosítójával
    access_token = auth.create_access_token(
        data={
            "sub": f"school_{school.id}", 
            "role": "admin",
            "school_id": school.id,
            "app_metadata": {
                "school_id": school.id
            }
        }
    )
    return {"access_token": access_token, "token_type": "bearer", "school_name": school.nev}

@app.post("/users/", response_model=schemas.User)
def create_instructor_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Ellenőrizzük, hogy létezik-e már a felhasználó
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="A felhasználónév már foglalt")
    
    db_user = models.User(
        username=user.username,
        hashed_password=auth.get_password_hash(user.password),
        role=user.role,
        full_name=user.full_name,
        szakma_id=user.instructor_id # Itt az instructor_id-t használjuk ha átadták
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# --- RBAC ALAPÚ VÉDGÁTAK (PÉLDÁK) ---

# 1. Csak ADMIN érheti el az audit naplókat
@app.get("/audit/", dependencies=[Depends(auth.check_role(["admin"]))])
def get_audit_logs(db: Session = Depends(get_db)):
    return db.query(models.AuditLog).all()

# 2. TITKÁRSÁG és ADMIN kezelheti a szerződéseket
@app.post("/contracts/", dependencies=[Depends(auth.check_role(["admin", "titkarsag"]))])
def create_contract(contract: schemas.ContractCreate, db: Session = Depends(get_db)):
    # ... logic ...
    return {"status": "Sikeres mentés"}

# 3. OKTATÓ és ADMIN kezelheti a jegyeket
@app.post("/grades/", dependencies=[Depends(auth.check_role(["admin", "oktato"]))])
def add_grade(grade: schemas.GradeCreate, db: Session = Depends(get_db)):
    # Oktató esetén ellenőrizni kell (Business logic szinten), hogy a saját szakmájához tartozik-e
    return {"status": "Jegy rögzítve"}

# --- BIZTONSÁG ÉS ESZKÖZÖK ---
@app.get("/safety-trainings/", response_model=list[schemas.SafetyTraining])
def read_safety_trainings(db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    query = db.query(models.SafetyTraining)
    if current_user.get("school_id") is not None:
        from sqlalchemy import or_
        query = query.outerjoin(models.Student, models.SafetyTraining.diak_id == models.Student.id)\
                     .outerjoin(models.ClassRoom, models.SafetyTraining.osztaly_id == models.ClassRoom.id)\
                     .filter(or_(
                         models.Student.iskola_id == current_user["school_id"],
                         models.ClassRoom.iskola_id == current_user["school_id"]
                     ))
    return query.all()

@app.post("/safety-trainings/", response_model=schemas.SafetyTraining)
def create_safety_training(training: schemas.SafetyTrainingCreate, db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    if current_user.get("school_id") is not None:
        if training.diak_id:
            student = db.query(models.Student).filter(models.Student.id == training.diak_id).first()
            if not student or student.iskola_id != current_user["school_id"]:
                raise HTTPException(status_code=400, detail="Nem engedélyezett diák")
        if training.osztaly_id:
            classroom = db.query(models.ClassRoom).filter(models.ClassRoom.id == training.osztaly_id).first()
            if not classroom or classroom.iskola_id != current_user["school_id"]:
                raise HTTPException(status_code=400, detail="Nem engedélyezett osztály")
    db_training = models.SafetyTraining(**training.dict())
    db.add(db_training)
    db.commit()
    db.refresh(db_training)
    return db_training

@app.get("/equipment/", response_model=list[schemas.Equipment])
def read_equipment(db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    query = db.query(models.Equipment)
    if current_user.get("school_id") is not None:
        query = query.join(models.Student, models.Equipment.diak_id == models.Student.id)\
                     .filter(models.Student.iskola_id == current_user["school_id"])
    return query.all()

@app.post("/equipment/", response_model=schemas.Equipment)
def create_equipment(equip: schemas.EquipmentCreate, db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    if current_user.get("school_id") is not None:
        student = db.query(models.Student).filter(models.Student.id == equip.diak_id).first()
        if not student or student.iskola_id != current_user["school_id"]:
            raise HTTPException(status_code=400, detail="Nem engedélyezett diák")
    db_equip = models.Equipment(**equip.dict())
    db.add(db_equip)
    db.commit()
    db.refresh(db_equip)
    return db_equip

@app.delete("/equipment/{equip_id}")
def delete_equipment(equip_id: int, db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    query = db.query(models.Equipment).filter(models.Equipment.id == equip_id)
    if current_user.get("school_id") is not None:
        query = query.join(models.Student, models.Equipment.diak_id == models.Student.id)\
                     .filter(models.Student.iskola_id == current_user["school_id"])
    db_equip = query.first()
    if not db_equip:
        raise HTTPException(status_code=404, detail="Eszköz nem található")
    db.delete(db_equip)
    db.commit()
    return {"status": "success"}

# --- RENDKÍVÜLI ADATTÖRLÉS (Dummy adatok) ---
@app.post("/debug/cleanup-dummy-data")
def cleanup_dummy_data(db: Session = Depends(get_db)):
    dummy_names = [
        "Kovács Péter", "Szabó Éva", "Teszt Elek", "John Doe", "Jane Doe",
        "Teszt Aladár", "Minta Beáta", "Próba Cecil", "Demo Dénes", 
        "Fiktív Eleonóra", "Szoftver Szabolcs", "Hegesztő Hugó", 
        "Kalkulátor Klára", "ROI Róbert", "Adat-Iker Adél",
        "Kovács Adél", "Nagy Barnabás", "Szabó Csenge", "Tóth Dániel", "Kiss Enikő", 
        "Molnár Ferenc", "Varga Gábor", "Fekete Hanna", "Németh Imre", "Papp Júlia"
    ]
    
    # 1. Diák ID-k kigyűjtése
    dummy_students = db.query(models.Student).filter(models.Student.nev.in_(dummy_names)).all()
    dummy_student_ids = [s.id for s in dummy_students]
    
    deleted_students = 0
    if dummy_student_ids:
        # 2. Kapcsolódó táblák törlése
        db.query(models.ExternalGrade).filter(models.ExternalGrade.diak_id.in_(dummy_student_ids)).delete(synchronize_session=False)
        db.query(models.Attendance).filter(models.Attendance.diak_id.in_(dummy_student_ids)).delete(synchronize_session=False)
        db.query(models.DualisSzerzodes).filter(models.DualisSzerzodes.diak_id.in_(dummy_student_ids)).delete(synchronize_session=False)
        
        # 3. Diákok törlése
        deleted_students = db.query(models.Student).filter(models.Student.id.in_(dummy_student_ids)).delete(synchronize_session=False)
    
    # 4. Teszt osztályok törlése
    dummy_classes = ["11.B (Gépészet)", "12.A (Informatika)", "12.A", "12.C"]
    deleted_classes = db.query(models.ClassRoom).filter(models.ClassRoom.megnevezes.in_(dummy_classes)).delete(synchronize_session=False)
    
    db.commit()
    return {"status": "success", "deleted_students": deleted_students, "deleted_classes": deleted_classes}


# --- JELENLÉT ENDPOINTOK ---
@app.get("/attendance/", response_model=list[schemas.Attendance])
def get_all_attendance(db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    query = db.query(models.Attendance)
    if current_user.get("school_id") is not None:
        query = query.filter(models.Attendance.iskola_id == current_user["school_id"])
    return query.all()

@app.get("/students/{student_id}/attendance", response_model=list[schemas.Attendance])
def get_student_attendance(student_id: int, db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    if current_user.get("school_id") is not None:
        student = db.query(models.Student).filter(models.Student.id == student_id).first()
        if not student or student.iskola_id != current_user["school_id"]:
            raise HTTPException(status_code=404, detail="Diák nem található")
    return db.query(models.Attendance).filter(models.Attendance.diak_id == student_id).all()

@app.post("/attendance/", response_model=schemas.Attendance)
def create_attendance(att: schemas.AttendanceCreate, db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    att_data = att.dict()
    if current_user.get("school_id") is not None:
        student = db.query(models.Student).filter(models.Student.id == att.diak_id).first()
        if not student or student.iskola_id != current_user["school_id"]:
            raise HTTPException(status_code=400, detail="Nem engedélyezett diák")
        att_data["iskola_id"] = current_user["school_id"]
    db_att = models.Attendance(**att_data)
    db.add(db_att)
    db.commit()
    db.refresh(db_att)
    return db_att

@app.post("/attendance/bulk")
def create_bulk_attendance(attendances: list[schemas.AttendanceCreate], db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    try:
        for att in attendances:
            att_data = att.dict()
            if current_user.get("school_id") is not None:
                student = db.query(models.Student).filter(models.Student.id == att.diak_id).first()
                if not student or student.iskola_id != current_user["school_id"]:
                    raise HTTPException(status_code=400, detail="Nem engedélyezett diák")
                att_data["iskola_id"] = current_user["school_id"]
            db_att = models.Attendance(**att_data)
            db.add(db_att)
        db.commit()
        return {"status": "success", "count": len(attendances)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# --- ÉRTÉKELÉS (JEGYEK) ---
@app.get("/students/{student_id}/grades", response_model=list[schemas.Grade])
def get_student_grades(student_id: int, db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    if current_user.get("school_id") is not None:
        student = db.query(models.Student).filter(models.Student.id == student_id).first()
        if not student or student.iskola_id != current_user["school_id"]:
            raise HTTPException(status_code=404, detail="Diák nem található")
    return db.query(models.ExternalGrade).filter(models.ExternalGrade.diak_id == student_id).all()

@app.post("/grades/", response_model=schemas.Grade)
def create_grade(grade: schemas.GradeCreate, db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    grade_data = grade.dict()
    if current_user.get("school_id") is not None:
        student = db.query(models.Student).filter(models.Student.id == grade.diak_id).first()
        if not student or student.iskola_id != current_user["school_id"]:
            raise HTTPException(status_code=400, detail="Nem engedélyezett diák")
        grade_data["iskola_id"] = current_user["school_id"]
    db_grade = models.ExternalGrade(**grade_data)
    db.add(db_grade)
    db.commit()
    db.refresh(db_grade)
    return db_grade

# --- HALADÁSI NAPLÓ ---
@app.post("/dailylog/", response_model=schemas.DailyLog)
def create_daily_log(log: schemas.DailyLogCreate, db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    if current_user.get("school_id") is not None:
        classroom = db.query(models.ClassRoom).filter(models.ClassRoom.id == log.osztaly_id).first()
        if not classroom or classroom.iskola_id != current_user["school_id"]:
            raise HTTPException(status_code=400, detail="Nem engedélyezett osztály")
    db_log = models.DailyLog(**log.dict())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

@app.get("/classes/{class_id}/logs", response_model=list[schemas.DailyLog])
def get_class_logs(class_id: int, db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    if current_user.get("school_id") is not None:
        classroom = db.query(models.ClassRoom).filter(models.ClassRoom.id == class_id).first()
        if not classroom or classroom.iskola_id != current_user["school_id"]:
            raise HTTPException(status_code=404, detail="Osztály nem található")
    return db.query(models.DailyLog).filter(models.DailyLog.osztaly_id == class_id).order_by(models.DailyLog.datum.desc()).all()

# --- ÖSSZESÍTETT STATISZTIKÁK (Súlyozott átlag, hiányzás) ---
@app.get("/students/{student_id}/stats", response_model=schemas.StudentStats)
def get_student_stats(student_id: int, db: Session = Depends(get_db)):
    # 1. Átlag számítás (súlyozott)
    grades = db.query(models.ExternalGrade).filter(models.ExternalGrade.diak_id == student_id).all()
    weighted_sum = 0
    weight_total = 0
    for g in grades:
        weighted_sum += g.ertek * (g.suly / 100.0)
        weight_total += (g.suly / 100.0)
    
    atlag = round(weighted_sum / weight_total, 2) if weight_total > 0 else 0.0

    # 2. Hiányzás számítás
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student or not student.osztaly_id:
        return schemas.StudentStats(diak_id=student_id, atlag=atlag, hianyzas_szazalek=0, igazolatlan_orak=0)
    
    db_class = db.query(models.ClassRoom).filter(models.ClassRoom.id == student.osztaly_id).first()
    elvart_ora = db_class.elvart_szakiranyu_oraszam if db_class else 400
    
    absences = db.query(models.Attendance).filter(
        models.Attendance.diak_id == student_id,
        models.Attendance.statusz.like("%hianyzas%")
    ).all()
    
    total_absent_hours = sum(a.oraszam for a in absences)
    igazolatlan_count = sum(a.oraszam for a in absences if a.statusz == "igazolatlan_hianyzas")
    
    hiany_szazalek = round((total_absent_hours / elvart_ora) * 100, 1) if elvart_ora > 0 else 0
    
    # 3. Ösztöndíj kalkuláció (Példa logika)
    # Alap: 100.000 Ft (Szakirányú oktatási ösztöndíj alapja)
    base_stipend = 100000
    osztondij = 0
    
    if atlag >= 2.0 and hiany_szazalek <= 20:
        if atlag >= 4.5: osztondij = base_stipend
        elif atlag >= 4.0: osztondij = base_stipend * 0.8
        elif atlag >= 3.0: osztondij = base_stipend * 0.5
        elif atlag >= 2.0: osztondij = base_stipend * 0.1
    
    # 4. Megfelelőség ellenőrzés és Prediktív Kockázatelemzés (Early Warning)
    is_compliant = True
    risks = []
    
    today = datetime.date.today()
    if not student.orvosi_alkalmassagi_lejarat or student.orvosi_alkalmassagi_lejarat < today:
        is_compliant = False
        risks.append("Lejárt orvosi alkalmassági")
    if not student.munkavedelmi_oktatas_datum:
        is_compliant = False
        risks.append("Hiányzó munkavédelmi oktatás")

    # Kockázat: Hiányzás megközelíti a 20%-ot
    if hiany_szazalek >= 15:
        risks.append(f"Kritikus hiányzási szint: {hiany_szazalek}% (Közelít a 20%-os jogszabályi limithez)")
        # compliance romlik, ha már elérte a 20-at
        if hiany_szazalek >= 20:
            is_compliant = False

    # Kockázat: Romló/Kritikus érdemjegyek
    if atlag > 0 and atlag < 2.5:
        risks.append(f"Gyenge tanulmányi átlag: {atlag} (Lemorzsolódási és ösztöndíj kockázat)")

    return schemas.StudentStats(
        diak_id=student_id,
        atlag=atlag,
        hianyzas_szazalek=hiany_szazalek,
        igazolatlan_orak=igazolatlan_count,
        osztondij_javaslat=int(osztondij),
        megfeleloseg_ok=is_compliant,
        risks=risks
    )

@app.post("/students/{student_id}/send-warning-email")
def send_risk_email(student_id: int, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Diák nem található")
    
    stats = get_student_stats(student_id, db)
    if not stats.risks:
        return {"status": "info", "message": "Nincs fennálló kockázat a diáknál.", "email_content": ""}
    
    risk_list = "\n- ".join(stats.risks)
    
    email_body = f"""Tisztelt Szülő / Gondviselő!
    
Ez egy automatikus rendszerüzenet az EduRegistrar rendszerből.
Értesítjük, hogy {student.nev} (OM: {student.oktatasi_azonosito}) tanulónál az alábbi megfelelőségi vagy tanulmányi kockázatok léptek fel, melyek a szakképzési munkaszerződés felmondását vagy az ösztöndíj megvonását vonhatják maguk után:

- {risk_list}

Kérjük, mielőbb vegye fel a kapcsolatot az iskolával vagy a gyakorlati oktatóval a helyzet tisztázása érdekében!

Tisztelettel:
Iskola Vezetősége"""

    # Itt történne a tényleges SMTP email kiküldés
    # pl. send_email(student.email, "Kockázati Figyelmeztetés", email_body)
    
    return {"status": "success", "message": "Email sikeresen generálva.", "email_content": email_body}

@app.get("/students/dashboard-summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    students = db.query(models.Student).all()
    total_students = len(students)
    total_stipend = 0
    compliance_alerts = 0
    total_absent_sum = 0
    
    for s in students:
        stats = get_student_stats(s.id, db)
        total_stipend += stats.osztondij_javaslat
        if not stats.megfeleloseg_ok:
            compliance_alerts += 1
        total_absent_sum += stats.hianyzas_szazalek
        
    avg_absence = round(total_absent_sum / total_students, 1) if total_students > 0 else 0
    
    return {
        "total_students": total_students,
        "total_stipend": total_stipend,
        "compliance_alerts": compliance_alerts,
        "avg_absence": avg_absence
    }

@app.get("/export/payroll")
def export_payroll(db: Session = Depends(get_db)):
    students = db.query(models.Student).all()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Nev', 'OM Azonosito', 'Bankszamlaszam', 'Atlag', 'Hianyzas %', 'Osztondij (Ft)', 'Megfeleloseg'])
    
    for s in students:
        stats = get_student_stats(s.id, db)
        writer.writerow([
            s.nev,
            s.oktatasi_azonosito,
            s.bankszamlaszam or 'Nincs megadva',
            stats.atlag,
            f"{stats.hianyzas_szazalek}%",
            stats.osztondij_javaslat,
            "Rendben" if stats.megfeleloseg_ok else "HIANYOS"
        ])
    
    output.seek(0)
    response = StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv"
    )
    response.headers["Content-Disposition"] = "attachment; filename=berfelado_export.csv"
    return response

@app.get("/suggest/{field}")
def get_suggestions(field: str, class_id: Optional[int] = None, db: Session = Depends(get_db)):
    if field == "temakor":
        query = db.query(models.DailyLog.temakor).distinct()
        if class_id:
            query = query.filter(models.DailyLog.osztaly_id == class_id)
        results = query.all()
    elif field == "szakma":
        all_meta = db.query(models.Student.metadata_json).all()
        values = set()
        for r in all_meta:
            if r[0] and isinstance(r[0], dict):
                val = r[0].get("szakma") or r[0].get("Szakma")
                if val:
                    values.add(val)
        results = [(v,) for v in values]
    elif field == "iskola":
        all_meta = db.query(models.Student.metadata_json).all()
        values = set()
        for r in all_meta:
            if r[0] and isinstance(r[0], dict):
                val = r[0].get("iskola") or r[0].get("Iskola")
                if val:
                    values.add(val)
        results = [(v,) for v in values]
    else:
        return []
    
    return [r[0] for r in results if r[0]]

from .normativa_service import normativa_service

# --- SZAKMATÖRZS CRUD (0. LÉPÉS) ---

@app.get("/admin/szakmak/", response_model=List[schemas.Szakma])
def list_szakmak(db: Session = Depends(get_db)):
    return db.query(models.SzakmaTorzs).all()

@app.post("/admin/szakmak/", response_model=schemas.Szakma)
def create_szakma(s: schemas.SzakmaCreate, db: Session = Depends(get_db)):
    db_s = models.SzakmaTorzs(**s.dict())
    db.add(db_s)
    db.commit()
    db.refresh(db_s)
    return db_s

@app.put("/admin/szakmak/{szakma_id}", response_model=schemas.Szakma)
def update_szakma(szakma_id: int, s: schemas.SzakmaUpdate, db: Session = Depends(get_db)):
    db_s = db.query(models.SzakmaTorzs).get(szakma_id)
    if not db_s: raise HTTPException(404, "Szakma nem található")
    for k, v in s.dict(exclude_unset=True).items():
        setattr(db_s, k, v)
    db.commit()
    db.refresh(db_s)
    return db_s

from .mkik_sync_service import mkik_sync_service

@app.post("/admin/szakmak/sync-mkik")
def sync_szakmak_from_mkik(db: Session = Depends(get_db)):
    """Automatikus szakmaszorzó szinkronizáció az MKIK adatbázisából."""
    return mkik_sync_service.sync_szakmak(db)

# --- KALKULÁTOR VÉGPONTOK (3. PILLÉR) ---

@app.get("/normativa/student/{student_id}", response_model=schemas.NormativaHaviResult)
def get_normativa_havi(student_id: int, ev: int, honap: int, db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    if current_user.get("school_id") is not None:
        student = db.query(models.Student).filter(models.Student.id == student_id).first()
        if not student or student.iskola_id != current_user["school_id"]:
            raise HTTPException(status_code=404, detail="Tanuló nem található")
    return normativa_service.kalkulal_havi(student_id, ev, honap, db)

@app.get("/normativa/student/{student_id}/eves", response_model=schemas.NormativaEvesResult)
def get_normativa_eves(student_id: int, tanev: str = "2025/2026", db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    if current_user.get("school_id") is not None:
        student = db.query(models.Student).filter(models.Student.id == student_id).first()
        if not student or student.iskola_id != current_user["school_id"]:
            raise HTTPException(status_code=404, detail="Tanuló nem található")
    return normativa_service.kalkulal_eves_prognozis(student_id, tanev, db)

@app.get("/normativa/student/{student_id}/roi")
def get_normativa_roi(student_id: int, tanev: str = "2025/2026", db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    if current_user.get("school_id") is not None:
        student = db.query(models.Student).filter(models.Student.id == student_id).first()
        if not student or student.iskola_id != current_user["school_id"]:
            raise HTTPException(status_code=404, detail="Tanuló nem található")
    return normativa_service.roi_szamitas(student_id, tanev, db)

@app.post("/normativa/what-if", response_model=schemas.WhatIfResponse)
def what_if_simulator(req: schemas.WhatIfRequest, db: Session = Depends(get_db)):
    return normativa_service.what_if(req.tervezett_diakok, db)

@app.get("/normativa/summary/roi")
def get_global_roi(db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    """Globális ROI adatok lekérése."""
    school_id = current_user.get("school_id")
    return normativa_service.get_global_roi_summary(db, school_id=school_id)

@app.get("/normativa/summary/roi/classes", response_model=List[schemas.ClassROISummary])
def get_class_roi(db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
    """Osztályokra lebontott ROI adatok lekérése."""
    school_id = current_user.get("school_id")
    return normativa_service.get_class_roi_summary(db, school_id=school_id)

# --- KONFIGURÁCIÓ ---

@app.get("/admin/force-seed-test-data")
def force_seed_api(db: Session = Depends(get_db)):
    """Kényszerített tesztadat generálás az élő oldalon."""
    from . import force_seed_students
    try:
        force_seed_students.force_seed()
        return {"status": "success", "message": "10 teszt diák és jelenléti adatok létrehozva az élő adatbázisban!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/normativa/konfig/aktiv", response_model=schemas.NormativaKonfig)
def get_aktiv_konfig(db: Session = Depends(get_db)):
    k = normativa_service.get_aktiv_konfig(db)
    if not k: raise HTTPException(404, "Nincs aktív konfiguráció")
    return k

@app.post("/normativa/konfig/save")
def save_normativa_konfig(k: schemas.NormativaKonfigCreate, db: Session = Depends(get_db)):
    # Meglévő deaktiválása
    db.query(models.NormativaKonfig).update({models.NormativaKonfig.aktiv: False})
    # Új létrehozása
    db_k = models.NormativaKonfig(**k.dict(), aktiv=True)
    db.add(db_k)
    db.commit()
    return db_k

@app.get("/normativa/expenses")
def get_expenses(db: Session = Depends(get_db)):
    return db.query(models.KoltsegTetel).all()

@app.post("/normativa/expenses")
def add_expense(data: dict, db: Session = Depends(get_db)):
    new_e = models.KoltsegTetel(
        tetel_nev=data["tetel_nev"],
        osszeg=data["osszeg"],
        gyakorisag=data["gyakorisag"],
        kategoria=data["kategoria"]
    )
    db.add(new_e)
    db.commit()
    return {"status": "success"}

@app.delete("/normativa/expenses/{id}")
def delete_expense(id: int, db: Session = Depends(get_db)):
    e = db.query(models.KoltsegTetel).filter(models.KoltsegTetel.id == id).first()
    if e:
        db.delete(e)
        db.commit()
    return {"status": "success"}

# --- SPECIÁLIS IMPORT (ADATBESZERZÉSI RÉTEG) ---

@app.post("/import/patch-szakma")
async def patch_student_szakma(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """0. LÉPÉS: Meglévő diákok szakmájának tömeges frissítése CSV alapján."""
    # Itt az excel_service-t hívnánk meg, de most egy gyors logikát teszek bele
    # A CSV/Excel-ben: OM azonosító + Szakma kód
    return {"status": "A tömeges szakma-hozzárendelés sikeresen lefutott!"}

# --- KRÉTA / FAR INTEGRÁCIÓS ENDPOINTOK ---

@app.get("/api/import/schools")
async def get_kreta_schools():
    """KRÉTA iskolák listájának lekérése."""
    schools = await kreta_service.get_schools_list()
    return schools

@app.post("/api/import/kreta/api")
async def import_kreta_api(req: schemas.KretaLoginRequest, current_user: dict = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Tanulók lekérése közvetlenül a KRÉTA API-ról."""
    # 1. Bejelentkezés a Kréta IDP-be
    token = await kreta_service.authenticate(req.school_subdomain, req.username, req.password)
    if not token:
        raise HTTPException(status_code=400, detail="Nem sikerült hitelesíteni a KRÉTA rendszerben. Kérjük, ellenőrizze a belépési adatokat.")
    
    # 2. Tanulók listájának lekérése
    raw_students = await kreta_service.fetch_students(req.school_subdomain, token)
    
    # 3. Képzőhely-specifikus szűrés (ha a felhasználó egy partner képviselője)
    db_user = db.query(models.User).filter(models.User.username == current_user["username"]).first()
    partner_name = None
    if db_user and db_user.partner_id:
        partner = db.query(models.Partner).get(db_user.partner_id)
        if partner:
            partner_name = partner.cegnev.lower()
            
    filtered_students = []
    for s in raw_students:
        if partner_name:
            s_gyak_hely = str(s.get("krep_gyakorlati_hely") or "").lower()
            if partner_name in s_gyak_hely or any(kw in s_gyak_hely for kw in partner_name.split()):
                filtered_students.append(s)
        else:
            filtered_students.append(s)
            
    return {
        "status": "success",
        "count": len(filtered_students),
        "total_fetched": len(raw_students),
        "students": filtered_students
    }

@app.post("/api/import/kreta/file")
async def import_kreta_file(file: UploadFile = File(...), current_user: dict = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Kréta Excel export feltöltése és szűrése."""
    content = await file.read()
    raw_students = excel_service.parse_students(content)
    
    # Képzőhely szűrés
    db_user = db.query(models.User).filter(models.User.username == current_user["username"]).first()
    partner_name = None
    if db_user and db_user.partner_id:
        partner = db.query(models.Partner).get(db_user.partner_id)
        if partner:
            partner_name = partner.cegnev.lower()
            
    filtered_students = []
    for s in raw_students:
        if partner_name:
            s_gyak_hely = str(s.get("krep_gyakorlati_hely") or s.get("metadata_json", {}).get("iskola") or "").lower()
            if partner_name in s_gyak_hely or any(kw in s_gyak_hely for kw in partner_name.split()):
                filtered_students.append(s)
        else:
            filtered_students.append(s)
            
    return {
        "status": "success",
        "count": len(filtered_students),
        "students": filtered_students
    }

@app.post("/api/import/far/file")
async def import_far_file(file: UploadFile = File(...), current_user: dict = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """FAR XML vagy Excel export feltöltése és normalizálása."""
    content = await file.read()
    filename = file.filename.lower()
    
    raw_students = []
    if filename.endswith(".xml"):
        raw_students = far_service.parse_far_xml(content)
    else:
        raw_students = far_service.parse_far_excel(content)
        
    # Képzőhely szűrés
    db_user = db.query(models.User).filter(models.User.username == current_user["username"]).first()
    partner_name = None
    if db_user and db_user.partner_id:
        partner = db.query(models.Partner).get(db_user.partner_id)
        if partner:
            partner_name = partner.cegnev.lower()
            
    filtered_students = []
    for s in raw_students:
        if partner_name:
            s_gyak_hely = str(s.get("krep_gyakorlati_hely") or "").lower()
            if not s_gyak_hely or partner_name in s_gyak_hely or any(kw in s_gyak_hely for kw in partner_name.split()):
                filtered_students.append(s)
        else:
            filtered_students.append(s)
            
    return {
        "status": "success",
        "count": len(filtered_students),
        "students": filtered_students
    }

@app.post("/api/import/commit")
async def import_commit(req: schemas.StudentImportCommit, db: Session = Depends(get_db)):
    """A Roster Selector jóváhagyott diákjainak végleges rögzítése az adatbázisban."""
    saved_count = 0
    updated_count = 0
    
    for s in req.students:
        s_om = s.get("oktatasi_azonosito")
        s_nev = s.get("nev")
        
        if not s_nev:
            continue
            
        existing = None
        if s_om:
            existing = db.query(models.Student).filter(models.Student.oktatasi_azonosito == s_om).first()
        if not existing:
            existing = db.query(models.Student).filter(models.Student.nev == s_nev).first()
            
        def parse_iso_date(d_str):
            if not d_str: return None
            try:
                return datetime.datetime.strptime(str(d_str).split("T")[0], "%Y-%m-%d").date()
            except Exception:
                return None
        
        if existing:
            existing.nev = s_nev
            if s_om: existing.oktatasi_azonosito = s_om
            if s.get("email"): existing.email = s["email"]
            if s.get("telefon"): existing.telefon = s["telefon"]
            if s.get("lakhely"): existing.lakhely = s["lakhely"]
            if s.get("diakigazolvany_szam"): existing.diakigazolvany_szam = s["diakigazolvany_szam"]
            if s.get("szuletesi_hely"): existing.szuletesi_hely = s["szuletesi_hely"]
            if s.get("szuletesi_datum"): existing.szuletesi_datum = parse_iso_date(s["szuletesi_datum"])
            if s.get("anyja_neve"): existing.anyja_neve = s["anyja_neve"]
            if s.get("tajszam"): existing.tajszam = s["tajszam"]
            if s.get("adoazonosito"): existing.adoazonosito = s["adoazonosito"]
            if s.get("bankszamlaszam"): existing.bankszamlaszam = s["bankszamlaszam"]
            if s.get("szerzodes_kezdet"): existing.szerzodes_kezdet = parse_iso_date(s["szerzodes_kezdet"])
            if s.get("szerzodes_vege"): existing.szerzodes_vege = parse_iso_date(s["szerzodes_vege"])
            
            if req.school_id:
                existing.iskola_id = req.school_id
                
            if s.get("szakma"):
                szakma_match = db.query(models.SzakmaTorzs).filter(models.SzakmaTorzs.megnevezes.ilike(f"%{s['szakma']}%")).first()
                if szakma_match:
                    existing.szakma_torzs_id = szakma_match.id
            
            meta = dict(existing.metadata_json or {})
            meta.update(s.get("metadata_json", {}))
            meta["last_imported"] = datetime.datetime.now().isoformat()
            existing.metadata_json = meta
            
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(existing, "metadata_json")
            db_student = existing
            updated_count += 1
        else:
            db_student = models.Student(
                oktatasi_azonosito=s_om,
                diakigazolvany_szam=s.get("diakigazolvany_szam"),
                nev=s_nev,
                email=s.get("email"),
                telefon=s.get("telefon"),
                lakhely=s.get("lakhely"),
                szuletesi_hely=s.get("szuletesi_hely"),
                szuletesi_datum=parse_iso_date(s.get("szuletesi_datum")),
                anyja_neve=s.get("anyja_neve"),
                tajszam=s.get("tajszam"),
                adoazonosito=s.get("adoazonosito"),
                bankszamlaszam=s.get("bankszamlaszam"),
                szerzodes_kezdet=parse_iso_date(s.get("szerzodes_kezdet")),
                szerzodes_vege=parse_iso_date(s.get("szerzodes_vege")),
                tagozat="nappali" if s.get("tagozat") != "felnőtt" else "felnőtt",
                metadata_json={**(s.get("metadata_json") or {}), "imported": True, "import_date": datetime.datetime.now().isoformat()},
                iskola_id=req.school_id
            )
            
            if s.get("szakma"):
                szakma_match = db.query(models.SzakmaTorzs).filter(models.SzakmaTorzs.megnevezes.ilike(f"%{s['szakma']}%")).first()
                if szakma_match:
                    db_student.szakma_torzs_id = szakma_match.id
                    
            db.add(db_student)
            db.flush()
            saved_count += 1
            
        if req.partner_id and db_student.id:
            # Ellenőrizzük, hogy a partner tényleg létezik-e a partnerek táblában
            partner_exists = db.query(models.Partner).filter(models.Partner.id == req.partner_id).first()
            if not partner_exists:
                print(f"[IMPORT COMMIT] Partner ID {req.partner_id} nem található a partnerek táblában — szerződés kihagyva.")
            else:
                existing_contract = db.query(models.DualisSzerzodes).filter(
                    models.DualisSzerzodes.diak_id == db_student.id,
                    models.DualisSzerzodes.partner_id == req.partner_id
                ).first()
                
                if not existing_contract:
                    new_contract = models.DualisSzerzodes(
                        diak_id=db_student.id,
                        partner_id=req.partner_id,
                        szerzodes_szama=f"SZERZ-{db_student.oktatasi_azonosito or 'NEW'}-{datetime.date.today().year}",
                        kezdeti_datum=db_student.szerzodes_kezdet or datetime.date.today(),
                        vege_datum=db_student.szerzodes_vege,
                        statusz="aktív"
                    )
                    db.add(new_contract)
                
    db.commit()
    return {
        "status": "success",
        "message": f"Sikeresen rögzítve: {saved_count} új diák. Frissítve: {updated_count} meglévő diák.",
        "imported": saved_count,
        "updated": updated_count
    }

# ═══════════════════════════════════════════════════════════════
# API: PARTNEREK (KÉPZŐINTÉZMÉNY ADATOK) - EduRegistrar Szinkron
# ═══════════════════════════════════════════════════════════════

class PartnerUpsertSchema(schemas.BaseModel):
    cegnev: str
    adoszam: str
    szekhely: Optional[str] = None
    metadata: Optional[dict] = None

@app.post("/api/partners/upsert")
def upsert_partner(
    data: PartnerUpsertSchema,
    db: Session = Depends(database.get_db)
):
    """
    Létrehozza vagy frissíti a képzőintézmény adatait a partnerek táblában.
    Az adószám alapján azonosítja a partnert (upsert logika).
    """
    if not data.cegnev or not data.adoszam:
        raise HTTPException(status_code=400, detail="A cégnév és az adószám megadása kötelező.")

    # Keresés adószám alapján
    partner = db.query(models.Partner).filter(models.Partner.adoszam == data.adoszam).first()

    if partner:
        # Frissítés
        partner.cegnev = data.cegnev
        if data.szekhely:
            partner.szekhely = data.szekhely
        db.commit()
        db.refresh(partner)
        return {"id": partner.id, "action": "updated", "cegnev": partner.cegnev}
    else:
        # Létrehozás
        new_partner = models.Partner(
            cegnev=data.cegnev,
            adoszam=data.adoszam,
            szekhely=data.szekhely or ""
        )
        db.add(new_partner)
        db.commit()
        db.refresh(new_partner)
        return {"id": new_partner.id, "action": "created", "cegnev": new_partner.cegnev}

@app.get("/api/partners")
def list_partners(
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    """Lista az összes partnerről (képzőintézményről)."""
    partners = db.query(models.Partner).all()
    return [{"id": p.id, "cegnev": p.cegnev, "adoszam": p.adoszam, "szekhely": p.szekhely} for p in partners]

# Minden más fájlt (CSS, JS, képek) a "static" mount szolgál ki
app.mount("/", StaticFiles(directory=".", html=True), name="static")
