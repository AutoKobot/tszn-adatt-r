from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import asyncio
import shutil
import os
from . import models, schemas, database, sync_service

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
        if not db.query(models.User).filter(models.User.username == "oktato").first():
            oktato_user = models.User(username="oktato", hashed_password=auth.get_password_hash("oktato"), role="oktato", full_name="Teszt Oktató")
            db.add(oktato_user)
            
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

# CORS beállítások a React frontendhez
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Élesben szigorítani kell!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Adatbázis inicializálás
database.Base.metadata.create_all(bind=database.engine)

# Dependency: DB munkamenet lekérése
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"status": "EduRegistrar Backend Running"}

# --- DIÁKOK KEZELÉSE ---
@app.get("/students/", response_model=list[schemas.Student])
def read_students(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    students = db.query(models.Student).offset(skip).limit(limit).all()
    return students

@app.post("/students/", response_model=schemas.Student)
def create_student(student: schemas.StudentCreate, db: Session = Depends(get_db)):
    db_student = models.Student(**student.dict())
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student

# --- OSZTÁLYOK / KÉPZÉSI PARAMÉTEREK ---
@app.get("/classes/", response_model=list[schemas.ClassRoom])
def read_classes(db: Session = Depends(get_db)):
    classes = db.query(models.ClassRoom).all()
    # Dummy data provision if empty for demonstration
    if not classes:
        demo_class1 = models.ClassRoom(megnevezes="11.B (Gépészet)", elvart_szakiranyu_oraszam=400, max_hianyzas_szazalek=20)
        demo_class2 = models.ClassRoom(megnevezes="12.A (Informatika)", elvart_szakiranyu_oraszam=350, max_hianyzas_szazalek=20)
        db.add_all([demo_class1, demo_class2])
        db.commit()
        classes = db.query(models.ClassRoom).all()
    return classes

from fastapi import HTTPException

@app.put("/classes/{class_id}/parameters", response_model=schemas.ClassRoom)
def update_class_parameters(class_id: int, params: schemas.ClassRoomUpdate, db: Session = Depends(get_db)):
    db_class = db.query(models.ClassRoom).filter(models.ClassRoom.id == class_id).first()
    if not db_class:
        raise HTTPException(status_code=404, detail="Osztály nem található")
    
    if params.elvart_szakiranyu_oraszam is not None:
        db_class.elvart_szakiranyu_oraszam = params.elvart_szakiranyu_oraszam
    if params.max_hianyzas_szazalek is not None:
        db_class.max_hianyzas_szazalek = params.max_hianyzas_szazalek
        
    db.commit()
    db.refresh(db_class)
    return db_class

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

@app.post("/import/students")
async def import_students_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    parsed_students = excel_service.parse_students(content)
    
    saved_count = 0
    for s_data in parsed_students:
        s_om = s_data.get("om_azonosito")
        s_igaz = s_data.get("diakigazolvany_szam")
        s_nev = s_data["nev"]
        s_email = s_data["email"]
        s_szakma = s_data["szakma"]
        
        is_duplicate = False
        
        # 0. Ha Van OM azonosító, ELSŐDLEGESEN azzal szűrünk (a legpontosabb!)
        if s_om:
            if db.query(models.Student).filter(models.Student.oktatasi_azonosito == s_om).first():
                is_duplicate = True
        
        if not is_duplicate:
            # Lekérjük az összes azonos nevű diákot, ha az OM nem hozott eredményt (vagy nincs OM)
            existing_students = db.query(models.Student).filter(models.Student.nev == s_nev).all()
            for ex in existing_students:
                # 1. Ha az email is 100% egyezik (és nem üres) -> Biztos duplikáció
                if s_email and ex.email == s_email:
                    is_duplicate = True
                    break
                    
                # 2. Ha az email üres, de a név ÉS a betartott szakma is ugyanaz -> Valószínűleg duplikáció
                if not s_email and ex.metadata_json and ex.metadata_json.get("szakma") == s_szakma:
                     is_duplicate = True
                     break

        if not is_duplicate:
            new_student = models.Student(
                oktatasi_azonosito=s_om,
                diakigazolvany_szam=s_igaz,
                nev=s_nev,
                email=s_email,
                metadata_json={"iskola": s_data["iskola"], "szakma": s_szakma, "evfolyam": s_data["evfolyam"]}
            )
            db.add(new_student)
            saved_count += 1
            
    db.commit()
    return {"status": "success", "message": f"{saved_count} db új tanuló importálva a {len(parsed_students)} sorból."}

@app.post("/import/instructors")
async def import_instructors_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    parsed_instructors = excel_service.parse_instructors(content)
    
    saved_count = 0
    for i_data in parsed_instructors:
        # Hasonló okos szűrés az oktatókra is (Név + Email vagy Telefon alapú)
        i_nev, i_email, i_telefon = i_data["nev"], i_data["email"], i_data["telefon"]
        
        existing_insts = db.query(models.Instructor).filter(models.Instructor.nev == i_nev).all()
        is_duplicate = False
        
        for ex in existing_insts:
            if (i_email and ex.email == i_email) or (i_telefon and ex.telefon == i_telefon):
                is_duplicate = True
                break
            # Ha nincs email/telefon, de a név azonos, feltételezzük a duplikációt egyelőre
            if not i_email and not i_telefon:
                is_duplicate = True
                break
                
        if not is_duplicate:
            new_instructor = models.Instructor(
                nev=i_nev,
                email=i_email,
                szakterulet=i_data["szakterulet"],
                telefon=i_telefon
            )
            db.add(new_instructor)
            saved_count += 1
            
    db.commit()
    return {"status": "success", "message": f"{saved_count} db új oktató importálva a {len(parsed_instructors)} sorból."}

# --- TEMPLATE FELTÖLTÉS ---
@app.post("/templates/upload")
async def upload_template(type: str, file: UploadFile = File(...)):
    # type: dualis_nappali, dualis_felnott, oktatoi_megbizasi
    file_path = os.path.join("backend/templates", f"{type}.docx")
    os.makedirs("backend/templates", exist_ok=True)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"status": "success", "message": f"{type} sablon sikeresen feltöltve."}

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
