from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import date, datetime

# --- DIÁK SÉMÁK ---
class StudentBase(BaseModel):
    oktatasi_azonosito: Optional[str] = None
    diakigazolvany_szam: Optional[str] = None
    nev: str
    email: Optional[str] = None
    telefon: Optional[str] = None
    lakhely: Optional[str] = None
    tagozat: Optional[str] = "nappali"
    szerzodes_kezdet: Optional[date] = None
    szerzodes_vege: Optional[date] = None
    metadata_json: Optional[dict] = {}

class StudentCreate(StudentBase):
    pass

class StudentUpdate(BaseModel):
    oktatasi_azonosito: Optional[str] = None
    diakigazolvany_szam: Optional[str] = None
    nev: Optional[str] = None
    email: Optional[str] = None
    telefon: Optional[str] = None
    lakhely: Optional[str] = None
    tagozat: Optional[str] = None
    szerzodes_kezdet: Optional[date] = None
    szerzodes_vege: Optional[date] = None
    metadata_json: Optional[dict] = None

class Student(StudentBase):
    id: int
    letrehozva: datetime

    model_config = {"from_attributes": True}

# --- IMPORT KONFLIKTUS KÉP ---
class ImportConflict(BaseModel):
    id: Optional[int] = None
    incoming_data: dict
    existing_data: Optional[dict] = None
    reason: str # 'om_match', 'email_match', 'name_match'

# --- OSZTÁLYOK / PARAMÉTEREK ---
class ClassRoomBase(BaseModel):
    megnevezes: str
    statusz: Optional[str] = "aktív"
    elvart_szakiranyu_oraszam: Optional[int] = 400
    max_hianyzas_szazalek: Optional[int] = 20

class ClassRoomUpdate(BaseModel):
    megnevezes: Optional[str] = None
    statusz: Optional[str] = None
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
    email: Optional[str] = None
    telefon: Optional[str] = None
    szakterulet: Optional[str] = None
    metadata_json: Optional[dict] = {}

class InstructorCreate(InstructorBase):
    pass

class Instructor(InstructorBase):
    id: int
    model_config = {"from_attributes": True}

# --- BIZTONSÁG ÉS ESZKÖZÖK ---
class SafetyTrainingBase(BaseModel):
    diak_id: Optional[int] = None
    osztaly_id: Optional[int] = None
    megnevezes: str = "Munkavédelmi oktatás"
    datum: Optional[date] = None
    lejarat: date
    teljesitve: bool = True

class SafetyTrainingCreate(SafetyTrainingBase):
    pass

class SafetyTraining(SafetyTrainingBase):
    id: int
    model_config = {"from_attributes": True}

class EquipmentBase(BaseModel):
    diak_id: int
    eszkoz_nev: str
    statusz: Optional[str] = "kiadva"

class EquipmentCreate(EquipmentBase):
    pass

class Equipment(EquipmentBase):
    id: int
    datum_kiadva: date
    datum_visszaveve: Optional[date] = None
    model_config = {"from_attributes": True}

# --- PARTNEREK SÉMÁK ---
class PartnerBase(BaseModel):
    cegnev: str
    adoszam: Optional[str] = None
    szekhely: Optional[str] = None

class PartnerCreate(PartnerBase):
    pass

class Partner(PartnerBase):
    id: int
    model_config = {"from_attributes": True}

# --- FELHASZNÁLÓ SÉMÁK ---
class UserBase(BaseModel):
    username: str
    full_name: Optional[str] = None
    role: str
    status: Optional[bool] = True

class UserCreate(UserBase):
    password: str
    instructor_id: Optional[int] = None

class User(UserBase):
    id: int
    last_login: Optional[datetime] = None
    model_config = {"from_attributes": True}
