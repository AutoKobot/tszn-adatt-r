# EduRegistrar ÁKK ⇄ InteractiveLearning - Adatbázis Integrációs Kézikönyv 🛠️

Ez a dokumentum a **Központi Iskolai Nyilvántartó** (EduRegistrar ÁKK / `tszn.onrender.com` / `iskolai adatbázis`) és az **Interaktív Oktatási Portál** (InteractiveLearning / `oktatas.click`) közötti kétirányú adatkapcsolat éles megvalósítási tervét tartalmazza. 

A két rendszer **közös Supabase PostgreSQL adatbázispéldányon** osztozik, így nincs szükség bonyolult API-szinkronizációra, a kommunikáció közvetlenül az SQL táblákon keresztül történik.

> [!IMPORTANT]
> **Kritikus Rendszer-audit Eredmény:** A két rendszer közötti mezőtípusok és státuszértékek eltérései komoly adatbázis-hibákhoz (pl. Foreign Key típusmismatchekhez) vagy hibás állami normatív számításokhoz vezetnének. Ezt a kézikönyvet úgy alkottuk meg, hogy ezeket a kritikus eltéréseket feloldja, így egy AI kódoló asszisztens hibátlanul képes megvalósítani a fejlesztést.

---

## 🗺️ Logikai Adatáramlási Térkép

```
1. DIÁKOK KISZOLGÁLÁSA (EduRegistrar -> InteractiveLearning)
[diakok] (SQLAlchemy Student) --(Drizzle DBRead)--> [users] (InteractiveLearning diák fiók)
- Kulcs: 'oktatasi_azonosito' (11 jegyű String) mint 'username'

2. JELENLÉT VISSZACSATORNÁZÁS (InteractiveLearning -> EduRegistrar)
[attendance] (Drizzle) --(Átfordítás & ID Keresés)--> [jelenlet] (SQLAlchemy Attendance)
- Státusz leképezés: 'present'/'late' -> 'jelen', 'excused' -> 'igazolt_hianyzas', 'absent' -> 'igazolatlan_hianyzas'

3. ÉRDEMJEGY VISSZACSATORNÁZÁS (InteractiveLearning -> EduRegistrar)
[practical_grades] (Drizzle) --(Küszöb-konverzió 1-5)--> [kulso_jegyek] (SQLAlchemy ExternalGrade)
- Érték leképezés: 0-100% kvízpontszám -> 1-5 érdemjegy a tanulmányi átlag megőrzéséért
```

---

## 🌐 Kréta mint Elsődleges Forrás (SSOT) és Automatikus Diák-Provinzionálás

A két rendszer integrációjának egyik legfontosabb alapelve, hogy az **EduRegistrar ÁKK a kizárólagos elsődleges adatbeviteli felület (Single Source of Truth - SSOT)**. 

### Az adatbevitel és szinkronizáció folyamata:
1.  **Adatbevitel Krétából:** A titkárság vagy az adminisztrátor az **EduRegistrar** felületén (a meglévő `excel_service.py` segítségével) feltölti a Krétából kiexportált tanulói és oktatói adatokat.
2.  **Központi rekordok létrejötte:** Ez az importálás automatikusan létrehozza a tanulókat a `diakok` táblában és az osztályokat az `osztalyok` táblában a megosztott PostgreSQL adatbázisban.
3.  **Közös adatbázis előnye:** Mivel az `InteractiveLearning` (`oktatas.click`) ugyanerre a Supabase PostgreSQL példányra kapcsolódik, a Kréta adatok bevitele után az új diákok és osztályok azonnal, valós időben elérhetővé válnak az oktatási portál számára is.

---

## 🔄 Automatikus Felhasználói Fiók Generálás (Provisioning) a Portál oldalon

Annak érdekében, hogy az adminisztrátoroknak ne kelljen manuálisan felhasználói fiókokat regisztrálniuk az oktatási portálon, az `InteractiveLearning` backendnek **automatikusan elő kell állítania a diákok tanulói fiókjait** a központi `diakok` tábla adatai alapján.

Az AI fejlesztőnek az alábbi **két párhuzamos módszert** kell megvalósítania az Express backend oldalon:

### ⚙️ A) Just-In-Time (JIT) Provinzionálás a portál bejelentkezésekor
Amikor egy diák első alkalommal próbál bejelentkezni az `InteractiveLearning` portálra a 11 jegyű OM azonosítójával (mint felhasználónévvel) és az alapértelmezett jelszavával:

