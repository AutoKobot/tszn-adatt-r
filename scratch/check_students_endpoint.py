import requests
import json

API_URL = "http://127.0.0.1:8000"

print("--- Testing API Endpoints ---")

# 1. GET /ping
try:
    r = requests.get(f"{API_URL}/ping", timeout=3)
    print(f"[OK] GET /ping status: {r.status_code}")
    print(f"     Response: {r.json()}")
except Exception as e:
    print(f"[FAIL] GET /ping failed: {e}")

# 2. GET /students/
try:
    r = requests.get(f"{API_URL}/students/", timeout=3)
    print(f"[STATUS] GET /students/ status: {r.status_code}")
    if r.status_code == 200:
        print(f"[OK] Successfully fetched students. Total: {len(r.json())}")
        if len(r.json()) > 0:
            print("First student sample:")
            print(json.dumps(r.json()[0], indent=2, ensure_ascii=False))
    else:
        print(f"[FAIL] Failed to fetch students: {r.text}")
except Exception as e:
    print(f"[FAIL] GET /students/ request failed: {e}")

# 3. POST /students/ (Test manual addition)
try:
    test_student = {
        "nev": "Teszt Elek",
        "email": "teszt.elek@pelda.hu",
        "oktatasi_azonosito": "71112223334",
        "tagozat": "nappali",
        "metadata_json": {"szakma": "Szoftverfejlesztő", "iskola": "Teszt Iskola"}
    }
    r = requests.post(f"{API_URL}/students/", json=test_student, timeout=3)
    print(f"[STATUS] POST /students/ status: {r.status_code}")
    if r.status_code in [200, 201]:
        print("[OK] Test student successfully created!")
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    else:
        print(f"[FAIL] Failed to create test student: {r.text}")
except Exception as e:
    print(f"[FAIL] POST /students/ request failed: {e}")
