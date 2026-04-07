from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Lokális PostgreSQL kapcsolódási adatok (példa)
# FORMÁTUM: postgresql://username:password@localhost:5432/database_name
# Megpróbáljuk lekérni a DATABASE_URL környezeti változót (Renderen kötelező)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    print("!!! FIGYELMEZTETÉS !!!: A 'DATABASE_URL' környezeti változó hiányzik a Renderen. Visszaesés a localhost-ra (ez hibát okoz a felhőben).")
    SQLALCHEMY_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/edu_registrar"

# A Render néha "postgres://" formátumot ad, amit a SQLAlchemy nem szeret
if SQLALCHEMY_DATABASE_URL and SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