1.  A bejelentkezési útvonal (`server/routes/auth.ts` -> `/login`) lekérdezi a helyi `users` táblát a felhasználónév alapján.
2.  **Ha a diák még nem létezik a helyi `users` táblában:**
    *   Lekérdezi a közös adatbázis `diakok` tábláját a megadott `oktatasi_azonosito` (username) alapján.
    *   **Ha megtalálja a tanulót a `diakok` között:** automatikusan beszúr egy új rekordot a helyi `users` táblába az alábbi leképezéssel:
        *   `id`: `"student_" + student.oktatasi_azonosito` (egyedi azonosító a portálon)
        *   `username`: `student.oktatasi_azonosito` (11 jegyű OM azonosító)
        *   `password`: Hashed alapértelmezett jelszó (pl: `change_me_promptly`)
        *   `email`: `student.email` (ha nincs megadva, akkor `username@iskola.hu` generálása)
        *   `firstName`: A `student.nev` szétválasztásával kapott utónév (pl: "Molnár Ákos" -> "Ákos")
        *   `lastName`: A `student.nev` szétválasztásával kapott vezetéknév (pl: "Molnár Ákos" -> "Molnár")
        *   `role`: `"student"`
        *   `schoolId`: `student.iskola_id`
        *   `classId`: `student.osztaly_id`
        *   `xp`: `0`
    *   A fiók sikeres automatikus létrehozása után a bejelentkezés zökkenőmentesen folytatódik (a diák azonnal beléphet).
    *   **Ha a diák nem szerepel a `diakok` táblában sem:** A rendszer elutasítja a bejelentkezést ("A diák még nincs rögzítve a központi Krétában!").

### ⚙️ B) Tömeges Szinkronizációs Gomb az Iskolai Adminok számára
Az `InteractiveLearning` admin felületén az iskolai adminisztrátorok számára elérhetővé kell tenni egy **"Diákok szinkronizálása a központi Krétából"** gombot, amely az alábbi logikát futtatja le a háttérben:

1.  Lekéri az összes diákot a `diakok` táblából, akik az adott iskola azonosítójához (`schoolId`) tartoznak.
2.  Minden diákra végigfut:
    *   Ha a diák `oktatasi_azonosito`-ja alapján már van fiók a `users` táblában, akkor frissíti az osztály azonosítóját (`classId`), vezetéknevét és keresztnevét a legfrissebb Kréta adatok alapján (adathelyreállítás).
    *   Ha nem létezik, automatikusan létrehozza a fiókot a JIT-nél leírt leképezés alapján.

---

## 🗂️ Lépésről Lépésre Fejlesztési Útmutató az AI Számára

