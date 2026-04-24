# Normatíva és Költségkalkulátor – Végleges Megvalósítási Terv

> Ez a dokumentum a korábbi tervek és a 4 Pillér keretrendszer összevonásával készült.  
> **Ezt kövessük az implementáció során lépésről lépésre.**

---

## A 4 Pillér – Rendszer Architektúra

```
┌─────────────────────────────────────────────────────────────┐
│  1. PILLÉR          │  2. PILLÉR          │  3. PILLÉR      │
│  Adat-Iker          │  Jelenlét-Motor     │  Számítási Réteg│
│  (Digital Twin)     │  (Tiszta adatok)    │  (Stratégiai agy│
├─────────────────────┴─────────────────────┴─────────────────┤
│              4. PILLÉR – Dokumentum-Architektúra             │
│         (Automatizált könyvelői + kamarai outputok)          │
└─────────────────────────────────────────────────────────────┘
```

### 1. Pillér – Adat-Iker (Digital Twin)
A valóság pontos digitális leképezése 3 komponensből:
- **Szakma-mátrix** (`SzakmaTorzs` tábla) – szakmakód, megnevezés, súlyszorzó
- **Idővonal-kezelő** (`TanevRendje` tábla) – szünetek, vizsgaidőszak, munkaszüneti napok
- **Szerződés-figyelő** – a `Student.szerzodes_kezdet` / `szerzodes_vege` adja a számítási keretet

### 2. Pillér – Jelenlét-Logikai Motor
Kategorizált napi státuszok (nem csak szöveg!). **Minden naphoz egy státusz:**

| Státusz | Normatíva hatás | Leírás |
|---|---|---|
| `dualis_nap` | ✅ 100% | A tanuló a cégnél teljesít |
| `iskolai_nap` | ❌ 0% | Elméleti oktatás – jogviszony él, de normatíva nem jár |
| `betegszabadsag` | ✅ 100% | **Jogszabály szerint jár a normatíva!** |
| `fizetett_szabadsag` | ✅ 100% | Jár a normatíva |
| `igazolatlan_hianyzas` | ❌ Levonás | Normatívából ÉS tanulói bérből is levon |
| `munkaszuneti_nap` | ➖ Semleges | Nem számít az elvártba |

> ⚠️ **Kritikus pont:** A betegszabadság és fizetett szabadság normatíva-jogosultsága pénzügyi szempontból döntő – ezeket külön kell kezelni az egyszerű hiányzástól!

### 3. Pillér – Számítási Réteg
**A) Retrospektív (Könyvelői csomag):** Lezárt hónap → pontos adóbevallási összeg  
**B) Prediktív (Prognózis):** Hátralévő képzési időre várható teljes állami támogatás + Sikerdíj  
**C) ROI számítás:** `Kapott normatíva – Kifizetett tanulói bérek = Projekt nettó nyeresége`

### 4. Pillér – Automatizált Dokumentum-Architektúra
- Havi igazolás a szakmai gyakorlatról (PDF)
- Bérjegyzék-alapanyag (hiányzás-levonásokkal)
- Kamarai adatszolgáltatási export (CSV/XML)

---

## 0. LÉPÉS – Adatbeszerzési Réteg (ELŐFELTÉTEL!)

> **Ez az egész rendszer alapja.** Ha a szorzók és az alapösszeg nincs helyesen betöltve,  
> a kalkulátor hibás eredményt ad. Ezt az 1. lépés (adatmodell) előtt kell megtervezni.

### Milyen adatokat kell beszerezni?

| Adat | Forrás (jogszabályi) | Frissítési gyakoriság |
|---|---|---|
| **Önköltségi alapösszeg (Ö)** | Éves rendelet (Nemzeti Jogszabálytár) | Évente (tanév elején) |
| **Szakmaszorzók (S)** | SZVK-ban rögzített szorzótáblázat | Ritkán változik (rendelet módosításkor) |
| **Munkaszüneti napok** | Magyar állami munkaszüneti naptár | Évente |
| **Tanév rendje** | EMMI/Oktatási Hivatal rendelet | Évente (tanévkezdéskor) |

---

### 0/A – Automatikus adatbetöltés: Seed fájl (Elsődleges megoldás)

A rendszer indításakor egy JSON seed fájlból tölti be az alapadatokat, ha az adatbázis üres.  
**Ez a legmegbízhatóbb megoldás** – offline is működik, nincs külső függőség.

**Fájl helye:** `backend/seed_data/normativa_seed.json`

```json
{
  "tanev": "2025/2026",
  "onkoltsegi_alap": 1200000,
  "sikerdij_szazalek": 20.0,
  "szakmak": [
    {
      "szakma_szam": "4-0611-16-Y",
      "megnevezes": "Szoftverfejlesztő, -tesztelő",
      "agazat": "Informatika",
      "szorzo": 1.20
    },
    {
      "szakma_szam": "3-0521-16-Y",
      "megnevezes": "Hegesztő",
      "agazat": "Gépészet",
      "szorzo": 2.42
    },
    {
      "szakma_szam": "3-0522-16-Y",
      "megnevezes": "Asztalos",
      "agazat": "Faipar",
      "szorzo": 1.85
    }
  ],
  "munkaszuneti_napok_2025_2026": [
    "2025-10-23", "2025-11-01", "2025-12-25", "2025-12-26",
    "2026-01-01", "2026-03-15", "2026-04-03", "2026-04-06",
    "2026-05-01", "2026-06-08"
  ]
}
```

