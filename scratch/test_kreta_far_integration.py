import asyncio
import sys
import os

# Szükséges elérési utak beállítása
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.kreta_service import kreta_service
from backend.far_service import far_service

# Mock FAR XML adatok teszteléshez
TEST_FAR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<felnottkepzes>
    <kepzesben_resztvevo>
        <csaladi_nev>Mészáros</csaladi_nev>
        <uto_nev>Béla</uto_nev>
        <szuletesi_hely>Pécs</szuletesi_hely>
        <szuletesi_datum>1995-10-15</szuletesi_datum>
        <anyja_szuletesi_csaladi_neve>Szabó</anyja_szuletesi_csaladi_neve>
        <anyja_szuletesi_uto_neve>Katalin</anyja_szuletesi_uto_neve>
        <taj_szam>456-123-789</taj_szam>
        <adoazonosito_jel>8398765432</adoazonosito_jel>
        <email_cim>meszaros.bela@felnott.hu</email_cim>
        <telefonszam>+36709876543</telefonszam>
        <oktatasi_azonosito>79988776655</oktatasi_azonosito>
        <kepzes_megnevezese>Hegesztő</kepzes_megnevezese>
        <csoport>FAR-HEG-2025</csoport>
        <szerzodes_kezdet>2025-10-01</szerzodes_kezdet>
        <szerzodes_vege>2026-06-30</szerzodes_vege>
        <gyakorlati_hely>Hegesztő Kft</gyakorlati_hely>
    </kepzesben_resztvevo>
</felnottkepzes>
""".encode("utf-8")

async def test_all():
    print("=== INTEGRÁCIÓS SZOLGÁLTATÁSOK DIAGNOSZTIKAI TESZTJE ===")

    # 1. FAR XML parser teszt
    print("\n1. FAR XML parser tesztelése...")
    far_xml_students = far_service.parse_far_xml(TEST_FAR_XML)
    if len(far_xml_students) > 0:
        s = far_xml_students[0]
        print(f"  [SIKER] Sikeres XML beolvasás! Diákok száma: {len(far_xml_students)}")
        print(f"  Név: {s['nev']}")
        print(f"  OM azonosító: {s['oktatasi_azonosito']}")
        print(f"  Születési hely/idő: {s['szuletesi_hely']}, {s['szuletesi_datum']}")
        print(f"  Anyja neve: {s['anyja_neve']}")
        print(f"  TAJ és adószám: {s['tajszam']} | {s['adoazonosito']}")
        print(f"  Képzőhely: {s['krep_gyakorlati_hely']}")
        assert s["nev"] == "Mészáros Béla"
        assert s["oktatasi_azonosito"] == "79988776655"
        assert s["szuletesi_hely"] == "Pécs"
        assert s["anyja_neve"] == "Szabó Katalin"
        assert s["tajszam"] == "456-123-789"
        assert s["adoazonosito"] == "8398765432"
    else:
        print("  [HIBA] FAR XML parser nem talált diákokat!")

    # 2. Kréta API Mock teszt
    print("\n2. Kréta API kliens tesztelése (MOCK módban)...")
    token = await kreta_service.authenticate("mock_school", "mock_admin", "password")
    print(f"  [SIKER] Kréta API token: {token}")
    assert token is not None

    mock_students = await kreta_service.fetch_students("mock_school", token)
    print(f"  [SIKER] Lekért tanulók száma: {len(mock_students)}")
    assert len(mock_students) == 5

    # Szűrési ellenőrzés
    partner_name = "hegesztő kft"
    filtered = [s for s in mock_students if s.get("krep_gyakorlati_hely") and partner_name in s["krep_gyakorlati_hely"].lower()]
    print(f"  [SIKER] Szűrt diákok a(z) '{partner_name}' képzőhelyre: {len(filtered)} fő")
    for s in filtered:
        print(f"    - {s['nev']} (Képzőhely: {s['krep_gyakorlati_hely']})")
    assert len(filtered) == 3

    print("\n=== MINDEN TESZT HIBÁTLANUL LEFUTOTT! ===")

if __name__ == "__main__":
    asyncio.run(test_all())
