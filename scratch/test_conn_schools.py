import os
from sqlalchemy import create_engine, Column, Integer, String, TIMESTAMP, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv(".env")
db_url = os.getenv("DATABASE_URL")
if not db_url:
    load_dotenv("../InteractiveLearning/.env")
    db_url = os.getenv("DATABASE_URL")

if not db_url:
    db_url = "postgresql://postgres.epbyruyoblszmbcgpfvh:TiszaloK123@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"

Base = declarative_base()

class School(Base):
    __tablename__ = "schools"
    id = Column(Integer, primary_key=True, index=True)
    nev = Column("name", String(255), nullable=False)

engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    schools = db.query(School).all()
    print("SUCCESSFULLY QUERIED schools table via SQLAlchemy mapped model:")
    for s in schools:
        print(f"  ID: {s.id}, Nev (from 'name' column): '{s.nev}'")
except Exception as e:
    print(f"FAILED: {e}")
finally:
    db.close()