**Backend logika** (`backend/seed_service.py`):
```python
def seed_if_empty(db: Session):
    """Indításkor lefut – csak ha a táblák üresek."""
    if db.query(models.SzakmaTorzs).count() == 0:
        with open("backend/seed_data/normativa_seed.json") as f:
            data = json.load(f)
        for s in data["szakmak"]:
            db.add(models.SzakmaTorzs(**s, onkoltsegi_alap=data["onkoltsegi_alap"]))
        # NormativaKonfig feltöltése
        db.add(models.NormativaKonfig(
            tanev_nev=data["tanev"],
            onkoltsegi_alap_default=data["onkoltsegi_alap"],
            sikerdij_szazalek=data["sikerdij_szazalek"],
            aktiv=True
        ))
        # TanevRendje munkaszüneti napok
        for nap_str in data["munkaszuneti_napok_2025_2026"]:
            db.add(models.TanevRendje(
                tanev_nev=data["tanev"],
                datum=datetime.date.fromisoformat(nap_str),
                tipus="munkaszuneti"
            ))
        db.commit()
        print("[SEED] Alapadatok betöltve a seed fájlból.")
```

Hívás helye: `lifespan()` függvényben, az adatbázis inicializálás után.

---

### 0/B – Excel/CSV Import (Másodlagos megoldás)

Ha az iskola megkapja a hatályos szakmaszorzó listát Excel-ben (pl. NSZFH-tól), fel tudja tölteni.

**Új API végpont:** `POST /admin/szakmak/import`

```python
@app.post("/admin/szakmak/import")
async def import_szakmak_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Elfogad egy CSV/Excel fájlt a következő oszlopokkal:
    szakma_szam | megnevezes | agazat | szorzo | onkoltsegi_alap
    """
    content = await file.read()
    # pandas-szal beolvasás, normalizálás
    # Meglévő szakmák UPDATE, újak INSERT
    # Visszajelzés: hány sor frissítve, hány új
```

**CSV fejléc formátum** (amit az admin feltölt):
```
szakma_szam;megnevezes;agazat;szorzo;onkoltsegi_alap
4-0611-16-Y;Szoftverfejlesztő, -tesztelő;Informatika;1.20;1200000
3-0521-16-Y;Hegesztő;Gépészet;2.42;1200000
```

---

### 0/C – Manuális bevitel az Admin UI-n (Mindig elérhető)

Az admin bármikor kézzel is módosíthat minden értéket. Ez a **fallback** és a **jogszabályváltozás-kezelő**.

**UI elem (a Normatíva tab tetején):**
```
┌──────────────────────────────────────────────────────────────┐
│  ⚙️  Tanév alapadatok beállítása                             │
├──────────────────────────────────────────────────────────────┤
│  Aktív tanév:       [2025/2026        ]                      │
│  Önköltségi alap:  [1200000          ] Ft/év                 │
│  Sikerdíj:         [20               ] %                     │
│                    [💾 Mentés]   [📋 Másolás előző tanévről]  │
├──────────────────────────────────────────────────────────────┤
│  ℹ️ Adatok utolsó frissítése: 2025-09-01  (seed fájlból)     │
│  [📥 Import Excel/CSV-ből]  [🔄 Ellenőrzés forrással]        │
└──────────────────────────────────────────────────────────────┘
```

---

### 0/D – Automatikus Ellenőrzés (Opcionális, haladó funkció)

> Csak akkor implementálandó, ha az iskola igényli. Első körben a seed fájl elegendő.

Az NSZFH (Nemzeti Szakképzési és Felnőttképzési Hivatal) és az NJT (Nemzeti Jogszabálytár) nyilvános weboldalakon publikálják a szorzókat. Egy backend service évente egyszer ellenőrzi:

```python
class NormativaDataFetcher:

    NJT_URL = "https://njt.hu/jogszabaly/..."  # Konkrét rendelet URL-je
    NSZFH_URL = "https://nszfh.gov.hu/..."

    async def check_for_updates(self, db: Session) -> dict:
        """
        Évente egyszer lefut (pl. szeptember 1-én, a nightly_sync_loop-ban).
        1. Lekéri a nyilvános forrást
        2. Összehasonlítja a DB-ben lévő adatokkal
        3. Ha eltérés van → értesíti az admint (nem frissít automatikusan!)
        4. Az admin jóváhagyja vagy elveti a változást
        """
        # Scraping vagy strukturált adat lekérés
        # Visszaad: {"valtozas_van": True, "reszletek": [...]}
        pass

    def notify_admin(self, valtozasok: list, db: Session):
        """Audit log bejegyzés + dashboard értesítés az adminnak."""
        pass
```

**Fontos:** Az automatikus fetch **SOHA nem ír az adatbázisba jóváhagyás nélkül.**  
Csak értesítést küld: *„Az önköltségi alap 1.350.000 Ft-ra változott a jogszabályban. Szeretné frissíteni?"*

---

### 0/E – Adatfrissesség Jelző (UI elem)

Minden szorzó és alapösszeg mellett jelenjen meg, mikor és honnan jött az adat:

```
Szorzó: 2.42   📅 Forrás: seed fájl │ 2025-09-01   [✏️ Szerkesztés]
                                     └─ Ha kézzel lett módosítva: "Kézi bevitel │ 2025-11-15"
```

**Adatmodell-kiegészítés a `SzakmaTorzs` táblán:**
```python
adat_forrasa   = Column(String(50), default="seed")  # 'seed', 'import', 'kezzel', 'auto'
utolso_frissites = Column(TIMESTAMP, default=datetime.datetime.utcnow)
```

---

### Összefoglalás: Adatbeszerzési Prioritási Sorrend

