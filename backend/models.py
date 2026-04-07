from sqlalchemy import Column, Integer, String, Date, Text, ForeignKey, TIMESTAMP, Enum, Numeric, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()

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
    oktatasi_azonosito = Column(String(11), unique=True)
    nev = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True)
    telefon = Column(String(20))
    lakhely = Column(Text)
    ertesitesi_cim = Column(Text)
    tagozat = Column(String(50))
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
    datum = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    forras = Column(String(50), default="Kréta")
    kulso_azonosito = Column(String(100))

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    felhasznalo_id = Column(Integer, ForeignKey("felhasznalok.id"))
    esemeny = Column(Text)
    idopont = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    metadata = Column(JSON)

# Szükséges segédtáblák (üres de kellenek a Foreign Key-ekhez)
class Profession(Base):
    __tablename__ = "szakmak"
    id = Column(Integer, primary_key=True, index=True)
    megnevezes = Column(String(255))

class ClassRoom(Base):
    __tablename__ = "osztalyok"
    id = Column(Integer, primary_key=True, index=True)
    megnevezes = Column(String(50))
