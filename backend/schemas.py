from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import date, datetime

# --- DIÁK SÉMÁK ---
class StudentBase(BaseModel):
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