```
1. Seed fájl betöltés (automatikus, indításkor)      → offline, megbízható
       ↓ ha nincs / hiányos
2. Excel/CSV import (admin tölti fel)                → rugalmas, iskola-specifikus
       ↓ ha változik valami
3. Kézi szerkesztés az admin UI-n                   → azonnali, bármikor
       ↓ opcionálisan, haladó szinten
4. Automatikus forrás-ellenőrzés (NJT/NSZFH)        → értesítés, nem automatikus írás
```

---

## Az Alapképlet

```
T = Ö × S × M
```

| Változó | Leírás | Példa |
|---|---|---|
| **Ö** | Éves önköltségi alapösszeg (Ft) | 1.200.000 Ft |
| **S** | Szakmaszorzó (szakmánként eltérő) | Hegesztő: 2.42 / Szoftverfejlesztő: 1.2 |
| **M** | Munkanap-arány (0.0–1.0) | 18 teljesített / 21 elvárt = 0.857 |

**Havi összeg = (Ö × S × M) / 12**  
**Példa:** `(1.200.000 × 2.42 × 0.857) / 12 ≈ 138.629 Ft/hó`

A számított havi összeg duális képzésnél **1:1 arányban érvényesíthető adókedvezményként**.

---

## Döntési Pontok (Egyeztetni Kell Implementáció Előtt!)

Ezeket **nem feltételezhetjük** – le kell fixálni mielőtt kódot írunk:

| # | Kérdés | Két lehetséges válasz |
|---|---|---|
| D1 | **Munkanap vs. Óra** | A) 1 nap = 8 óra átváltás a meglévő Attendance-ből VAGY B) Új "napi pipa" rögzítési mód |
| D2 | **Munkaszüneti napok** | A) Admin adja meg évenként manuálisan VAGY B) Automatikus (python-munkaszunetek csomag) |
| D3 | **Sikerdíj feltétele** | A) Checkbox a diák adatlapján ("Záróvizsga sikeres") VAGY B) Külön vizsga-esemény tábla |
| D4 | **What-if kimenet** | A) Csak egyösszegű szám VAGY B) Havi cash-flow grafikon 12 hónapra |

---

## LÉPÉS 1 – Adatmodell bővítése (`backend/models.py`)

### 1/A – Új tábla: `SzakmaTorzs`
Ez az admin által szerkeszthető szakmatörzs. Ha jogszabály változik, csak itt kell módosítani.

```python
class SzakmaTorzs(Base):
    __tablename__ = "szakma_torzs"
    id              = Column(Integer, primary_key=True, index=True)
    szakma_szam     = Column(String(20), unique=True)        # OKJ/SZVK szám
    megnevezes      = Column(String(255), nullable=False)
    agazat          = Column(String(100))                     # pl. "Gépészet"
    szorzo          = Column(Numeric(5, 4), nullable=False)  # pl. 2.4200
    onkoltsegi_alap = Column(Integer, nullable=False)        # Ft, pl. 1200000
    aktiv           = Column(Boolean, default=True)
    ervenyes_tol    = Column(Date, nullable=True)
    ervenyes_ig     = Column(Date, nullable=True)
    megjegyzes      = Column(Text)
    letrehozva      = Column(TIMESTAMP, default=datetime.datetime.utcnow)
```

### 1/B – Új tábla: `NormativaKonfig`
Tanév-szintű globális beállítások (alapértelmezett önköltségi alap, sikerdíj %).

```python
class NormativaKonfig(Base):
    __tablename__ = "normativa_konfig"
    id                       = Column(Integer, primary_key=True, index=True)
    tanev_nev                = Column(String(50), nullable=False)  # "2025/2026"
    aktiv                    = Column(Boolean, default=True)
    onkoltsegi_alap_default  = Column(Integer, nullable=False)     # Ft
    sikerdij_szazalek        = Column(Numeric(4, 2), default=20.0) # pl. 20.00
    letrehozva               = Column(TIMESTAMP, default=datetime.datetime.utcnow)
```

### 1/C – Új tábla: `KoltsegTetel`
Egyéb, manuálisan rögzített költségtételek (védőfelszerelés, oktatói díj stb.).

```python
class KoltsegTetel(Base):
    __tablename__ = "koltseg_tetelek"
    id         = Column(Integer, primary_key=True, index=True)
    osztaly_id = Column(Integer, ForeignKey("osztalyok.id"), nullable=True)
    diak_id    = Column(Integer, ForeignKey("diakok.id"), nullable=True)
    idoszak    = Column(String(20))          # pl. "2025-09" vagy "2025/2026-1"
    tetel_nev  = Column(String(255), nullable=False)
    osszeg     = Column(Integer, nullable=False)  # Ft
    kategoria  = Column(String(50))          # 'vedofelszereles','oktato','admin','egyeb'
    megjegyzes = Column(Text)
    letrehozva = Column(TIMESTAMP, default=datetime.datetime.utcnow)
```

### 1/D – Meglévő `Student` modell bővítése
```python
# Hozzáadandó sor a Student osztályhoz:
szakma_torzs_id = Column(Integer, ForeignKey("szakma_torzs.id"), nullable=True)
# A metadata_json["szakma"] string visszafelé-kompatibilis marad!
```

