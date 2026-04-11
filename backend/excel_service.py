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
        if ("szerz" in name and ("kezd" in name or "datum" in name)) and "vege" not in name:
            return "szerzodes_kezdet"
        if "szerz" in name and ("vege" in name or "lejar" in name):
            return "szerzodes_vege"
        if ("szerz" in name and "idoszak" in name) or "erven" in name:
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

    def _read_df(self, file_bytes, sheet=0, header=None):
        """Beolvassa a fájlt (Excel vagy CSV) DataFrame-be."""
        try:
            # Megpróbáljuk Excelként
            return pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, header=header)
        except Exception:
            # Ha nem Excel, megpróbáljuk CSV-ként
            # Automatikus szeparátor felismerés (sep=None, engine='python')
            try:
                # Először UTF-8-as kódolással
                return pd.read_csv(io.BytesIO(file_bytes), sep=None, engine='python', header=header, encoding='utf-8')
            except Exception:
                # Ha elbukik (pl. ékezetes karakterek hibás kódolása), megpróbáljuk közép-európai kódolással
                return pd.read_csv(io.BytesIO(file_bytes), sep=None, engine='python', header=header, encoding='latin-2')

    def _find_header_row(self, file_bytes, sheet=0):
        """Megkeresi, hogy melyik sorban vannak a fejlécek (0-indexelt).
        Végigpásztázza az első 10 sort, és azt választja, ahol a legtöbb
        ismert kulcsszót találja (pl. 'nev', 'mail', 'iskol', 'szakma')."""
        df_raw = self._read_df(file_bytes, sheet=sheet, header=None)
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

    def _clean_string(self, value):
        """Megtisztítja a sztringet a null bájtoktól és egyéb vezérlő karakterektől, amik tönkretehetik az adatbázist."""
        if value is None: return None
        s = str(value)
        # Null bájt (\0) eltávolítása - PostgreSQL nem szereti őket VARCHAR-ban
        s = s.replace('\0', '').replace('\u0000', '')
        # Felesleges whitespace-ek
        return s.strip()

    def _get_safe_val(self, row, key, default=None):
        """Biztonságosan lekér egy értéket egy sorból, akkor is ha duplikált oszlop miatt Series-t kapnánk"""
        val = row.get(key)
        if hasattr(val, 'any'): # Ha Series (lista)
            val = val.iloc[0] if len(val) > 0 else None
        
        if pd.isna(val):
            return default
        
        # Tisztítás
        return self._clean_string(val)

    def parse_instructors(self, file_bytes):
        """Oktatói Excel/CSV feldolgozása Intelligensen"""
        header_row = self._find_header_row(file_bytes)
        df = self._read_df(file_bytes, sheet=0, header=header_row)
        
        # Normalize headers and remove duplicates
        df.columns = [self._normalize_column_name(col) for col in df.columns]
        df = df.loc[:, ~df.columns.duplicated()]
        
        instructors = []
        for _, row in df.iterrows():
            nev = self._get_safe_val(row, 'nev')
            if not nev or str(nev).strip() == "":
                continue # Üres nevek átugrása
            
            instructor_data = {
                "nev": str(nev).strip(),
                "email": str(self._get_safe_val(row, 'email', '')).strip() or None,
                "szakterulet": str(self._get_safe_val(row, 'szakma', '')).strip() or None,
                "telefon": str(self._get_safe_val(row, 'telefon', '')).strip() or None,
                "metadata_json": {}
            }
            instructors.append(instructor_data)
        return instructors

    def parse_students(self, file_bytes):
        """Tanulói Excel/CSV feldolgozása"""
        header_row = self._find_header_row(file_bytes)
        df = self._read_df(file_bytes, sheet=0, header=header_row)
        
        # Normalize headers and remove duplicates
        df.columns = [self._normalize_column_name(col) for col in df.columns]
        df = df.loc[:, ~df.columns.duplicated()]
        
        students = []
        for _, row in df.iterrows():
            nev = self._get_safe_val(row, 'nev')
            if not nev or str(nev).strip() == "":
                continue
                
            # Szerződés kezelés: lehet egyben (pl. 2023.01.01 - 2024.12.31) vagy külön oszlopban
            kezdet = self._get_safe_val(row, 'szerzodes_kezdet')
            vege = self._get_safe_val(row, 'szerzodes_vege')
            
            if not kezdet or not vege:
                szerz_szoveg = str(self._get_safe_val(row, 'szerzodes_idoszak', ''))
                if "-" in szerz_szoveg:
                    parts = szerz_szoveg.split("-")
                    if not kezdet: kezdet = parts[0].replace('.', '-').strip()
                    if not vege: vege = parts[1].replace('.', '-').strip()
            
            # Formázás (ha szükséges, pl. pontok kötőjelre cserélése)
            if kezdet: kezdet = str(kezdet).replace('.', '-').strip()
            if vege: vege = str(vege).replace('.', '-').strip()
                
            student_data = {
                "om_azonosito": str(self._get_safe_val(row, 'om_azonosito', '')).strip() or None,
                "diakigazolvany_szam": str(self._get_safe_val(row, 'diakigazolvany', '')).strip() or None,
                "nev": str(nev).strip(),
                "email": str(self._get_safe_val(row, 'email', '')).strip() or None,
                "iskola": str(self._get_safe_val(row, 'iskola', '')).strip() or None,
                "szakma": str(self._get_safe_val(row, 'szakma', '')).strip() or None,
                "evfolyam": str(self._get_safe_val(row, 'evfolyam', '')).strip() or None,
                "szerzodes_kezdet": kezdet,
                "szerzodes_vege": vege,
                "metadata_json": {}
            }
            students.append(student_data)
        return students

excel_service = ExcelService()
