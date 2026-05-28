import xml.etree.ElementTree as ET
import pandas as pd
import io
import logging
from typing import List, Dict, Any

logger = logging.getLogger("far_service")

class FARService:
    def __init__(self):
        pass

    def parse_far_xml(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        """FAR (Felnőttképzési Adatszolgáltató Rendszer) XML feltöltés beolvasása és normalizálása."""
        students = []
        try:
            # XML fa betöltése
            xml_str = file_bytes.decode('utf-8', errors='ignore')
            # Tisztítás a hibás karakterektől
            xml_str = xml_str.replace('\x00', '')
            root = ET.fromstring(xml_str)
            
            # Különböző lehetséges gyermek elemek keresése (pl. <resztvevo>, <diak>, <kepzesben_resztvevo>)
            entries = root.findall('.//kepzesben_resztvevo') or root.findall('.//resztvevo') or root.findall('.//tanulo') or root.findall('.//Student')
            
            # Ha nem talált specifikus tag-et, de vannak gyermekek
            if not entries and len(root) > 0:
                entries = list(root)

            for entry in entries:
                # Személyes adatok kinyerése a tag-ekből
                csaladi_nev = entry.findtext('csaladi_nev') or entry.findtext('vezeteknev') or ""
                uto_nev = entry.findtext('uto_nev') or entry.findtext('keresztnev') or ""
                nev = f"{csaladi_nev} {uto_nev}".strip()
                if not nev:
                    nev = entry.findtext('nev') or entry.findtext('Name') or ""
                
                if not nev:
                    continue  # Nincs név, hagyjuk ki
                
                # Születési adatok
                szuletesi_hely = entry.findtext('szuletesi_hely') or entry.findtext('szul_hely') or ""
                szuletesi_datum = entry.findtext('szuletesi_datum') or entry.findtext('szul_ido') or ""
                
                # Anyja neve
                anyja_csaladi = entry.findtext('anyja_szuletesi_csaladi_neve') or entry.findtext('anyja_vezetekneve') or ""
                anyja_uto = entry.findtext('anyja_szuletesi_uto_neve') or entry.findtext('anyja_keresztneve') or ""
                anyja_neve = f"{anyja_csaladi} {anyja_uto}".strip()
                if not anyja_neve:
                    anyja_neve = entry.findtext('anyja_neve') or ""

                # Egyéb GDPR adatok
                tajszam = entry.findtext('taj_szam') or entry.findtext('taj') or ""
                adoazonosito = entry.findtext('adoazonosito_jel') or entry.findtext('adoazonosito') or ""
                bankszamlaszam = entry.findtext('bankszamlaszam') or entry.findtext('bankszamla') or ""
                
                # Kapcsolati adatok
                email = entry.findtext('email_cim') or entry.findtext('email') or ""
                telefon = entry.findtext('telefonszam') or entry.findtext('telefon') or ""
                
                # Lakcím
                lakhely_telepules = entry.findtext('lakcim_telepules') or ""
                lakhely_utca = entry.findtext('lakcim_utca') or ""
                lakhely_hazszam = entry.findtext('lakcim_hazszam') or ""
                lakhely = f"{lakhely_telepules} {lakhely_utca} {lakhely_hazszam}".strip()
                if not lakhely:
                    lakhely = entry.findtext('lakhely') or entry.findtext('address') or ""
                
                # Képzési adatok
                oktatasi_azonosito = entry.findtext('oktatasi_azonosito') or entry.findtext('om_azonosito') or ""
                szakma = entry.findtext('kepzes_megnevezese') or entry.findtext('szakma') or ""
                evfolyam = entry.findtext('csoport') or entry.findtext('evfolyam') or ""
                
                students.append({
                    "oktatasi_azonosito": oktatasi_azonosito,
                    "diakigazolvany_szam": entry.findtext('diakigazolvany') or "",
                    "nev": nev,
                    "email": email,
                    "telefon": telefon,
                    "lakhely": lakhely,
                    "szuletesi_hely": szuletesi_hely,
                    "szuletesi_datum": szuletesi_datum,
                    "anyja_neve": anyja_neve,
                    "tajszam": tajszam,
                    "adoazonosito": adoazonosito,
                    "bankszamlaszam": bankszamlaszam,
                    "szakma": szakma,
                    "evfolyam": evfolyam,
                    "szerzodes_kezdet": entry.findtext('szerzodes_kezdet') or None,
                    "szerzodes_vege": entry.findtext('szerzodes_vege') or None,
                    "krep_gyakorlati_hely": entry.findtext('gyakorlati_hely') or None,
                    "metadata_json": {
                        "source": "far_xml",
                        "import_date": __import__('datetime').datetime.now().isoformat()
                    }
                })
        except Exception as e:
            logger.error(f"Hiba a FAR XML feldolgozásakor: {e}")
        
        return students

    def parse_far_excel(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        """FAR Excel export beolvasása normalizált oszlopokkal."""
        try:
            df = pd.read_excel(io.BytesIO(file_bytes))
        except Exception:
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), sep=';', encoding='utf-8')
            except Exception:
                df = pd.read_csv(io.BytesIO(file_bytes), sep=';', encoding='latin-2')
        
        # Oszlopnevek normalizálása
        def normalize_far_col(col):
            c = str(col).lower().strip()
            c = c.replace('á','a').replace('é','e').replace('í','i')\
                 .replace('ó','o').replace('ö','o').replace('ő','o')\
                 .replace('ú','u').replace('ü','u').replace('ű','u')
            if 'resztvevo' in c or 'tanulo' in c or 'nev' in c: return 'nev'
            if 'om' in c or 'azonosito' in c: return 'om_azonosito'
            if 'szuletesi hely' in c or 'szul hely' in c: return 'szuletesi_hely'
            if 'szuletesi ido' in c or 'szuletesi datum' in c or 'szul datum' in c: return 'szuletesi_datum'
            if 'anyja' in c: return 'anyja_neve'
            if 'taj' in c: return 'taj_szam'
            if 'ado' in c: return 'adoazonosito'
            if 'szamla' in c or 'giro' in c: return 'bankszamlaszam'
            if 'mail' in c: return 'email'
            if 'telefon' in c or 'tel' in c: return 'telefon'
            if 'lakhely' in c or 'lakcim' in c: return 'lakhely'
            if 'szakma' in c or 'kepzes' in c: return 'szakma'
            return c

        df.columns = [normalize_far_col(c) for c in df.columns]
        students = []
        for _, row in df.iterrows():
            nev = row.get('nev')
            if pd.isna(nev) or not str(nev).strip():
                continue
            
            # Dátumok biztonságos konverziója
            def get_safe_date(val):
                if pd.isna(val): return None
                if isinstance(val, (pd.Timestamp, __import__('datetime').datetime)):
                    return val.strftime('%Y-%m-%d')
                return str(val).strip().replace('.', '-').replace('/', '-')

            students.append({
                "oktatasi_azonosito": str(row.get('om_azonosito', '')) if not pd.isna(row.get('om_azonosito')) else "",
                "diakigazolvany_szam": str(row.get('diakigazolvany', '')) if not pd.isna(row.get('diakigazolvany')) else "",
                "nev": str(nev).strip(),
                "email": str(row.get('email', '')) if not pd.isna(row.get('email')) else "",
                "telefon": str(row.get('telefon', '')) if not pd.isna(row.get('telefon')) else "",
                "lakhely": str(row.get('lakhely', '')) if not pd.isna(row.get('lakhely')) else "",
                "szuletesi_hely": str(row.get('szuletesi_hely', '')) if not pd.isna(row.get('szuletesi_hely')) else "",
                "szuletesi_datum": get_safe_date(row.get('szuletesi_datum')),
                "anyja_neve": str(row.get('anyja_neve', '')) if not pd.isna(row.get('anyja_neve')) else "",
                "tajszam": str(row.get('taj_szam', '')) if not pd.isna(row.get('taj_szam')) else "",
                "adoazonosito": str(row.get('adoazonosito', '')) if not pd.isna(row.get('adoazonosito')) else "",
                "bankszamlaszam": str(row.get('bankszamlaszam', '')) if not pd.isna(row.get('bankszamlaszam')) else "",
                "szakma": str(row.get('szakma', '')) if not pd.isna(row.get('szakma')) else "",
                "evfolyam": str(row.get('evfolyam', '')) if not pd.isna(row.get('evfolyam')) else "",
                "szerzodes_kezdet": get_safe_date(row.get('szerzodes_kezdet')),
                "szerzodes_vege": get_safe_date(row.get('szerzodes_vege')),
                "krep_gyakorlati_hely": str(row.get('gyakorlati_hely', '')) if not pd.isna(row.get('gyakorlati_hely')) else "",
                "metadata_json": {
                    "source": "far_excel",
                    "import_date": __import__('datetime').datetime.now().isoformat()
                }
            })
        return students

far_service = FARService()
