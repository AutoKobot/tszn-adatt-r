from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import asyncio
import shutil
import os
import datetime
from . import models, schemas, database, sync_service
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
        
        # Alapértelmezett tesztfiókok létrehozása (Titkárság és Oktató)
        db = database.SessionLocal()
        from . import auth
        if not db.query(models.User).filter(models.User.username == "admin").first():
            admin_user = models.User(username="admin", hashed_password=auth.get_password_hash("admin"), role="admin", full_name="Adminisztrátor")
            db.add(admin_user)
        # Eltávolítva a "Teszt Oktató" automatikus létrehozása
            
        # Adatbázis sémák frissítése (Migráció meglévő táblákon)
        from sqlalchemy import text
        try:
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS oktatasi_azonosito VARCHAR(11) UNIQUE;"))
            db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS diakigazolvany_szam VARCHAR(50) UNIQUE;"))
            db.execute(text("ALTER TABLE osztalyok ADD COLUMN IF NOT EXISTS elvart_szakiranyu_oraszam INTEGER DEFAULT 400;"))
            db.execute(text("ALTER TABLE osztalyok ADD COLUMN IF NOT EXISTS max_hianyzas_szazalek INTEGER DEFAULT 20;"))
            db.commit()
            print("Adatbázis oszlopok frissítve (Migráció sikeres).")
        except Exception as mig_e:
            print(f"Migrációs megjegyzés (nem kritikus): {mig_e}")
            db.rollback()

        db.commit()
        db.close()
        print("Teszfiókok ellenőrizve: admin/admin, oktato/oktato.")
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
                {"id": s.id, "nev": s.nev, "meta": s.metadata_json} 
                for s in db.query(models.Student).limit(3).all()
            ]
        }
        return counts
    except Exception as e:
        return {"error": str(e)}

@app.get("/students/", response_model=list[schemas.Student])
def read_students(skip: int = 0, limit: int = 500, db: Session = Depends(get_db)):
    try:
        print("[API] Diákok listázása (GET /students/)")
        students = db.query(models.Student).offset(skip).limit(limit).all()
        return students
    except Exception as e:
        print(f"[HIBA] Diákok lekérése közben: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/students/", response_model=schemas.Student)
def create_student(student: schemas.StudentCreate, db: Session = Depends(get_db)):
    db_student = models.Student(**student.dict())
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student

@app.put("/students/{student_id}", response_model=schemas.Student)
def update_student(student_id: int, student_update: schemas.StudentUpdate, db: Session = Depends(get_db)):
    db_student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Diák nem található")
    
    update_data = student_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_student, key, value)
    
    db.commit()
    db.refresh(db_student)
    return db_student

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
def read_classes(db: Session = Depends(get_db)):
    classes = db.query(models.ClassRoom).all()
    # Eltávolítva a dummy osztályok automatikus létrehozása
    return classes

from fastapi import HTTPException

@app.put("/classes/{class_id}/parameters", response_model=schemas.ClassRoom)
def update_class_parameters(class_id: int, params: schemas.ClassRoomUpdate, db: Session = Depends(get_db)):
    db_class = db.query(models.ClassRoom).filter(models.ClassRoom.id == class_id).first()
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
def archive_class(class_id: int, db: Session = Depends(get_db)):
    db_class = db.query(models.ClassRoom).filter(models.ClassRoom.id == class_id).first()
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
    
    saved_count = 0
    for i_data in parsed_instructors:
        # Hasonló okos szűrés az oktatókra is (Név + Email alapú)
        i_nev = i_data.get("nev")
        i_email = i_data.get("email")
        i_szakterulet = i_data.get("szakterulet")
        
        existing_insts = db.query(models.Instructor).filter(models.Instructor.nev == i_nev).all()
        is_duplicate = False
        
        for ex in existing_insts:
            if i_email and ex.email == i_email:
                is_duplicate = True
                break
            # Ha nincs email, de a név azonos, feltételezzük a duplikációt
            if not i_email:
                is_duplicate = True
                break
                
        if not is_duplicate:
            new_instructor = models.Instructor(
                nev=i_nev,
                email=i_email,
                szakterulet=i_szakterulet,
            )
            db.add(new_instructor)
            saved_count += 1
            
    db.commit()
    return {
        "status": "success", 
        "message": f"{saved_count} db új oktató importálva a {len(parsed_instructors)} sorból.",
        "beolvasott_sorok": f"{saved_count} / {len(parsed_instructors)}"
    }

@app.get("/instructors/", response_model=list[schemas.Instructor])
def read_instructors(db: Session = Depends(get_db)):
    return db.query(models.Instructor).all()

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
    
    # 2. JWT Token generálása a szerepkörrel
    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    return {"access_token": access_token, "token_type": "bearer"}

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
def read_safety_trainings(db: Session = Depends(get_db)):
    return db.query(models.SafetyTraining).all()

@app.post("/safety-trainings/", response_model=schemas.SafetyTraining)
def create_safety_training(training: schemas.SafetyTrainingCreate, db: Session = Depends(get_db)):
    db_training = models.SafetyTraining(**training.dict())
    db.add(db_training)
    db.commit()
    db.refresh(db_training)
    return db_training

@app.get("/equipment/", response_model=list[schemas.Equipment])
def read_equipment(db: Session = Depends(get_db)):
    return db.query(models.Equipment).all()

@app.post("/equipment/", response_model=schemas.Equipment)
def create_equipment(equip: schemas.EquipmentCreate, db: Session = Depends(get_db)):
    db_equip = models.Equipment(**equip.dict())
    db.add(db_equip)
    db.commit()
    db.refresh(db_equip)
    return db_equip

@app.delete("/equipment/{equip_id}")
def delete_equipment(equip_id: int, db: Session = Depends(get_db)):
    db_equip = db.query(models.Equipment).filter(models.Equipment.id == equip_id).first()
    if not db_equip:
        raise HTTPException(status_code=404, detail="Eszköz nem található")
    db.delete(db_equip)
    db.commit()
    return {"status": "success"}

# --- RENDKÍVÜLI ADATTÖRLÉS (Dummy adatok) ---
@app.post("/debug/cleanup-dummy-data")
def cleanup_dummy_data(db: Session = Depends(get_db)):
    # Töröljük a diákokat aki neve teszt jellegű
    dummy_names = ["Kovács Péter", "Szabó Éva", "Teszt Elek", "John Doe", "Jane Doe"]
    deleted_students = db.query(models.Student).filter(models.Student.nev.in_(dummy_names)).delete(synchronize_session=False)
    
    # Töröljük a demo osztályokat
    dummy_classes = ["11.B (Gépészet)", "12.A (Informatika)"]
    deleted_classes = db.query(models.ClassRoom).filter(models.ClassRoom.megnevezes.in_(dummy_classes)).delete(synchronize_session=False)
    
    db.commit()
    return {"status": "success", "deleted_students": deleted_students, "deleted_classes": deleted_classes}

# Minden más fájlt (CSS, JS, képek) a "static" mount szolgál ki
app.mount("/", StaticFiles(directory=".", html=True), name="static")
