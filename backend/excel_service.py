import pandas as pd
import io
import re

# VERSION 1.1 - Emergency Fix for Profession Column
class ExcelService:
    def __init__(self):
        pass

    def _normalize_column_name(self, name):
        if pd.isna(name): return ""
        orig_name = str(name).strip()
        name = orig_name.lower()
        name = self._normalize_accent(name)
        
        # PRIORITÁS 1: Szakma
        if "szakma" in name or "kepzes" in name or "szakir" in name or "megnevez" in name:
            return "szakma"
        
        # PRIORITÁS 2: Név
        if any(x in name for x in ["nev", "tanu", "diak"]) and "iskol" not in name:
            return "nev"
            
        if "mail" in name: return "email"
        if "iskol" in name: return "iskola"
        if "evfolyam" in name or "evf" in name or "osztaly" in name: return "evfolyam"
            
        if "szerz" in name:
            if "kezd" in name and "vege" in name: return "szerzodes_idoszak"
            if "kezd" in name: return "szerzodes_kezdet"
            if "vege" in name: return "szerzodes_vege"
            return "szerzodes_idoszak"

        if "om" in name or "oktat" in name:
            return "om_azonosito"
            
        return re.sub(r'[^a-z0-9_]', '', name.replace(' ', '_'))

    def _normalize_accent(self, text):
        if not text: return ""
        return str(text).replace('á','a').replace('é','e').replace('í','i')\
                   .replace('ó','o').replace('ö','o').replace('ő','o')\
                   .replace('ú','u').replace('ü','u').replace('ű','u')

    def _read_df(self, file_bytes, sheet=0, header=None):
        try:
            return pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, header=header)
        except Exception:
            try:
                # Automata elválasztó felismerés
                return pd.read_csv(io.BytesIO(file_bytes), sep=None, engine='python', header=header, encoding='utf-8')
            except Exception:
                return pd.read_csv(io.BytesIO(file_bytes), sep=None, engine='python', header=header, encoding='latin-2')

    def _find_header_row(self, file_bytes, sheet=0):
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
        if value is None: return None
        s = str(value)
        return s.replace('\0', '').replace('\u0000', '').strip()

    def _get_safe_val(self, row, key, default=None):
        val = row.get(key)
        if hasattr(val, 'any'): 
            val = val.iloc[0] if len(val) > 0 else None
        if pd.isna(val): return default
        return self._clean_string(val)

    def parse_students(self, file_bytes):
        header_row = self._find_header_row(file_bytes)
        df = self._read_df(file_bytes, sheet=0, header=header_row)
        
        # Oszlopok normalizálása
        df.columns = [self._normalize_column_name(col) for col in df.columns]
        df = df.loc[:, ~df.columns.duplicated()]
        
        students = []
        occ_kws = ['technikus', 'szabo', 'burkolo', 'komuves', 'festo', 'hegeszto', 'asztalos', 'villany', 'szakma']
        
        for _, row in df.iterrows():
            nev = self._get_safe_val(row, 'nev')
            if not nev: continue
            
            # --- EMERGENCY SZAKMA FALLBACK ---
            # Ha a 'szakma' oszlop üres, nézzük végig az egész sort!
            szakma = self._get_safe_val(row, 'szakma')
            if not szakma:
                for col_name in df.columns:
                    val = str(row.get(col_name) or "").lower()
                    val_norm = self._normalize_accent(val)
                    if any(kw in val_norm for kw in occ_kws):
                        # Ha találtunk olyat, ami NÉV vagy ISKOLA vagy EMAIL, azt ne szakmának vegyük
                        if val_norm != self._normalize_accent(str(nev).lower()) and "@" not in val:
                            szakma = self._clean_string(row.get(col_name))
                            break

            # Date parsing
            kezdet = self._get_safe_val(row, 'szerzodes_kezdet')
            vege = self._get_safe_val(row, 'szerzodes_vege')
            if not kezdet or not vege:
                szerz_szoveg = str(self._get_safe_val(row, 'szerzodes_idoszak', ''))
                for sep in ["-", "–", "—"]: 
                    if sep in szerz_szoveg:
                        parts = szerz_szoveg.split(sep)
                        if len(parts) >= 2:
                            if not kezdet: kezdet = parts[0].strip()
                            if not vege: vege = parts[1].strip()
                            break
            
            students.append({
                "om_azonosito": self._get_safe_val(row, 'om_azonosito'),
                "diakigazolvany_szam": self._get_safe_val(row, 'diakigazolvany'),
                "nev": str(nev),
                "email": self._get_safe_val(row, 'email'),
                "iskola": self._get_safe_val(row, 'iskola'),
                "szakma": szakma,
                "evfolyam": self._get_safe_val(row, 'evfolyam'),
                "szerzodes_kezdet": str(kezdet).replace('.', '-') if kezdet else None,
                "szerzodes_vege": str(vege).replace('.', '-') if vege else None,
                "metadata_json": {}
            })
        return students

    def parse_instructors(self, file_bytes):
        # Hasonló logika mint a diákoknál...
        header_row = self._find_header_row(file_bytes)
        df = self._read_df(file_bytes, sheet=0, header=header_row)
        df.columns = [self._normalize_column_name(col) for col in df.columns]
        df = df.loc[:, ~df.columns.duplicated()]
        instructors = []
        for _, row in df.iterrows():
            nev = self._get_safe_val(row, 'nev')
            if not nev: continue
            instructors.append({
                "nev": str(nev),
                "email": self._get_safe_val(row, 'email'),
                "szakterulet": self._get_safe_val(row, 'szakma'),
                "metadata_json": {}
            })
        return instructors

excel_service = ExcelService()
