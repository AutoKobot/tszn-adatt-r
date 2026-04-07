# EduRegistrar ÁKK - Telepítési és Indítási Útmutató

Ez a rendszer egy modern iskolai nyilvántartó, amely támogatja az OCR alapú adatbevitelt, a duális képzési szerződések generálását és az automatikus naplószinkronizációt.

## 1. Előfeltételek (Mielőtt elkezded)

Győződj meg róla, hogy a következő szoftverek telepítve vannak a laptopodon:
- **Python (3.9+)**: [python.org](https://www.python.org/downloads/) (Telepítéskor jelöld be az "Add Python to PATH" opciót!)
- **PostgreSQL**: [postgresql.org](https://www.postgresql.org/download/) (Az adatbázis tárolásához)
- **Microsoft Word**: (A `.docx` alapú PDF generáláshoz szükséges a `docx2pdf` könyvtárnak)
- **Node.js**: (Ha később React frontendet is használnál, de a jelenlegi HTML felülethez nem kötelező)

## 2. Adatbázis beállítása

1. Nyisd meg a **pgAdmin 4**-et (vagy DBeaver-t).
2. Hozz létre egy új adatbázist: `edu_registrar`.
3. Futtasd le benne az `iskola_schema.sql` tartalmát a táblák létrehozásához.
4. (Opcionális) Futtasd le az `iskola_dummy_adatok.sql`-t a tesztadatokhoz.

## 3. Backend beállítása és indítása

Nyisd meg a **PowerShell**-t vagy a **Parancssort** a projekt mappájában:

```powershell
# Lépj be a projekt mappájába
cd "e:\Antigravity_projektek\iskolai adatbázis"

# Hozz létre egy virtuális környezetet (ajánlott)
python -m venv venv
.\venv\Scripts\activate

# Telepítsd a függőségeket
pip install -r backend/requirements.txt

# Telepítsd a Playwright böngészőket (a szinkronizációhoz)
playwright install chromium
```

### Indítás:
```powershell
# Indítsd el a FastAPI szervert
uvicorn backend.main:app --reload
```
A szerver alapértelmezetten a `http://127.0.0.1:8000` címen fog futni.

## 4. Frontend indítása

Mivel a jelenlegi felület statikus HTML/CSS/JS:
1. Keresd meg a mappáid között az `index.html` fájlt.
2. Kattints rá jobb gombbal és válaszd a **"Megnyitás böngészőben"** (Chrome/Edge ajánlott) opciót.

## 5. Konfiguráció (.env fájl)

Hozz létre egy `.env` fájlt a gyökérkönyvtárban az alábbi tartalommal:
```env
DATABASE_URL=postgresql://postgres:JELSZAVAD@localhost:5432/edu_registrar
SECRET_KEY=tiszalok_titkos_kulcs
```

## Hibaelhárítás
- **OCR hiba**: Ellenőrizd, hogy az `easyocr` települt-e (első indításkor letölti a nyelvi modelleket, ez pár percet igénybe vehet).
- **PDF hiba**: Ha nem generál PDF-et, győződj meg róla, hogy a Word futtatható a háttérben.
