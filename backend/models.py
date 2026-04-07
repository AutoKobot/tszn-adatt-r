from sqlalchemy import Column, Integer, String, Date, Text, ForeignKey, TIMESTAMP, Enum, Numeric, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()

class Student(Base):
    __tablename__ = "diakok"

    id = Column(Integer, primary_key=True, index=True)
    nev = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True)
    telefon = Column(String(20))
    lakhely = Column(Text)
    ertesitesi_cim = Column(Text)
    tagozat = Column(String(50)) # 'nappali', 'felnőtt'
    szerzodes_kezdet = Column(Date)
    szerzodes_vege = Column(Date)
    metadata_json = Column("metadata", JSON, default={})
    letrehozva = Column(TIMESTAMP, default=datetime.datetime.utcnow)

    # Kapcsolatok
    dualis_szerzodesek = relationship("DualisSzerzodes", back_populates="diak")
    naplok = relationship("KepzesiNaplo", back_populates="diak")
    biztonsagi_oktatasok = relationship("BiztonsagiNaplo", back_populates="diak")

class DualisSzerzodes(Base):
    __tablename__ = "dualis_szerzodesek"

    id = Column(Integer, primary_key=True, index=True)
    diak_id = Column(Integer, ForeignKey("diakok.id"))
    partner_id = Column(Integer, ForeignKey("partnerek.id"))
    szerzodes_szama = Column(String(100), unique=True)
    kezdeti_datum = Column(Date, nullable=False)
    vege_datum = Column(Date)
    statusz = Column(String(50), default="aktív")

    diak = relationship("Student", back_populates="dualis_szerzodesek")
    partner = relationship("Partner")

class Partner(Base):
    __tablename__ = "partnerek"

    id = Column(Integer, primary_key=True, index=True)
    cegnev = Column(String(255), nullable=False)
    adoszam = Column(String(13), unique=True)
    szekhely = Column(Text)

class KepzesiNaplo(Base):
    __tablename__ = "kepzesi_naplo"

    id = Column(Integer, primary_key=True, index=True)
    diak_id = Column(Integer, ForeignKey("diakok.id"))
    temakor = Column(String(255), nullable=False)
    modul_kod = Column(String(50))
    ora_szam = Column(Numeric(5, 2))
    eredmeny_ertek = Column(String(50))
    oktatas_datuma = Column(Date)

    diak = relationship("Student", back_populates="naplok")

class BiztonsagiNaplo(Base):
    __tablename__ = "biztonsagi_naplo"

    id = Column(Integer, primary_key=True, index=True)
    diak_id = Column(Integer, ForeignKey("diakok.id"))
    tipus = Column(String(50)) # 'munkavédelem', 'tűzvédelem'
    oktatas_datuma = Column(Date)
    ervenyesseg_vege = Column(Date)

    diak = relationship("Student", back_populates="biztonsagi_oktatasok")