### 1/E – Meglévő `Attendance` modell bővítése
```python
# RÉGI értékek: 'jelen', 'igazolt_hianyzas', 'igazolatlan_hianyzas'
# ÚJ, teljes státusz-lista (2. Pillér alapján):
# 'dualis_nap'          → 100% normatíva (cégnél töltött nap)
# 'iskolai_nap'         → 0% normatíva (elméleti oktatás)
# 'betegszabadsag'      → 100% normatíva (jogszabály!)
# 'fizetett_szabadsag'  → 100% normatíva
# 'igazolatlan_hianyzas'→ levonás normatívából ÉS bérből
# 'munkaszuneti_nap'    → semleges, nem számít az elvártba
# 'szunet'              → semleges (iskolai szünet)
```

### 1/F (Új) – Új tábla: `TanevRendje` (Idővonal-kezelő)
```python
class TanevRendje(Base):
    __tablename__ = "tanev_rendje"
    id         = Column(Integer, primary_key=True, index=True)
    tanev_nev  = Column(String(50))          # pl. "2025/2026"
    datum      = Column(Date, nullable=False)
    tipus      = Column(String(30))          # 'tanítási_nap','szünet','vizsga','munkaszüneti'
    megjegyzes = Column(Text)
    letrehozva = Column(TIMESTAMP, default=datetime.datetime.utcnow)
```

### 1/F – Adatbázis-migráció (`lifespan` blokkban, `main.py`)
```python
db.execute(text("ALTER TABLE diakok ADD COLUMN IF NOT EXISTS szakma_torzs_id INTEGER;"))
db.execute(text("""
    CREATE TABLE IF NOT EXISTS szakma_torzs (
        id SERIAL PRIMARY KEY, megnevezes VARCHAR(255) NOT NULL,
        szakma_szam VARCHAR(20) UNIQUE, agazat VARCHAR(100),
        szorzo NUMERIC(5,4) NOT NULL, onkoltsegi_alap INTEGER NOT NULL,
        aktiv BOOLEAN DEFAULT TRUE, letrehozva TIMESTAMP DEFAULT NOW()
    );
"""))
db.execute(text("""
    CREATE TABLE IF NOT EXISTS normativa_konfig (
        id SERIAL PRIMARY KEY, tanev_nev VARCHAR(50) NOT NULL,
        aktiv BOOLEAN DEFAULT TRUE, onkoltsegi_alap_default INTEGER NOT NULL,
        sikerdij_szazalek NUMERIC(4,2) DEFAULT 20.0, letrehozva TIMESTAMP DEFAULT NOW()
    );
"""))
db.execute(text("""
    CREATE TABLE IF NOT EXISTS koltseg_tetelek (
        id SERIAL PRIMARY KEY, osztaly_id INTEGER, diak_id INTEGER,
        idoszak VARCHAR(20), tetel_nev VARCHAR(255) NOT NULL,
        osszeg INTEGER NOT NULL, kategoria VARCHAR(50), letrehozva TIMESTAMP DEFAULT NOW()
    );
"""))
```

---

## LÉPÉS 2 – Pydantic Sémák (`backend/schemas.py`)

```python
# --- SZAKMATÖRZS ---
class SzakmaBase(BaseModel):
    megnevezes: str
    szakma_szam: Optional[str] = None
    agazat: Optional[str] = None
    szorzo: float
    onkoltsegi_alap: int
    aktiv: bool = True

class SzakmaCreate(SzakmaBase): pass
class SzakmaUpdate(BaseModel):
    megnevezes: Optional[str] = None
    szorzo: Optional[float] = None
    onkoltsegi_alap: Optional[int] = None
    aktiv: Optional[bool] = None
class Szakma(SzakmaBase):
    id: int
    model_config = {"from_attributes": True}

# --- KALKULÁTOR KIMENETEK ---
class NormativaHaviResult(BaseModel):
    diak_id: int
    ev: int
    honap: int
    havi_normativa: int           # Ft
    adokedvezmeny: int            # Ft (megegyezik havi_normativa-val)
    sikerdij_celtar: int          # Ft (felhalmozott sikerdíj-rész)
    munkanap_arany: float         # 0.0–1.0
    szorzo: float
    onkoltsegi_alap: int
    jogosult: bool                # M >= 0.8

class NormativaEvesResult(BaseModel):
    diak_id: int
    tanev: str
    tenyleges_osszeg: int         # Ft (eddig tényleg kiszámolt hónapok)
    prognozis_osszeg: int         # Ft (ha minden hónap M=1.0 lenne)
    sikerdij_celtar_ossz: int     # Ft (teljes évi céltartalék)
    teljesitett_honapok: int
    osszes_honapok: int           # pl. 10 (szept–jún)

class WhatIfRequest(BaseModel):
    tervezett_diakok: list[dict]  # [{"szakma_id": 3, "db": 2}, ...]
    idoszak_kezdet: str           # pl. "2025-09"

class WhatIfResponse(BaseModel):
    jelenlegi_havi_keret: int     # Ft
    szimulalt_havi_keret: int     # Ft
    valtozas_havi: int            # Ft
    valtozas_eves: int            # Ft
    reszletezés: list[dict]       # szakmánként bontva

# --- NORMATÍVA KONFIG ---
class NormativaKonfigCreate(BaseModel):
    tanev_nev: str
    onkoltsegi_alap_default: int
    sikerdij_szazalek: float = 20.0
    aktiv: bool = True
class NormativaKonfig(NormativaKonfigCreate):
    id: int
    model_config = {"from_attributes": True}
```

---

## LÉPÉS 3 – Kalkulátor Motor (`backend/normativa_service.py`)

Új fájl. Ez a rendszer "agya" – független a FastAPI-tól, jól tesztelhető.

