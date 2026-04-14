from sqlalchemy import Column, Integer, String, Date, Text, ForeignKey, TIMESTAMP, Enum, Numeric, JSON, Boolean
from sqlalchemy.orm import relationship
import datetime
from .database import Base

class User(Base):
    __tablename__ = "felhasznalok"
    id = Column(Integer, primary_key=True, index=True)
    username = Column("felhasznalonev", String(50), unique=True, nullable=False)
    hashed_password = Column("jelszo_hash", Text, nullable=False)
    role = Column("szerep", String(20), nullable=False) # 'admin', 'oktato', 'titkarsag'
    full_name = Column("teljes_nev", String(255))
    szakma_id = Column(Integer, ForeignKey("szakmak.id"))
    status = Column("statusz", Boolean, default=True)
    last_login = Column("utolso_bejelentkezes", TIMESTAMP)

class Student(Base):
    __tablename__ = "diakok"
    id = Column(Integer, primary_key=True, index=True)
    oktatasi_azonosito = Column(String(11), unique=True, index=True)
    diakigazolvany_szam = Column(String(50), unique=True, index=True)
    nev = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True)
    telefon = Column(String(20))
    lakhely = Column(Text)
    ertesitesi_cim = Column(Text)
    orvosi_alkalmassagi_lejarat = Column(Date)
    munkavedelmi_oktatas_datum = Column(Date)
    tagozat = Column(String(50))
    
    # Új személyes adatok
    szuletesi_hely = Column("szuletesi_hely", String(255))
    szuletesi_datum = Column("szuletesi_datum", Date)
    anyja_neve = Column("anyja_neve", String(255))
    tajszam = Column("tajszam", String(20))
    adoazonosito = Column("adoazonosito", String(20))
    bankszamlaszam = Column("bankszamlaszam", String(50))
    
    szerzodes_kezdet = Column(Date)
    szerzodes_vege = Column(Date)
    osztaly_id = Column(Integer, ForeignKey("osztalyok.id"))
    metadata_json = Column("megjegyzesek", JSON, default={})
    letrehozva = Column(TIMESTAMP, default=datetime.datetime.utcnow)

    # Kapcsolatok
    dualis_szerzodesek = relationship("DualisSzerzodes", back_populates="diak")

class Partner(Base):
    __tablename__ = "partnerek"
    id = Column(Integer, primary_key=True, index=True)
    cegnev = Column(String(255), nullable=False)
    adoszam = Column(String(13), unique=True)
    szekhely = Column(Text)

class DualisSzerzodes(Base):
    __tablename__ = "szakiranyu_szerzodesek"
    id = Column(Integer, primary_key=True, index=True)
    diak_id = Column(Integer, ForeignKey("diakok.id"))
    partner_id = Column(Integer, ForeignKey("partnerek.id"))
    szerzodes_szama = Column(String(100), unique=True)
    kezdeti_datum = Column("ervenyesseg_kezdet", Date, nullable=False)
    vege_datum = Column("ervenyesseg_vege", Date)
    statusz = Column(String(50), default="aktív")

    diak = relationship("Student", back_populates="dualis_szerzodesek")
    partner = relationship("Partner")

class ExternalGrade(Base):
    __tablename__ = "kulso_jegyek"
    id = Column(Integer, primary_key=True, index=True)
    diak_id = Column(Integer, ForeignKey("diakok.id"))
    tantargy = Column(String(100), nullable=False)
    ertek = Column(Integer, nullable=False)
    suly = Column(Integer, default=100) # Súly (százalékban, pl. 50, 100, 200)
    tipus = Column(String(20), default="elmélet", comment="Pl: gyakorlat, elmélet")
    datum = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    forras = Column(String(50), default="EduRegistrar")
    kulso_azonosito = Column(String(100))

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    felhasznalo_id = Column(Integer, ForeignKey("felhasznalok.id"))
    esemeny = Column(Text)
    idopont = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    audit_data = Column("metadata", JSON)

# Szükséges segédtáblák (üres de kellenek a Foreign Key-ekhez)
class Profession(Base):
    __tablename__ = "szakmak"
    id = Column(Integer, primary_key=True, index=True)
    megnevezes = Column(String(255))

class ClassRoom(Base):
    __tablename__ = "osztalyok"
    id = Column(Integer, primary_key=True, index=True)
    megnevezes = Column(String(50))
    statusz = Column(String(20), default="aktív") # 'aktív', 'archivált'
    # --- ÁKK és Duális Képzési Paraméterek ---
    elvart_szakiranyu_oraszam = Column(Integer, default=400, comment="Félévi vagy éves elvárt gyakorlati óraszám")
    max_hianyzas_szazalek = Column(Integer, default=20, comment="A megengedett hiányzás %-os határa")

class Instructor(Base):
    __tablename__ = "oktatok"
    id = Column(Integer, primary_key=True, index=True)
    nev = Column(String(255), nullable=False)
    email = Column(String(255), unique=True)
    telefon = Column(String(20))
    szakterulet = Column(String(255))
    metadata_json = Column("metadata", JSON, default={})

class SafetyTraining(Base):
    __tablename__ = "biztonsagi_oktatasok"
    id = Column(Integer, primary_key=True, index=True)
    diak_id = Column(Integer, ForeignKey("diakok.id"), nullable=True) # None ha teljes osztályra vonatkozik
    osztaly_id = Column(Integer, ForeignKey("osztalyok.id"), nullable=True)
    megnevezes = Column(String(255), default="Munkavédelmi oktatás")
    datum = Column(Date, default=datetime.date.today)
    lejarat = Column(Date)
    teljesitve = Column(Boolean, default=True)

class Equipment(Base):
    __tablename__ = "eszkozok"
    id = Column(Integer, primary_key=True, index=True)
    diak_id = Column(Integer, ForeignKey("diakok.id"))
    eszkoz_nev = Column(String(255), nullable=False)
    datum_kiadva = Column(Date, default=datetime.date.today)
    datum_visszaveve = Column(Date, nullable=True)
    statusz = Column(String(50), default="kiadva") # kiadva, visszavéve, elhasználódott

class Attendance(Base) :
    __tablename__ = "jelenlet"
    id = Column(Integer, primary_key=True, index=True)
    diak_id = Column(Integer, ForeignKey("diakok.id"), nullable=False)
    datum = Column(Date, nullable=False)
    oraszam = Column(Integer, default=0)
    tipus = Column(String(20), default="iskola") # 'iskola', 'cég'
    statusz = Column(String(20), default="jelen") # 'jelen', 'igazolt_hianyzas', 'igazolatlan_hianyzas'
    megjegyzes = Column(Text)
    letrehozva = Column(TIMESTAMP, default=datetime.datetime.utcnow)

class DailyLog(Base):
    __tablename__ = "haladasi_naplo"
    id = Column(Integer, primary_key=True, index=True)
    osztaly_id = Column(Integer, ForeignKey("osztalyok.id"))
    oktato_id = Column(Integer, ForeignKey("felhasznalok.id"))
    datum = Column(Date, default=datetime.date.today)
    oraszam = Column(Integer, default=1)
    temakor = Column(String(255))
    tartalom = Column(Text)
    letrehozva = Column(TIMESTAMP, default=datetime.datetime.utcnow)
