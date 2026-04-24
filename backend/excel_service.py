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
        if "szakma" in name or "kepzes" in name or "kepzesi" in name or "szakir" in name or "megnevez" in name or "agazat" in name:
            return "szakma"

        # PRIORITÁS 2: Oktató neve ("Oktatók" fejléc)
        if name.strip() in ["oktatok", "oktato"] or ("oktato" in name and "nev" in name):
            return "nev"

        # PRIORITÁS 3: Általános név mező
        if any(x in name for x in ["tanu", "diak"]) and "iskol" not in name:
            return "nev"
        if "nev" in name and "iskol" not in name and "anyja" not in name:
            return "nev"

        if "mail" in name: return "email"
        if "iskol" in name: return "iskola"
        if "evfolyam" in name or "osztaly" in name or "csoport" in name: return "evfolyam"
        
        if "szerz" in name:
            if "kezd" in name and "veg" in name: return "szerzodes_idoszak"
            if "kezd" in name: return "szerzodes_kezdet"
            if "veg" in name: return "szerzodes_vege"
            return "szerzodes_idoszak"

        # OM azonosító / Oktatási azonosító
        if ("azonosito" in name or "om" == name.strip() or "oktatasi_azonosito" in name) and "oktat" not in name:
            return "om_azonosito"
        if "oktatasi" in name and ("azonosito" in name or "kod" in name):
            return "om_azonosito"

        # Kréta-specifikus mezők
        if "szulet" in name:
            if "hely" in name: return "szuletesi_hely"
            return "szuletesi_datum"
        if "anyja" in name: return "anyja_neve"
        if "lakcim" in name or "lakhely" in name or "cim" in name or "lakos" in name: return "lakhely"
        if "taj" in name: return "taj_szam"
        if "ado" in name and "jel" in name: return "adoazonosito"
        if "bank" in name or "szamlaszam" in name: return "bankszamlaszam"
        if "telefon" in name or "tel" == name.strip() or "mobil" in name: return "telefon"
        if "diakigazolvany" in name: return "diakigazolvany"
            
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
        
        # Dátum típusú pandas mező kezelése
        if isinstance(val, (pd.Timestamp, __import__('datetime').datetime)):
            return val.strftime('%Y-%m-%d')
            
        return self._clean_string(val)

    def _parse_date(self, val):
        if not val: return None
        s = str(val).strip().replace('.', '-').replace('/', '-')
        # Kréta formátum: 2024-09-01- (néha van a végén kötőjel)
        s = s.rstrip('-')
        return s

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
                "telefon": self._get_safe_val(row, 'telefon'),
                "lakhely": self._get_safe_val(row, 'lakhely'),
                "iskola": self._get_safe_val(row, 'iskola'),
                "szakma": szakma,
                "evfolyam": self._get_safe_val(row, 'evfolyam'),
                "szerzodes_kezdet": self._parse_date(kezdet),
                "szerzodes_vege": self._parse_date(vege),
                "metadata_json": {
                    # Alap meta
                    "szakma": szakma,
                    "iskola": self._get_safe_val(row, 'iskola'),
                    "evfolyam": self._get_safe_val(row, 'evfolyam'),
                    # Kréta-specifikus extra mezők
                    "szuletesi_datum": self._get_safe_val(row, 'szuletesi_datum'),
                    "szuletesi_hely": self._get_safe_val(row, 'szuletesi_hely'),
                    "anyja_neve": self._get_safe_val(row, 'anyja_neve'),
                    "taj_szam": self._get_safe_val(row, 'taj_szam'),
                    "adoazonosito": self._get_safe_val(row, 'adoazonosito'),
                    "bankszamlaszam": self._get_safe_val(row, 'bankszamlaszam'),
                    "import_date": __import__('datetime').datetime.now().isoformat()
                }
            })
        return students

    def parse_instructors(self, file_bytes):
        """Oktatók beolvasása xlsx/csv fájlból.
        Elvártjellemző fejlécek: Oktatók (nev), Szakma megnevezése (szakterulet), e-mail cím (email)
        """
        header_row = self._find_header_row(file_bytes)
        df = self._read_df(file_bytes, sheet=0, header=header_row)
        
        # Oszlop nevek normalizálása
        orig_cols = list(df.columns)
        df.columns = [self._normalize_column_name(col) for col in orig_cols]
        df = df.loc[:, ~df.columns.duplicated()]
        
        print(f"[EXCEL][OKTATÓK] Fejléc sor: {header_row}")
        print(f"[EXCEL][OKTATÓK] Eredeti oszlopok: {orig_cols}")
        print(f"[EXCEL][OKTATÓK] Normalizált oszlopok: {list(df.columns)}")
        
        instructors = []
        for _, row in df.iterrows():
            nev = self._get_safe_val(row, 'nev')
            
            # Fallback: ha nincs 'nev' oszlop, próbáljuk az első szöveges oszlopot
            if not nev:
                for col in df.columns:
                    val = self._get_safe_val(row, col)
                    if val and len(val) > 3 and '@' not in val and not val.isdigit():
                        nev = val
                        break
            
            if not nev or str(nev).strip() == '' or str(nev).isdigit():
                continue
            
            # Sorszám szűrés: ha a "nev" egy szám, kihagyjuk
            try:
                float(nev)
                continue  # Ez csak egy sorszám
            except (ValueError, TypeError):
                pass
            
            email = self._get_safe_val(row, 'email')
            szakterulet = self._get_safe_val(row, 'szakma')
            
            instructors.append({
                "nev": str(nev).strip(),
                "email": email,
                "szakterulet": szakterulet,
                "metadata_json": {
                    "import_date": __import__('datetime').datetime.now().isoformat()
                }
            })
        
        print(f"[EXCEL][OKTATÓK] Beolvasott oktatók száma: {len(instructors)}")
        return instructors

excel_service = ExcelService()