```python
import calendar
import datetime
from sqlalchemy.orm import Session
from . import models

class NormativaService:

    def get_szakma(self, diak_id: int, db: Session):
        student = db.query(models.Student).get(diak_id)
        if student and student.szakma_torzs_id:
            return db.query(models.SzakmaTorzs).get(student.szakma_torzs_id)
        return None

    def get_aktiv_konfig(self, db: Session):
        return db.query(models.NormativaKonfig).filter(
            models.NormativaKonfig.aktiv == True
        ).first()

    def get_munkanap_arany(self, diak_id: int, ev: int, honap: int, db: Session) -> float:
        """
        Kiszámolja az M értéket az adott hónapra.
        Elvárt munkanapok: hónap összes napja - hétvégék - munkaszüneti_nap státuszú jelenlét sorok.
        Teljesített napok: 'jelen' + 'betegszabadsag' státuszú sorok (D3 döntéstől függhet!).
        """
        # Hónap összes napja
        _, napok_szama = calendar.monthrange(ev, honap)
        datum_kezd = datetime.date(ev, honap, 1)
        datum_vege = datetime.date(ev, honap, napok_szama)

        # Összes jelenlét sor az adott hónapban
        att_sorok = db.query(models.Attendance).filter(
            models.Attendance.diak_id == diak_id,
            models.Attendance.datum >= datum_kezd,
            models.Attendance.datum <= datum_vege
        ).all()

        # D1 döntés alapján: ha óra alapú, akkor nap = oraszam / 8
        jelen_napok = sum(
            1 for a in att_sorok if a.statusz == "jelen"
        )
        munkaszuneti_napok = sum(
            1 for a in att_sorok if a.statusz == "munkaszuneti_nap"
        )

        # Elvárt munkanapok = hétköznapok - munkaszüneti napok
        hetkonapok = sum(
            1 for d in range(napok_szama)
            if (datum_kezd + datetime.timedelta(days=d)).weekday() < 5
        )
        elvart = max(hetkonapok - munkaszuneti_napok, 1)

        return round(min(jelen_napok / elvart, 1.0), 4)

    def kalkulal_havi(self, diak_id: int, ev: int, honap: int, db: Session) -> dict:
        szakma = self.get_szakma(diak_id, db)
        konfig = self.get_aktiv_konfig(db)

        if not szakma:
            return {"hiba": "A diákhoz nincs hozzárendelve szakma a törzsadatbázisból."}

        O = szakma.onkoltsegi_alap
        S = float(szakma.szorzo)
        M = self.get_munkanap_arany(diak_id, ev, honap, db)

        eves_T = O * S           # Teljes éves összeg (ha M=1.0)
        havi_T = (eves_T * M) / 12  # Arányos havi összeg

        sikerdij_szazalek = float(konfig.sikerdij_szazalek) / 100 if konfig else 0.20
        sikerdij = havi_T * sikerdij_szazalek

        return {
            "diak_id": diak_id,
            "ev": ev, "honap": honap,
            "havi_normativa": round(havi_T),
            "adokedvezmeny": round(havi_T),
            "sikerdij_celtar": round(sikerdij),
            "munkanap_arany": M,
            "szorzo": S,
            "onkoltsegi_alap": O,
            "jogosult": M >= 0.8,
        }

    def kalkulal_eves_prognozis(self, diak_id: int, tanev: str, db: Session) -> dict:
        """Összesíti a múlt hónapokat + becsüli a jövőt M=1.0 feltételezéssel."""
        ev = int(tanev.split("/")[0])
        honapok = list(range(9, 13)) + list(range(1, 7))  # szept–jún
        evek = [ev] * 4 + [ev + 1] * 6

        tenyleges = 0
        prognozis = 0
        teljesitett = 0
        ma = datetime.date.today()

        for honap, e in zip(honapok, evek):
            vizsgalt = datetime.date(e, honap, 1)
            if vizsgalt <= ma.replace(day=1):
                eredmeny = self.kalkulal_havi(diak_id, e, honap, db)
                tenyleges += eredmeny.get("havi_normativa", 0)
                teljesitett += 1
            else:
                # Jövőbeli hónap: M=1.0 feltételezés
                szakma = self.get_szakma(diak_id, db)
                if szakma:
                    prognozis += round((szakma.onkoltsegi_alap * float(szakma.szorzo)) / 12)

        konfig = self.get_aktiv_konfig(db)
        sikerdij_pct = float(konfig.sikerdij_szazalek) / 100 if konfig else 0.20

        return {
            "diak_id": diak_id,
            "tanev": tanev,
            "tenyleges_osszeg": tenyleges,
            "prognozis_osszeg": tenyleges + prognozis,
            "sikerdij_celtar_ossz": round((tenyleges + prognozis) * sikerdij_pct),
            "teljesitett_honapok": teljesitett,
            "osszes_honapok": 10,
        }

    def what_if(self, tervezett_diakok: list, idoszak_kezdet: str, db: Session) -> dict:
        """Szimulátor: Ha X db új tanuló adott szakmával csatlakozna, mennyi a várható plusz keret?"""
        jelenlegi = sum(
            self.kalkulal_havi(s.id, datetime.date.today().year, datetime.date.today().month, db).get("havi_normativa", 0)
            for s in db.query(models.Student).all()
        )
        plusz_havi = 0
        reszletek = []
        for t in tervezett_diakok:
            szakma = db.query(models.SzakmaTorzs).get(t["szakma_id"])
            if szakma:
                havi = round((szakma.onkoltsegi_alap * float(szakma.szorzo)) / 12 * t.get("db", 1))
                plusz_havi += havi
                reszletek.append({"szakma": szakma.megnevezes, "db": t.get("db", 1), "havi_plusz": havi})

        return {
            "jelenlegi_havi_keret": jelenlegi,
            "szimulalt_havi_keret": jelenlegi + plusz_havi,
            "valtozas_havi": plusz_havi,
            "valtozas_eves": plusz_havi * 12,
            "reszletezés": reszletek,
        }

    def roi_szamitas(self, diak_id: int, tanev: str, db: Session) -> dict:
        """
        3. Pillér – ROI számítás:
        Kapott normatíva - Kifizetett tanulói bérek = Projekt nettó nyeresége
        """
        prognozis = self.kalkulal_eves_prognozis(diak_id, tanev, db)
        student = db.query(models.Student).get(diak_id)

        # Kifizetett bérek: a jelenlét 'dualis_nap' napok × napi bér
        # (A napi bért a normativa_konfig-ból vagy fix értékként vesszük)
        # Egyszerűsített: havi normatíva 40%-a megy ki bérként a diáknak
        kifizetett_berek = round(prognozis["tenyleges_osszeg"] * 0.40)
        kapott_normativa = prognozis["tenyleges_osszeg"]
        netto_nyereseg = kapott_normativa - kifizetett_berek

        return {
            "diak_id": diak_id,
            "tanev": tanev,
            "kapott_normativa": kapott_normativa,
            "kifizetett_berek": kifizetett_berek,
            "netto_nyereseg": netto_nyereseg,
            "roi_szazalek": round((netto_nyereseg / max(kifizetett_berek, 1)) * 100, 1),
        }

normativa_service = NormativaService()
```

