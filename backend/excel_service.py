import pandas as pd
import io
import re

class ExcelService:
    def __init__(self):
        pass

    def _normalize_column_name(self, name):
        """Oszlopnevek egységesítése - rugalmas, széles körű felismerés"""
        if pd.isna(name): return ""
        name = str(name).lower().strip()
        # Ékezetek normalizálása
        name = name.replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ö','o').replace('ő','o').replace('ú','u').replace('ü','u').replace('ű','u')
        
        if any(x in name for x in ["nev", "oktat", "tanu", "diak", "nev"]):
            if "iskol" not in name:  # Ne keverjük az iskolával
                return "nev"
        if "mail" in name:
            return "email"
        if "szakma" in name or "kepzes" in name or "szakir" in name:
            return "szakma"
        if ("szerz" in name and "kezd" in name) or "idoszak" in name or "erven" in name:
            return "szerzodes_idoszak"
        if "iskol" in name:
            return "iskola"
        if "evfolyam" in name or "evf" in name or "osztaly" in name or "csoport" in name:
            return "evfolyam"
        if "telefon" in name or "tel" in name or "mobil" in name:
            return "telefon"
        if "om" == name.strip() or "om_" in name or ("oktat" in name and "azonos" in name) or "om azon" in name:
            return "om_azonosito"
        if "igazolv" in name or "diakig" in name:
            return "diakigazolvany"
        if "szam" in name and len(name) < 8:  # pl. "sorszám"
            return "sorszam"
        
        return re.sub(r'[^a-z0-9_]', '', name.replace(' ', '_'))


    def _normalize_accent(self, text):
        """Ékezetek eltávolítása összehasonlításhoz"""
        return text.replace('á','a').replace('é','e').replace('í','i')\
                   .replace('ó','o').replace('ö','o').replace('ő','o')\
                   .replace('ú','u').replace('ü','u').replace('ű','u')

    def _find_header_row(self, file_bytes, sheet=0):
        """Megkeresi, hogy melyik sorban vannak a fejlécek (0-indexelt).
        Végigpásztázza az első 10 sort, és azt választja, ahol a legtöbb
        ismert kulcsszót találja (pl. 'nev', 'mail', 'iskol', 'szakma')."""
        df_raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, header=None)
        keywords = ['nev', 'mail', 'iskol', 'szakma', 'oktat', 'evfolyam', 'tanu', 'szerz']
        best_row = 0
        best_score = 0
        for i in range(min(10, len(df_raw))):
            row_str = ' '.join([self._normalize_accent(str(v).lower()) for v in df_raw.iloc[i].values if pd.notna(v)])
            score = sum(1 for kw in keywords if kw in row_str)
            if score > best_score:
                best_score = score
                best_row = i
        return best_row

    def parse_instructors(self, file_bytes):
        """Oktatói Excel feldolgozása Intelligensen"""
        header_row = self._find_header_row(file_bytes)
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0, header=header_row)
        
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
        header_row = self._find_header_row(file_bytes)
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0, header=header_row)
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
                "om_azonosito": str(row.get('om_azonosito', '')).strip() if pd.notna(row.get('om_azonosito')) else None,
                "diakigazolvany_szam": str(row.get('diakigazolvany', '')).strip() if pd.notna(row.get('diakigazolvany')) else None,
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