### 1. Lépés: Adatbázis sémák frissítése és Multi-Tenancy (`models.py`)
**Módosítandó fájl:** [models.py](file:///e:/Antigravity_projektek/iskolai%20adatb%C3%A1zis/backend/models.py)

Vezesd be az `iskolak` modellt, és minden alapvető entitáshoz csatold az `iskola_id` idegen kulcsot.

#### A végrehajtandó kódmódosítás:
```python
# 1. Helyezd el a School modellt a User osztály elé:
class School(Base):
    __tablename__ = "iskolak"
    id = Column(Integer, primary_key=True, index=True)
    name = Column("nev", String(255), nullable=False)
    api_key = Column("api_key", String(255), unique=True)
    created_at = Column("created_at", TIMESTAMP, default=datetime.datetime.utcnow)

# 2. Add hozzá az iskola_id ForeignKey-t a meglévő táblákhoz:
# User (felhasznalok)
class User(Base):
    __tablename__ = "felhasznalok"
    # ...
    iskola_id = Column("iskola_id", Integer, ForeignKey("iskolak.id"), nullable=True)

# Student (diakok)
class Student(Base):
    __tablename__ = "diakok"
    # ...
    iskola_id = Column("iskola_id", Integer, ForeignKey("iskolak.id"), nullable=False, index=True)

# ClassRoom (osztalyok)
class ClassRoom(Base):
    __tablename__ = "osztalyok"
    # ...
    iskola_id = Column("iskola_id", Integer, ForeignKey("iskolak.id"), nullable=False, index=True)

# Instructor (oktatok)
class Instructor(Base):
    __tablename__ = "oktatok"
    # ...
    iskola_id = Column("iskola_id", Integer, ForeignKey("iskolak.id"), nullable=False, index=True)

# ExternalGrade (kulso_jegyek)
class ExternalGrade(Base):
    __tablename__ = "kulso_jegyek"
    # ...
    iskola_id = Column("iskola_id", Integer, ForeignKey("iskolak.id"), nullable=False, index=True)

# Attendance (jelenlet)
class Attendance(Base):
    __tablename__ = "jelenlet"
    # ...
    iskola_id = Column("iskola_id", Integer, ForeignKey("iskolak.id"), nullable=False, index=True)
```

---

### 2. Lépés: Automatikus sémamigráció (`main.py`)
**Módosítandó fájl:** [main.py](file:///e:/Antigravity_projektek/iskolai%20adatb%C3%A1zis/backend/main.py)

A FastAPI indításakor (`lifespan` aszinkron kontextus) hajtsd végre a DDL migrációkat a táblák fizikai létrehozásához és módosításához a Supabase PostgreSQL adatbázisban.

#### A `lifespan` aszinkron kontextus kiegészítése:
```python
        # Multi-tenancy sémamigráció (DDL)
        from sqlalchemy import text
        try:
            # 1. Iskolák tábla létrehozása
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS public.iskolak (
                    id SERIAL PRIMARY KEY,
                    nev VARCHAR(255) NOT NULL,
                    api_key VARCHAR(255) UNIQUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
                );
            """))
            db.commit()

            # 2. Iskola idegen kulcsok hozzáadása a meglévő táblákhoz
            db.execute(text("ALTER TABLE public.felhasznalok ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.iskolak(id);"))
            db.execute(text("ALTER TABLE public.diakok ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.iskolak(id);"))
            db.execute(text("ALTER TABLE public.osztalyok ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.iskolak(id);"))
            db.execute(text("ALTER TABLE public.oktatok ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.iskolak(id);"))
            db.execute(text("ALTER TABLE public.kulso_jegyek ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.iskolak(id);"))
            db.execute(text("ALTER TABLE public.jelenlet ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.iskolak(id);"))
            db.commit()
            print("[MIGRÁCIÓ] Multi-tenancy oszlopok és táblák sikeresen létrehozva.")
        except Exception as e:
            print(f"[MIGRÁCIÓ HIBA] {e}")
            db.rollback()
```

---

### 3. Lépés: Pydantic validációs sémák kiegészítése (`schemas.py`)
**Módosítandó fájl:** [schemas.py](file:///e:/Antigravity_projektek/iskolai%20adatb%C3%A1zis/backend/schemas.py)

#### Elvégzendő módosítások:
1. Add hozzá a `School` sémákat a fájl elejéhez:
```python
class SchoolBase(BaseModel):
    name: str
    api_key: Optional[str] = None

class SchoolCreate(SchoolBase):
    pass

class School(SchoolBase):
    id: int
    created_at: datetime
    model_config = {"from_attributes": True}
```

2. Bővítsd a meglévő sémákat az `iskola_id` mezővel:
*   `StudentBase` -> `iskola_id: int`
*   `StudentUpdate` -> `iskola_id: Optional[int] = None`
*   `ClassRoomBase` -> `iskola_id: int`
*   `ClassRoomUpdate` -> `iskola_id: Optional[int] = None`
*   `InstructorBase` -> `iskola_id: int`
*   `GradeCreate` -> `iskola_id: int`
*   `AttendanceBase` -> `iskola_id: int`
*   `UserBase` -> `iskola_id: Optional[int] = None`

---

### 4. Lépés: JWT Token és Login hitelesítés (`auth.py` és `main.py`)
Biztosítani kell, hogy a rendszer a hitelesítési tokenben (`access_token`) és annak dekódolásában is átadja és értelmezze a felhasználó `iskola_id` értékét.

#### A) JWT Dekódolás (`backend/auth.py` -> `get_current_user`):
```python
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Érvénytelen hitelesítési adatok",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        
        # Supabase RLS kompatibilitás
        app_metadata = payload.get("app_metadata", {})
        school_id: Optional[int] = app_metadata.get("school_id") if isinstance(app_metadata, dict) else None
        if school_id is None:
            school_id = payload.get("school_id") # Közvetlen fallback
            
        if username is None:
            raise credentials_exception
        return {"username": username, "role": role, "school_id": school_id}
    except JWTError:
        raise credentials_exception
```

#### B) Login válasz (`backend/main.py` -> `/login`):
```python
@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Hibás felhasználónév vagy jelszó")
    
    access_token = auth.create_access_token(
        data={
            "sub": user.username, 
            "role": user.role,
            "school_id": user.iskola_id,
            "app_metadata": {
                "school_id": user.iskola_id
            }
        }
    )
    return {"access_token": access_token, "token_type": "bearer"}
```

---

### 5. Lépés: API szintű Multi-Tenant elszigetelés (`main.py`)
Minden lekérdező és író végponton érvényesíteni kell az `iskola_id` szerinti szűrést, így az iskolák nem láthatják egymás diákjait, osztályait vagy jegyeit.

#### Végpontok módosítása (Példák):
*   **Diákok lekérése (GET `/students/`):**
    ```python
    @app.get("/students/", response_model=list[schemas.Student])
    def read_students(skip: int = 0, limit: int = 100, class_id: Optional[int] = None, 
                      db: Session = Depends(get_db), current_user: dict = Depends(auth.get_current_user)):
        query = db.query(models.Student)
        if current_user["role"] != "admin" or current_user["school_id"] is not None:
            query = query.filter(models.Student.iskola_id == current_user["school_id"])
        
        if class_id:
            query = query.filter(models.Student.osztaly_id == class_id)
        return query.offset(skip).limit(limit).all()
    ```
*   **Diák létrehozása (POST `/students/`):**
    ```python
    @app.post("/students/", response_model=schemas.Student)
    def create_student(student: schemas.StudentCreate, db: Session = Depends(get_db), 
                       current_user: dict = Depends(auth.get_current_user)):
        student_data = student.dict()
        if current_user["school_id"] is not None:
            student_data["iskola_id"] = current_user["school_id"]
            
        db_student = models.Student(**student_data)
        db.add(db_student)
        db.commit()
        db.refresh(db_student)
        return db_student
    ```

---

## ⚠️ KRITIKUS INTEGRÁCIÓS CSAPDÁK ÉS KÓDOLÁSI SZABÁLYOK AZ AI SZÁMÁRA

### 🚨 1. Csapda: A 'diak_id' típusbeli eltérése (Foreign Key Hiba!)
*   **A hiba:** Az `InteractiveLearning` (`oktatas.click`) adatbázisában a diák azonosítója a `users.id` táblában egy String (pl: `student_72345678901`), vagy a bejelentkezési név `users.username` (11 jegyű String, pl: `72345678901`). Ezzel szemben az `EduRegistrar` adatbázisában a `diakok.id` egy **Integer** (pl: `12`).
*   **A katasztrófa:** Ha az `InteractiveLearning` közvetlenül a `users.id` vagy `username` értéket próbálja meg beilleszteni a `jelenlet.diak_id` vagy `kulso_jegyek.diak_id` oszlopokba, a PostgreSQL azonnal `foreign key constraint` hibát dob és megszakítja a tranzakciót.
*   **A Megoldás (Kötelező fejlesztési lépés az Express backend oldalon):**
    Mielőtt a Drizzle beszúrná a jelenléti adatot vagy érdemjegyet, le kell kérnie a `diakok` táblából az integer belső `id`-t a diák 11 jegyű `oktatasi_azonosito`-ja alapján:
    ```typescript
    // Drizzle ORM kódrészlet az Express backendbe (pl. teacher.ts / practical-grades.ts):
    const studentRecord = await db.select({ id: diakok.id })
      .from(diakok)
      .where(eq(diakok.oktatasi_azonosito, studentUsername))
      .limit(1);
      
    if (studentRecord.length === 0) {
      throw new Error(`A diák nem található a központi diakok táblában: ${studentUsername}`);
    }
    
    const dbStudentId = studentRecord[0].id; // Ez az Integer ID!
    
    // Most már biztonságosan beszúrható a jegy vagy jelenlét a megosztott PostgreSQL-be:
    await db.insert(jelenlet).values({
      diak_id: dbStudentId, // INTEGER!
      iskola_id: teacher.schoolId,
      statusz: mappedStatus,
      // ... egyéb mezők
    });
    ```

### 🚨 2. Csapda: Érdemjegy és Kvízeredmény Eltérés (Átlag-torzulási Hiba!)
*   **A hiba:** A diákok kvízeredményei 0 és 100 közötti pontszámok (százalékok), míg az `EduRegistrar` tanulmányi átlagszámítása (`main.py` -> `/stats` végpont) a klasszikus magyar **1-5 érdemjegyeket** várja el.
*   **A katasztrófa:** Ha a portál beír egy 85%-os tesztet `85` értékkel a `kulso_jegyek.ertek` oszlopba, a diák súlyozott tanulmányi átlaga `85.0` lesz, ami teljesen tönkreteszi a megfelelőségi jelentést és az ösztöndíj-kalkulációt.
*   **A Megoldás:** Az érdemjegy visszamentése előtt a kvízeredményt át kell számítani a tanár által beállított osztályküszöbök alapján 1-5 közötti egész számmá, és ezt az átváltott érdemjegyet kell beírni az `ExternalGrade` táblába.

### 🚨 3. Csapda: Státuszkódok leképezése (Normatíva-vesztés!)
*   **A hiba:** Az `InteractiveLearning` kliens oldalon a jelenléti státuszok az angol szakkifejezéseket használják: `'present'`, `'absent'`, `'late'`, `'excused'`. Az `EduRegistrar` normatíva motorja viszont szigorúan a `'jelen'`, `'igazolt_hianyzas'`, `'igazolatlan_hianyzas'` státuszokat értelmezi és számolja el jogosult gyakorlati napként.
*   **A katasztrófa:** Ha a portál beszúr egy `'present'` státuszt, a normatíva kalkulátor kihagyja a számításból, így a rendszer $M=0$-t fog számolni, és a cég nem kapja meg a havi normatívát az adott diák után.
*   **A Megoldás (Munkaszabály):** Az Express backendnek a mentés előtt le kell képeznie a státuszkódokat a központi rendszer belső formátumára az alábbi táblázat szerint:

| InteractiveLearning Státusz | Leképezett EduRegistrar Státusz | Normatíva szempontból jogosult? |
| :--- | :--- | :--- |
| **`present`** | **`jelen`** | **Igen** (Jogosult képzési nap) |
| **`late`** | **`jelen`** | **Igen** (Jogosult képzési nap) |
| **`excused`** | **`igazolt_hianyzas`** | **Nem** (Hiányzásnak számít) |
| **`absent`** | **`igazolatlan_hianyzas`** | **Nem** (Ösztöndíj-levonással jár!) |

---

## 🔒 Adat-hozzáférési Mátrix és Biztonsági Hozzáférés-szabályozás

Mivel mindkét platform **ugyanarra a közös éles Supabase PostgreSQL** adatbázisra csatlakozik, rendkívül fontos tisztázni a jogosultsági és olvasási határokat. A **Minimális Adat Elvének (Principle of Least Privilege)** értelmében az oktatási portálnak (`InteractiveLearning`) kizárólag a működéséhez minimálisan szükséges adatokhoz szabad hozzáférést biztosítani. Ez garantálja, hogy a portál esetleges biztonsági incidense (pl. egy XSS vagy backend sérülékenység) esetén se szivároghassanak ki bizalmas személyes és pénzügyi adatok.

### 📊 Adat-hozzáférési Jogosultsági Mátrix

| Tábla Megnevezése | EduRegistrar ÁKK Hozzáférés | InteractiveLearning Hozzáférés | Részletek és Korlátozások |
| :--- | :--- | :--- | :--- |
| **`iskolak`** | Írás / Olvasás (Teljes) | Olvasás (Csak a saját iskola) | Az intézményi alapadatok azonosítására. |
| **`diakok`** | Írás / Olvasás (Teljes) | **Szigorúan Korlátozott Olvasás** | Lásd a lenti Column-Level Security korlátozást! |
| **`osztalyok`** | Írás / Olvasás (Teljes) | Olvasás (Csak a saját osztályok) | Diákok csoportosításához a portálon. |
| **`oktatok`** | Írás / Olvasás (Teljes) | Olvasás (Csak a saját oktatók) | A tanári fiókok szinkronizálásához. |
| **`jelenlet`** | Írás / Olvasás (Teljes) | Írás / Olvasás (Saját diákok) | A portál generálja a jelenléti bejegyzéseket. |
| **`kulso_jegyek`** | Írás / Olvasás (Teljes) | Írás / Olvasás (Saját diákok) | A portál írja be a kvíz érdemjegyeket. |
| **`felhasznalok`** | Írás / Olvasás (Teljes) | **NINCS ELÉRÉS (Tiltott)** | A központi rendszer belső admin/oktatói fiókjai. |
| **`partnerek`** | Írás / Olvasás (Teljes) | **NINCS ELÉRÉS (Tiltott)** | A duális képzőhelyek céges adatai. |
| **`szakiranyu_szerzodesek`**| Írás / Olvasás (Teljes) | **NINCS ELÉRÉS (Tiltott)** | A bizalmas tanulói munkaszerződések. |
| **`koltseg_tetelek`** | Írás / Olvasás (Teljes) | **NINCS ELÉRÉS (Tiltott)** | A belső ROI számításhoz használt működési költségek. |
| **`tanev_rendje`** | Írás / Olvasás (Teljes) | **NINCS ELÉRÉS (Tiltott)** | A központi naptári konfiguráció. |

---

### 🛡️ Oszlopszintű Biztonság (Column-Level Security) a `diakok` táblán

Az `InteractiveLearning` portálnak **semmilyen körülmények között** nem szabad olvasnia a diákok személyes, egészségügyi és pénzügyi adatait.

#### ⛔ Tiltott mezők a portál számára:
*   `bankszamlaszam` (Bankszámlaszám)
*   `tajszam` (TAJ szám)
*   `adoazonosito` (Adóazonosító)
*   `szuletesi_hely`, `szuletesi_datum` (Születési adatok)
*   `anyja_neve` (Születési anyja neve)
*   `telefon` (Személyes telefonszám)
*   `lakhely`, `ertesitesi_cim` (Lakcím adatok)
*   `szerzodes_kezdet`, `szerzodes_vege` (Duális szerződés dátumai)
*   `megjegyzesek` / `metadata_json` (Szenzitív adminisztratív bejegyzések)

#### ✅ Engedélyezett biztonságos mezők a portál számára:
*   `id` (Belső adatbázis Integer ID)
*   `oktatasi_azonosito` (11 jegyű OM azonosító - a bejelentkezéshez)
*   `nev` (Diák neve - a személyre szabott felülethez)
*   `osztaly_id` (Osztály azonosítója)
*   `iskola_id` (Iskola azonosítója)

---

### 🛠️ Megvalósítási Javaslat az AI-nak a szivárgások ellen:

#### 1. SQL szintű védelem (Biztonsági Nézet / View):
Ahelyett, hogy a portálnak közvetlen hozzáférést adnánk a `diakok` táblához, a Supabase adatbázisban hozzunk létre egy biztonságos SQL Nézetet, és a portál drizzle sémájában ezt a nézetet képezzük le táblaként:

```sql
-- Biztonságos nézet létrehozása a Supabase SQL Editorban
CREATE OR REPLACE VIEW public.diakok_oktatas_portal AS
SELECT 
    id,
    oktatasi_azonosito,
    nev,
    osztaly_id,
    iskola_id
FROM public.diakok;

-- Hozzáférés biztosítása a portál adatbázis-szerepköre számára
GRANT SELECT ON public.diakok_oktatas_portal TO authenticated;
```

#### 2. Kliens oldali (Drizzle) korlátozás:
Az `InteractiveLearning` drizzle sémájában (`shared/schema.ts`) a `diakok` tábla leképzésekor **kizárólag** a biztonságos mezőket szabad definiálni (a szenzitív mezőket ki kell hagyni a TypeScript definícióból is), így a Drizzle ORM fizikailag sem tudja lekérdezni azokat:

```typescript
// Shared/schema.ts kód az Express backendhez:
export const diakok = pgTable("diakok_oktatas_portal", {
  id: integer("id").primaryKey(),
  oktatasi_azonosito: varchar("oktatasi_azonosito", { length: 11 }).notNull(),
  nev: varchar("nev", { length: 255 }).notNull(),
  osztaly_id: integer("osztaly_id"),
  iskola_id: integer("iskola_id"),
});
```

---

## 🚀 Validálási lépések a megvalósítás után

1.  **Futtasd a diagnosztikát:** Futtasd le a `check_system_health.py` szkriptet, hogy lásd, a migráció sikeres volt-e.
2.  **JWT Tesztelés:** Generálj egy tokent a `/login` végponton egy iskolai felhasználóval, dekódold (pl. jwt.io portálon) és győződj meg arról, hogy a `school_id` szerepel az `app_metadata` alatt.
3.  **RLS Adat-szigetelési teszt:** Hozz létre két tesztiskolát. Az egyik iskola felhasználójával felvitt diákok nem jelenhetnek meg a másik iskola felületén.