---

## LÉPÉS 4 – API Végpontok (`backend/main.py`)

Szúrjuk be a következő blokkot a meglévő `main.py` végére (a `StaticFiles` mount elé):

```python
from .normativa_service import normativa_service
from . import models as mdl  # ha ütközne a névvel

# --- SZAKMATÖRZS CRUD ---
@app.get("/admin/szakmak/", response_model=list[schemas.Szakma])
def list_szakmak(db: Session = Depends(get_db)):
    return db.query(models.SzakmaTorzs).all()

@app.post("/admin/szakmak/", response_model=schemas.Szakma)
def create_szakma(s: schemas.SzakmaCreate, db: Session = Depends(get_db)):
    db_s = models.SzakmaTorzs(**s.dict())
    db.add(db_s); db.commit(); db.refresh(db_s)
    return db_s

@app.put("/admin/szakmak/{szakma_id}", response_model=schemas.Szakma)
def update_szakma(szakma_id: int, s: schemas.SzakmaUpdate, db: Session = Depends(get_db)):
    db_s = db.query(models.SzakmaTorzs).get(szakma_id)
    if not db_s: raise HTTPException(404, "Szakma nem található")
    for k, v in s.dict(exclude_unset=True).items():
        setattr(db_s, k, v)
    db.commit(); db.refresh(db_s)
    return db_s

# --- NORMATÍVA KONFIG ---
@app.get("/normativa/konfig/aktiv", response_model=schemas.NormativaKonfig)
def get_aktiv_konfig(db: Session = Depends(get_db)):
    k = normativa_service.get_aktiv_konfig(db)
    if not k: raise HTTPException(404, "Nincs aktív konfiguráció")
    return k

@app.post("/normativa/konfig", response_model=schemas.NormativaKonfig)
def create_konfig(k: schemas.NormativaKonfigCreate, db: Session = Depends(get_db)):
    # Korábbi aktív konfig deaktiválása
    db.query(models.NormativaKonfig).filter(models.NormativaKonfig.aktiv == True).update({"aktiv": False})
    db_k = models.NormativaKonfig(**k.dict())
    db.add(db_k); db.commit(); db.refresh(db_k)
    return db_k

# --- KALKULÁTOR ---
@app.get("/normativa/student/{student_id}", response_model=schemas.NormativaHaviResult)
def get_normativa_havi(student_id: int, ev: int, honap: int, db: Session = Depends(get_db)):
    return normativa_service.kalkulal_havi(student_id, ev, honap, db)

@app.get("/normativa/student/{student_id}/eves")
def get_normativa_eves(student_id: int, tanev: str = "2025/2026", db: Session = Depends(get_db)):
    return normativa_service.kalkulal_eves_prognozis(student_id, tanev, db)

@app.post("/normativa/what-if", response_model=schemas.WhatIfResponse)
def what_if_szimulator(req: schemas.WhatIfRequest, db: Session = Depends(get_db)):
    return normativa_service.what_if(req.tervezett_diakok, req.idoszak_kezdet, db)

@app.get("/normativa/class/{class_id}/export")
def export_normativa_osztaly(class_id: int, ev: int, honap: int, db: Session = Depends(get_db)):
    """CSV export könyveléshez / bérszámfejtőhöz."""
    diakok = db.query(models.Student).filter(models.Student.osztaly_id == class_id).all()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Nev', 'Szakmaszam', 'Szorzo', 'Munkanap arany', 'Havi normativa (Ft)', 'Adokedvezmeny (Ft)', 'Jogosult'])
    for d in diakok:
        r = normativa_service.kalkulal_havi(d.id, ev, honap, db)
        szakma = normativa_service.get_szakma(d.id, db)
        writer.writerow([
            d.nev, szakma.szakma_szam if szakma else '', r.get('szorzo',''),
            r.get('munkanap_arany',''), r.get('havi_normativa',''),
            r.get('adokedvezmeny',''), 'Igen' if r.get('jogosult') else 'Nem'
        ])
    output.seek(0)
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=normativa_{class_id}_{ev}_{honap:02d}.csv"
    return response
```

