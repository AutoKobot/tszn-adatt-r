import requests
import json

print("Testing local FastAPI backend connection...")
try:
    # 1. Teszteljük a /ping végpontot
    r_ping = requests.get("http://127.0.0.1:8000/ping", timeout=3)
    print(f"[PING] Status: {r_ping.status_code}, Response: {r_ping.json()}")
    
    # 2. Teszteljük a /debug/db végpontot
    r_db = requests.get("http://127.0.0.1:8000/debug/db", timeout=3)
    print(f"[DEBUG_DB] Status: {r_db.status_code}")
    print(json.dumps(r_db.json(), indent=2, ensure_ascii=False))

except requests.exceptions.ConnectionError:
    print("[FAIL] Nem sikerült csatlakozni a helyi szerverhez a http://127.0.0.1:8000 címen!")
    print("  Kérlek győződj meg róla, hogy a 'uvicorn backend.main:app --reload' parancs fut és nincs hibája.")
except Exception as e:
    print(f"[FAIL] Váratlan hiba történt a teszt során: {e}")
