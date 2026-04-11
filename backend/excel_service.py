import pandas as pd
import io
import re

class ExcelService:
    def __init__(self):
        pass

    def _normalize_column_name(self, name):
        if pd.isna(name): return ""
        orig_name = str(name).strip()
        name = orig_name.lower()
        # Ékezetek manuális lecsupaszítása az összehasonlításhoz
        name = self._normalize_accent(name)
        
        # PRIORITÁS 1: Szakma (Ez a leggyakoribb hibaforrás)
        if "szakma" in name or "kepzes" in name or "szakir" in name or "megnevez" in name:
            if "nev" not in name or "szakma" in name: 
                return "szakma"
        
        # PRIORITÁS 2: Név
        if any(x in name for x in ["nev", "tanu", "diak"]) and "iskol" not in name:
            return "nev"
            
        if "mail" in name:
            return "email"
        
        if "iskol" in name:
            return "iskola"
            
        if "evfolyam" in name or "evf" in name or "osztaly" in name:
            return "evfolyam"
            
        if "szerz" in name:
            if "kezd" in name and "vege" in name: return "szerzodes_idoszak"
            if "kezd" in name: return "szerzodes_kezdet"
            if "vege" in name: return "szerzodes_vege"
            return "szerzodes_idoszak"

        if "om" in name or "oktat" in name:
            return "om_azonosito"
            
        res = re.sub(r'[^a-z0-9_]', '', name.replace(' ', '_'))
        return res

    def _normalize_accent(self, text):
        """Ékezetek eltávolítása összehasonlításhoz"""
        if not text: return ""
        return str(text).replace('á','a').replace('é','e').replace('í','i')\
                   .replace('ó','o').replace('ö','o').replace('ő','o')\
                   .replace('ú','u').replace('ü','u').replace('ű','u')

    def _read_df(self, file_bytes, sheet=0, header=None):
        try:
            return pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, header=header)
        except Exception:
            try:
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
        s = s.replace('\0', '').replace('\u0000', '')
        return s.strip()

    def _get_safe_val(self, row, key, default=None):
        val = row.get(key)
        if hasattr(val, 'any'): 
            val = val.iloc[0] if len(val) > 0 else None
        if pd.isna(val): return default
        return self._clean_string(val)

    def parse_instructors(self, file_bytes):
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
                "telefon": self._get_safe_val(row, 'telefon'),
                "metadata_json": {}
            })
        return instructors

    def parse_students(self, file_bytes):
        header_row = self._find_header_row(file_bytes)
        df = self._read_df(file_bytes, sheet=0, header=header_row)
        
        # 0. Eredeti oszlopnevek elmentése
        orig_cols = list(df.columns)
        
        # 1. Oszlopok normalizálása
        df.columns = [self._normalize_column_name(col) for col in df.columns]
        
        # 2. TARTALOM-ALAPÚ KERESÉS (Ez a legbiztosabb)
        occ_kws = ['technikus', 'szabo', 'burkolo', 'komuves', 'festo', 'hegeszto', 'asztalos', 'villany']
        if "szakma" not in df.columns:
            for col in df.columns.tolist():
                sample = df[col].dropna().head(10).astype(str).str.lower().tolist()
                sample_text = ' '.join([self._normalize_accent(s) for s in sample])
                if any(kw in sample_text for kw in occ_kws):
                    df.rename(columns={col: "szakma"}, inplace=True)
                    break
        
        df = df.loc[:, ~df.columns.duplicated()]
        
        students = []
        for _, row in df.iterrows():
            nev = self._get_safe_val(row, 'nev')
            if not nev: continue
            
            # Dátumok
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
            
            if kezdet: kezdet = str(kezdet).replace('.', '-')
            if vege: vege = str(vege).replace('.', '-')
                
            students.append({
                "om_azonosito": self._get_safe_val(row, 'om_azonosito'),
                "diakigazolvany_szam": self._get_safe_val(row, 'diakigazolvany'),
                "nev": str(nev),
                "email": self._get_safe_val(row, 'email'),
                "iskola": self._get_safe_val(row, 'iskola'),
                "szakma": self._get_safe_val(row, 'szakma'),
                "evfolyam": self._get_safe_val(row, 'evfolyam'),
                "szerzodes_kezdet": kezdet,
                "szerzodes_vege": vege,
                "metadata_json": {}
            })
        return students

excel_service = ExcelService()