---

## LÉPÉS 5 – Frontend (`admin_dashboard.html`)

### 5/A – Új "Normatíva" Tab hozzáadása a navigációhoz
```html
<!-- A meglévő tab navigációba illesztendő -->
<button class="tab-btn" onclick="showTab('normativa')">📊 Normatíva</button>
```

### 5/B – Normatíva Tab tartalma (UI blokkok)

**1. Konfiguráció kártya (tanév + szakmaszorzók szerkesztője)**
- Legördülő: tanév kiválasztás / létrehozás
- Táblázat: szakma neve, szám, szorzó, önköltségi alap – szerkeszthető sorokkal
- "Mentés" gomb → `PUT /admin/szakmak/{id}`

**2. Összesítő kártyák (havi nézet)**
```
[ Teljes havi adókedvezmény ] [ Jogosult diákok X/Y ] [ Sikerdíj-céltartalék ]
```
Adatforrás: `GET /normativa/class/{id}?ev=...&honap=...`

**3. Diáklista táblázat**
| Diák neve | Szakma | Szorzó | Munkanap% | Havi normatíva | Jogosult |
|---|---|---|---|---|---|

**4. What-if Szimulátor panel**
```
[ + Új sor ] → Szakma ▼  Létszám ▼
[ ▶ Szimulálás ]
→ Eredmény: Jelenlegi: X Ft | Szimulált: Y Ft | Különbség: +Z Ft/év
```

### 5/C – "Pénzügyi Fül" a Diák Modalban
Az existing diák-modal-ba egy új fül:
```
Havi normatíva: 138.629 Ft    Éves prognózis: 1.663.543 Ft
Jogosultság: ✅ (M = 0.857)
Sikerdíj-céltartalék: [████████░░] 33.271 Ft / 4 hó teljesítve
```
Adatforrás: `GET /normativa/student/{id}?ev=...&honap=...` + `.../eves`

---

## LÉPÉS 5/D – Vizuális Megértés-Támogató Elemek (UX Edukáció)

> **Alapelv:** Az admin ne csak számokat lásson, hanem értse az összefüggéseket.  
> Ha egy kolléga megkérdezi „miért ennyi a normatíva?", az admin válaszolni tudjon – mert a felület megmutatta.

### 5/D-1 – Képletmagyarázó Panel

A Normatíva tab tetején: kinyitható `<details>` elem, ami élő számokkal mutatja a képletet:

```
┌──────────────────────────────────────────────────────────────┐
│  ℹ️  Hogyan számítódik a normatíva?                 [▼ Csuk] │
├──────────────────────────────────────────────────────────────┤
│  T = Ö  ×  S  ×  M                                          │
│      ↓      ↓      ↓                                         │
│  1.200.000  2.42  18/21 nap                                  │
│  (állam)   (jszab) (te rögzíted)                             │
│                                                              │
│  Havi = (1.200.000 × 2.42 × 0.857) / 12 = 138.629 Ft        │
│  Ez az összeg a havi adóbevallásból levonható (08-as nyomtatv.)│
└──────────────────────────────────────────────────────────────┘
```

**Implementáció:** `<details><summary>` + CSS animáció. A számok az aktuális kiválasztott diák adatait tükrözik.

---

### 5/D-2 – Jelenlét-Státusz Legenda (állandóan látható)

A jelenléti nézet mellé rögzítve – ne kelljen fejből tudni, melyik szín mit jelent:

```
┌─────────────────┬────────────┬──────────────────────┐
│  Státusz        │  Szín      │  Normatíva hatás     │
├─────────────────┼────────────┼──────────────────────┤
│  Duális nap     │  🟢 Zöld   │  ✅ 100% – beleszámít │
│  Iskolai nap    │  🔵 Kék    │  ❌ 0%  – NEM számít  │
│  Betegszabadság │  🟡 Sárga  │  ✅ 100% – JÁR!       │
│  Fiz. szabadság │  🟡 Sárga  │  ✅ 100% – jár        │
│  Igazolat. hián │  🔴 Piros  │  ❌ Levonás (bérből!) │
│  Munkaszüneti   │  ⬜ Szürke │  ➖ Semleges           │
└─────────────────┴────────────┴──────────────────────┘

⚠️  A betegszabadság NEM hiányzás – normatíva jár utána!
    (Ez a leggyakoribb adminisztrációs félreértés.)
```

**Implementáció:** Statikus HTML tábla, CSS színekkel. A `⚠️` sor sárga `background`-dal emelendő ki.

---

### 5/D-3 – Havi Jelenlét-Bontás Sávdiagram (diákonként)

```
Kovács Péter – 2025. november (21 munkanap)

Duális nap    [████████████████░░░]  17 nap (81%)  ← M-be beleszámít
Iskolai nap   [██░░░░░░░░░░░░░░░░░]   2 nap  (9%)  ← NEM számít M-be
Betegszabads. [██░░░░░░░░░░░░░░░░░]   2 nap  (9%)  ← beleszámít ✅
Igazolat.     [░░░░░░░░░░░░░░░░░░░]   0 nap  (0%)

M = (17 + 2) / 21 = 0.905   →  ✅ Jogosult  (küszöb: 0.80)
Havi normatíva: 152.034 Ft
```

**Implementáció:** CSS `width: X%` sávok – Chart.js nem kell. Hover-re tooltip mutatja az összeg-bontást.

---

### 5/D-4 – ROI Kártya (Megtérülés)

