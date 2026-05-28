import httpx
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("kreta_service")

class KretaService:
    def __init__(self):
        pass

    async def get_schools_list(self) -> List[Dict[str, str]]:
        """Lekéri a hivatalos KRÉTA iskolalistát kereséshez."""
        url = "https://waiter.e-kreta.hu/api/v1/Institutes"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    # A Kréta válasz formátuma: [{"InstituteCode": "klik035...", "Name": "...", "Url": "..."}]
                    return [
                        {
                            "code": item.get("InstituteCode"),
                            "name": item.get("Name"),
                            "subdomain": item.get("InstituteCode")
                        }
                        for item in data
                    ]
        except Exception as e:
            logger.error(f"Hiba a Kréta iskolalista lekérésekor: {e}")
        
        # Fallback alapértelmezett teszt iskolákkal
        return [
            {"code": "klik035123001", "name": "Budapesti Gépészeti Szakképzési Centrum", "subdomain": "klik035123001"},
            {"code": "klik035123002", "name": "Váci Szakképzési Centrum Boronkay György", "subdomain": "klik035123002"},
            {"code": "klik035123003", "name": "Győri Szakképzési Centrum Jedlik Ányos", "subdomain": "klik035123003"},
        ]

    async def authenticate(self, subdomain: str, username: str, password: str) -> Optional[str]:
        """OAuth2 bejelentkezés és Access Token lekérése."""
        # --- MOCK FALLBACK TESZTELÉSHEZ ---
        if subdomain == "mock_school" or username == "mock_admin":
            return "mock_access_token_12345"

        url = f"https://{subdomain}.e-kreta.hu/idp/profile/oauth/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Kreta.Ellenorzo/3.0.0 (Android; SDK 33)"
        }
        data = {
            "username": username,
            "password": password,
            "grant_type": "password",
            "client_id": "kreta-naplo-mobile-android"
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, data=data, headers=headers)
                if response.status_code == 200:
                    res_json = response.json()
                    return res_json.get("access_token")
                else:
                    logger.error(f"Kréta hitelesítési hiba: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Kréta hálózati hiba: {e}")
        return None

    async def fetch_students(self, subdomain: str, access_token: str) -> List[Dict[str, Any]]:
        """Lekéri a diákok adatait a KRÉTA API-n keresztül és normalizálja őket."""
        # --- MOCK FALLBACK TESZTELÉSHEZ ---
        if access_token == "mock_access_token_12345":
            return self._generate_mock_students()

        url = f"https://{subdomain}.e-kreta.hu/api/v1/Student"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "Kreta.Ellenorzo/3.0.0 (Android; SDK 33)"
        }
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    students_data = response.json()
                    normalized_students = []
                    # Ha a válasz egy lista
                    if isinstance(students_data, list):
                        for item in students_data:
                            # A diák mélyebb részleteinek lekérése a személyes adatokért (TAJ, adóazonosító stb.)
                            student_id = item.get("Uid") or item.get("id") or item.get("StudentId")
                            detailed_info = {}
                            if student_id:
                                try:
                                    det_resp = await client.get(f"{url}/{student_id}", headers=headers)
                                    if det_resp.status_code == 200:
                                        detailed_info = det_resp.json()
                                except Exception:
                                    pass
                            normalized_students.append(self._normalize_student(item, detailed_info))
                    return normalized_students
        except Exception as e:
            logger.error(f"Kréta diákok lekérési hiba: {e}")
        
        return []

    def _normalize_student(self, raw: Dict[str, Any], detailed: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizálja a KRÉTA diák rekordját az EduRegistrar belső sémájára."""
        # Egyesíti a kapott adatokat
        data = {**raw, **detailed}
        
        # Próbáljuk kinyerni a születési helyet/időt, anyja nevét, lakcímet, TAJ-t és adóazonosítót
        szuletesi_hely = data.get("BirthPlace") or data.get("SzuletesiHely")
        szuletesi_datum = data.get("BirthDate") or data.get("SzuletesiDatum")
        anyja_neve = data.get("MotherName") or data.get("AnyjaNeve")
        tajszam = data.get("TajNumber") or data.get("TajSzam") or data.get("SocialSecurityNumber")
        adoazonosito = data.get("TaxSign") or data.get("Adoazonosito") or data.get("TaxNumber")
        bankszamlaszam = data.get("BankAccountNumber") or data.get("Bankszamlaszam")
        lakhely = data.get("Address") or data.get("Lakhely") or data.get("Cim")
        
        # Szakma és osztály adatok
        szakma_nev = data.get("ProfessionName") or data.get("SzakmaMegnevezese") or data.get("Képzés")
        evfolyam = data.get("Grade") or data.get("Evfolyam") or data.get("ClassRoomName")
        
        # Szerződés adatok
        kezdet = data.get("ContractStartDate") or data.get("SzerzodesKezdete")
        vege = data.get("ContractEndDate") or data.get("SzerzodesVege")

        return {
            "oktatasi_azonosito": str(data.get("OktatasiAzonosito") or data.get("OmIdentifier") or ""),
            "diakigazolvany_szam": data.get("StudentCardNumber") or data.get("Diakigazolvany"),
            "nev": data.get("Name") or data.get("Nev") or f"{data.get('LastName', '')} {data.get('FirstName', '')}".strip(),
            "email": data.get("Email") or data.get("EmailAddress"),
            "telefon": data.get("PhoneNumber") or data.get("Telefon"),
            "lakhely": lakhely,
            "szuletesi_hely": szuletesi_hely,
            "szuletesi_datum": szuletesi_datum,
            "anyja_neve": anyja_neve,
            "tajszam": tajszam,
            "adoazonosito": adoazonosito,
            "bankszamlaszam": bankszamlaszam,
            "szakma": szakma_nev,
            "evfolyam": evfolyam,
            "szerzodes_kezdet": kezdet,
            "szerzodes_vege": vege,
            "krep_gyakorlati_hely": data.get("GyakorlatiKepzohely") or data.get("PartnerName"), # Szűréshez
            "metadata_json": {
                "source": "kreta_api",
                "original_raw_id": data.get("Uid")
            }
        }

    def _generate_mock_students(self) -> List[Dict[str, Any]]:
        """Generál 5 darab élethű magyar teszt diákot szűrés és szinkronizáció teszteléséhez."""
        return [
            {
                "oktatasi_azonosito": "71122334455",
                "diakigazolvany_szam": "123456AB",
                "nev": "Kovács Ádám",
                "email": "kovacs.adam@diak.hu",
                "telefon": "+36301112233",
                "lakhely": "1117 Budapest, Irinyi József u. 42.",
                "szuletesi_hely": "Budapest",
                "szuletesi_datum": "2007-04-12",
                "anyja_neve": "Szabó Erzsébet",
                "tajszam": "123-456-789",
                "adoazonosito": "8412345678",
                "bankszamlaszam": "11773084-21012345",
                "szakma": "Szoftverfejlesztő és -tesztelő",
                "evfolyam": "11.A",
                "szerzodes_kezdet": "2024-09-01",
                "szerzodes_vege": "2026-06-30",
                "krep_gyakorlati_hely": "Hegesztő Kft", # Megegyező képzőhely a tesztekhez
                "metadata_json": {"source": "mock_kreta"}
            },
            {
                "oktatasi_azonosito": "72233445566",
                "diakigazolvany_szam": "234567BC",
                "nev": "Nagy Dóra",
                "email": "nagy.dora@diak.hu",
                "telefon": "+36302223344",
                "lakhely": "2000 Szentendre, Kossuth Lajos u. 5.",
                "szuletesi_hely": "Debrecen",
                "szuletesi_datum": "2006-08-25",
                "anyja_neve": "Kovács Ilona",
                "tajszam": "234-567-890",
                "adoazonosito": "8423456789",
                "bankszamlaszam": "11773084-21023456",
                "szakma": "Szoftverfejlesztő és -tesztelő",
                "evfolyam": "12.B",
                "szerzodes_kezdet": "2024-09-01",
                "szerzodes_vege": "2025-06-30",
                "krep_gyakorlati_hely": "Hegesztő Kft", # Megegyező képzőhely a tesztekhez
                "metadata_json": {"source": "mock_kreta"}
            },
            {
                "oktatasi_azonosito": "73344556677",
                "diakigazolvany_szam": "345678CD",
                "nev": "Tóth Bence",
                "email": "toth.bence@diak.hu",
                "telefon": "+36303334455",
                "lakhely": "1037 Budapest, Bécsi út 100.",
                "szuletesi_hely": "Kecskemét",
                "szuletesi_datum": "2008-01-15",
                "anyja_neve": "Tóth Mária",
                "tajszam": "345-678-901",
                "adoazonosito": "8434567890",
                "bankszamlaszam": "11773084-21034567",
                "szakma": "Hegesztő",
                "evfolyam": "10.C",
                "szerzodes_kezdet": "2025-09-01",
                "szerzodes_vege": "2027-06-30",
                "krep_gyakorlati_hely": "Forgácsoló Bt", # Eltérő képzőhely, szűrés teszteléséhez
                "metadata_json": {"source": "mock_kreta"}
            },
            {
                "oktatasi_azonosito": "74455667788",
                "diakigazolvany_szam": "456789DE",
                "nev": "Kiss Eszter",
                "email": "kiss.eszter@diak.hu",
                "telefon": "+36304445566",
                "lakhely": "9024 Győr, Baross Gábor u. 12.",
                "szuletesi_hely": "Győr",
                "szuletesi_datum": "2007-11-02",
                "anyja_neve": "Varga Zsófia",
                "tajszam": "456-789-012",
                "adoazonosito": "8445678901",
                "bankszamlaszam": "11773084-21045678",
                "szakma": "Villanyszerelő",
                "evfolyam": "11.B",
                "szerzodes_kezdet": "2024-09-01",
                "szerzodes_vege": "2026-06-30",
                "krep_gyakorlati_hely": "Hegesztő Kft", # Megegyező képzőhely
                "metadata_json": {"source": "mock_kreta"}
            },
            {
                "oktatasi_azonosito": "75566778899",
                "diakigazolvany_szam": "567890EF",
                "nev": "Horváth Tamás",
                "email": "horvath.tamas@diak.hu",
                "telefon": "+36305556677",
                "lakhely": "8000 Székesfehérvár, Fő utca 1.",
                "szuletesi_hely": "Székesfehérvár",
                "szuletesi_datum": "2006-03-18",
                "anyja_neve": "Németh Anna",
                "tajszam": "567-890-123",
                "adoazonosito": "8456789012",
                "bankszamlaszam": "11773084-21056789",
                "szakma": "Gépikönyvelő",
                "evfolyam": "12.A",
                "szerzodes_kezdet": "2024-09-01",
                "szerzodes_vege": "2025-06-30",
                "krep_gyakorlati_hely": "Számviteli Kft", # Eltérő képzőhely
                "metadata_json": {"source": "mock_kreta"}
            }
        ]

kreta_service = KretaService()
