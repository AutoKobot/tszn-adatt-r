import pandas as pd
import io
import re

class ExcelService:
    def __init__(self):
        pass

    def _normalize_column_name(self, name):
        """Oszlopnevek egységesítése a sorrendiség és elnevezések rugalmassága érdekében"""
        if pd.isna(name): return ""
        name = str(name).lower().strip()
        
        # Kis okos térkép a gyakori elnevezésekhez
        if "név" in name or "nev" in name or "oktatók" in name:
            return "nev"
        if "mail" in name:
            return "email"
        if "szakma" in name:
            return "szakma"
        if "szerz" in name and "kezdet" in name:
            return "szerzodes_idoszak"
        if "iskola" in name:
            return "iskola"
        if "évfolyam" in name or "evfolyam" in name:
            return "evfolyam"
        if "telefon" in name:
            return "telefon"
        
        return re.sub(r'[^a-z0-9_]', '', name.replace(' ', '_'))

    def parse_instructors(self, file_bytes):
        """Oktatói Excel feldolgozása Intelligensen"""
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0)
        
        # Normalize headers
        df.columns = [self._normalize_column_name(col) for col in df.columns]
        
        instructors = []
        for _, row in df.iterrows():
            if pd.isna(row.get('nev')):
                continue # Üres nevek átugrása
            
            # Adatok kinyerése (ha nincs az excelben, None marad, rugalmas)
            instructor_data = {
                "nev": str(row.get('nev', '')).strip(),
                "email": str(row.get('email', '')).strip() if pd.notna(row.get('email')) else None,
                "szakterulet": str(row.get('szakma', '')).strip() if pd.notna(row.get('szakma')) else None,
                "telefon": str(row.get('telefon', '')).strip() if pd.notna(row.get('telefon')) else None,
                "metadata_json": {}
            }
            instructors.append(instructor_data)
            
        return instructors

    def parse_students(self, file_bytes):
        """Tanulói Excel feldolgozása, támogatva a felnőtt/nappali keveredést nyitott módon"""
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0)
        df.columns = [self._normalize_column_name(col) for col in df.columns]
        
        students = []
        for _, row in df.iterrows():
            if pd.isna(row.get('nev')):
                continue
                
            # Dátumok feldarabolása ha egyben vannak (pl. "2024.09.01.-2027.06.30.")
            szerz_szoveg = str(row.get('szerzodes_idoszak', ''))
            kezdet, vege = None, None
            if "-" in szerz_szoveg:
                parts = szerz_szoveg.split("-")
                kezdet = parts[0].replace('.', '-').strip()
                vege = parts[1].replace('.', '-').strip()
                
            student_data = {
                "nev": str(row.get('nev', '')).strip(),
                "email": str(row.get('email', '')).strip() if pd.notna(row.get('email')) else None,
                "iskola": str(row.get('iskola', '')).strip() if pd.notna(row.get('iskola')) else None,
                "szakma": str(row.get('szakma', '')).strip() if pd.notna(row.get('szakma')) else None,
                "evfolyam": str(row.get('evfolyam', '')).strip() if pd.notna(row.get('evfolyam')) else None,
                "szerzodes_kezdet": kezdet,
                "szerzodes_vege": vege,
                "metadata_json": {}
            }
            students.append(student_data)
            
        return students

excel_service = ExcelService()