```
┌──────────────────────────────────────────────┐
│  📈 Befektetés-megtérülés (ROI) – 2025/2026  │
├──────────────────────────────────────────────┤
│  Kifizetett tanulói bérek:   −1.923.000 Ft   │
│  Kapott állami normatíva:   +2.847.320 Ft    │
│                              ──────────      │
│  Nettó nyereség:            +924.320 Ft  🟢  │
│  [████████████████████░░░░]   ROI: +48%      │
│                                              │
│  Minden 100 Ft kifizetett bérre              │
│  148 Ft normatíva érkezik vissza az államtól.│
└──────────────────────────────────────────────┘
```

A "Minden 100 Ft…" szöveges sor adja az igazi érthetőséget. A nyers szám önmagában nem sokat mond.

---

### 5/D-5 – Sikerdíj Progress Bar

```
Szept  Okt   Nov   Dec   Jan   Febr  Márc  Ápr   Máj   Jún
[█]   [█]   [█]   [█]   [░]   [░]   [░]   [░]   [░]   [░]
8.2k  7.9k  8.4k  8.1k   —     —     —     —     —     —

Eddig: 32.600 Ft  |  Ha befejezi: ≈ 82.000 Ft  |  Kifiz.: 2026. jún. 30.

ℹ️ Sikeres záróvizsga után, egy összegben. Sikertelen vizsgánál elvész.
```

**Implementáció:** 10 db kis `div` box (szept–jún), teljesített = zöld, jövő = szürke.

---

### 5/D-6 – What-if Eredmény Kontextussal

```
Jelenlegi:              Szimulált (+3 Asztalos):
┌──────────────────┐    ┌──────────────────────────┐
│  2.847.320 Ft/hó │→→→│  3.412.800 Ft/hó (+19,8%)│
│  [██████████░░]  │    │  [████████████░░]         │
└──────────────────┘    └──────────────────────────┘

Éves különbség: +6.785.760 Ft
Ez fedezi pl.: ~2,5 főállású oktató éves bérét
```

A "Ez fedezi" sor lefordítja a számot valós döntési kontextusba.

---

### 5/D-7 – Tooltip Rendszer (minden pénzügyi számon)

```
  138.629 Ft  ℹ️  ← hover →  Ö=1.200.000 × S=2.42 × M=0.857 / 12
```

**Implementáció:** CSS `position: absolute` tooltip JS `mouseenter` eseménnyel. A tooltip tartalma az API válasz `szorzo`, `onkoltsegi_alap`, `munkanap_arany` mezőiből generálódik.

---

## LÉPÉS 6 – Dokumentum-Architektúra (4. Pillér)

Új API végpontok a kötelező dokumentumok automatikus előállításához:

```python
# GET /normativa/student/{id}/igazolas?ev=2025&honap=11
# → PDF: "Igazolás szakmai gyakorlat teljesítéséről" (név, szakma, ledolgozott napok, összeg)

# GET /normativa/class/{class_id}/berjegyzek?ev=2025&honap=11
# → CSV/Excel: Bérjegyzék-alapanyag (hiányzás-levonásokkal, könyvelőnek)

# GET /normativa/class/{class_id}/kamarai-export?idoszak=2025/2026-1
# → XML: Kamarai adatszolgáltatás formátuma
```

Implementáció sorrendje:
1. CSV bérjegyzék (a meglévő `/export/payroll` bővítése, legegyszerűbb)
2. Kamarai XML export (struktúra egyeztetés után)
3. PDF igazolás (külön `document_service.py` bővítés, `reportlab` vagy `jinja2+weasyprint`)

---

## LÉPÉS 7 – Tesztelés és Ellenőrzés

### Manuális tesztek sorrendben:
1. Hozz létre egy szakmát az admin UI-n (pl. Hegesztő, szorzó: 2.42)
2. Rendelj egy diákhoz szakmát (`Student.szakma_torzs_id`)
3. Rögzíts jelenléteket az adott diákhoz – **különböző státuszokkal**: `dualis_nap`, `iskolai_nap`, `betegszabadsag`
4. Hívd meg: `GET /normativa/student/{id}?ev=2025&honap=11`
5. Ellenőrizd: a `betegszabadsag` napok **beleszámítanak** az M-be (normatíva szempontjából jelenlét!)
6. Ellenőrizd: az `iskolai_nap` napok **NEM számítanak** az M-be
7. Teszteld a ROI végpontot: `GET /normativa/student/{id}/roi?tanev=2025/2026`
8. Teszteld a what-if végpontot néhány dummy adattal
9. Töltsd le a CSV bérjegyzéket és nyisd meg Excelben

---

## A Két Korábbi Terv Különbségeinek Összefoglalója

| Témakör | `normativa_implementacios_terv.md` | `normatíva_kalkulátor_terv.md` | **Végleges döntés** |
|---|---|---|---|
| Számítási alap | T = Ö × S × M ✅ | T = Ö × S × M ✅ | Megegyezett |
| Adatmodell | 3 új tábla + Student FK | 3 új tábla + Student FK | Megegyezett |
| Munkanap granularitás | "napi pipa" → új mód | Óra/8 átváltás is opció | **D1 döntés kell** |
| What-if kimenet | Egyösszegű | Grafikon is | **D4 döntés kell** |
| Sikerdíj feltétel | Checkbox a diáknál | Külön tábla opció | **D3 döntés kell** |
| API útvonalak | `/api/normativa/...` | `/normativa/...` | `/normativa/...` (egyszerűbb) |
| Export formátum | CSV + XML | CSV + Excel | CSV elsőként, Excel később |
