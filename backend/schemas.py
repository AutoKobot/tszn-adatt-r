from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import date, datetime

# --- DIÁK SÉMÁK ---
class StudentBase(BaseModel):
    oktatasi_azonosito: Optional[str] = None
    diakigazolvany_szam: Optional[str] = None
    nev: str
    email: Optional[EmailStr] = None
    telefon: Optional[str] = None
    lakhely: Optional[str] = None
    tagozat: Optional[str] = "nappali"
    szerzodes_kezdet: Optional[date] = None
    szerzodes_vege: Optional[date] = None
    metadata_json: Optional[dict] = {}

class StudentCreate(StudentBase):
    pass

class Student(StudentBase):
    id: int
    letrehozva: datetime

    model_config = {"from_attributes": True}

# --- OSZTÁLYOK / PARAMÉTEREK ---
class ClassRoomBase(BaseModel):
    megnevezes: str
    elvart_szakiranyu_oraszam: Optional[int] = 400
    max_hianyzas_szazalek: Optional[int] = 20

class ClassRoomUpdate(BaseModel):
    elvart_szakiranyu_oraszam: Optional[int] = None
    max_hianyzas_szazalek: Optional[int] = None

class ClassRoom(ClassRoomBase):
    id: int
    model_config = {"from_attributes": True}

# --- SZERZŐDÉSEK ---
class ContractCreate(BaseModel):
    diak_id: int
    partner_id: int
    szerzodes_szama: str
    kezdeti_datum: date
    vege_datum: Optional[date] = None

# --- JEGYEK ---
class GradeCreate(BaseModel):
    diak_id: int
    tantargy: str
    ertek: int
    datum: Optional[datetime] = None

# --- OKTATÓK ---
class InstructorBase(BaseModel):
    nev: str
    email: Optional[EmailStr] = None
    telefon: Optional[str] = None
    szakterulet: Optional[str] = None
    metadata_json: Optional[dict] = {}

class InstructorCreate(InstructorBase):
    pass

class Instructor(InstructorBase):
    id: int
    model_config = {"from_attributes": True}
