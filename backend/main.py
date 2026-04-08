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

@asynccontextmanager
async def lifespan(app: FastAPI):
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
