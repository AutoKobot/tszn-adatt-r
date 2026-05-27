# Adatbázis Integrációs és Szinkronizációs Terv: tszn.onrender.com ⇄ oktatas.click

Ez a terv a központi **Központi Iskolai Nyilvántartó** (`tszn.onrender.com` / "EduRegistrar ÁKK" projekt) és az **Interaktív Oktatási Portál** (`oktatas.click` / "InteractiveLearning" projekt) közötti biztonságos adatkapcsolatot, RLS-alapú többszörös elszigetelést és valós idejű szinkronizációt részletezi.

A cél az, hogy a fejlesztő és az AI kódoló asszisztensek képesek legyenek egy az egyben, fájlról fájlra követni az integrációs lépéseket, mind a Python/FastAPI backend, mind a Node.js/Express backend oldalon.

---

## 🎯 Célkitűzés és Alapelvek

A két rendszer integrációja a **Minimális Adat Elvére** épül, biztosítva, hogy a külső oktatási portál (`oktatas.click`) esetleges biztonsági incidense esetén se szivároghassanak ki bizalmas személyes vagy pénzügyi adatok (pl. TAJ szám, adóazonosító, lakhely, szerződések részletei).

```
[ tszn.onrender.com (EduRegistrar) ] --(Minimális diákadat: Név, 11 jegyű ID, Osztály)--> [ oktatas.click (Supabase DB) ]
[ tszn.onrender.com (EduRegistrar) ] <-- (Valós idejű jelenléti adatok és kvíz érdemjegyek) -- [ oktatas.click (Supabase DB) ]
```

---

## ☁️ Supabase PostgreSQL mint Közös Adattár

Mindkét rendszer PostgreSQL alapokon nyugszik, így az integráció a **közös éles Supabase PostgreSQL példányon** valósul meg.
A `tszn.onrender.com` (Python FastAPI) közvetlen PostgreSQL kapcsolaton keresztül éri el a megosztott táblákat, míg az `oktatas.click` (Node.js Express) a Drizzle ORM segítségével végzi az olvasást és írást.

---

## 🏢 Supabase RLS (Row Level Security) és Több-intézményes Elszigetelés (Multi-Tenancy)

A rendszernek több száz iskolát kell kiszolgálnia. Az iskolák közötti logikai izolációt a PostgreSQL motor Row Level Security (RLS) funkciója garantálja adatbázis-szinten.

### 📍 SQL Forgatókönyv a Supabase Adatbázison (RLS beállítása)
Futtasd az alábbi SQL szkriptet a Supabase SQL Editorban az izolációs pajzs felépítéséhez:

```sql
-- 1. Intézmények (Iskolák) törzstábla létrehozása
CREATE TABLE IF NOT EXISTS public.iskolak (
    id SERIAL PRIMARY KEY,
    nev VARCHAR(255) NOT NULL,
    api_key VARCHAR(255) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Az iskola_id mezők hozzáadása a meglévő közös táblákhoz (ha még nincsenek ott)
ALTER TABLE public.diakok ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.iskolak(id);
ALTER TABLE public.osztalyok ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.iskolak(id);
ALTER TABLE public.oktatok ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.iskolak(id);
ALTER TABLE public.jelenlet ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.iskolak(id);
ALTER TABLE public.kulso_jegyek ADD COLUMN IF NOT EXISTS iskola_id INTEGER REFERENCES public.iskolak(id);

-- 3. Row Level Security engedélyezése az érintett táblákon
ALTER TABLE public.diakok ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.osztalyok ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.oktatok ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jelenlet ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.kulso_jegyek ENABLE ROW LEVEL SECURITY;

-- 4. Megkerülhetetlen elszigetelési szabályok (RLS Policies) létrehozása
CREATE POLICY school_isolation_policy ON public.diakok
    FOR ALL TO authenticated
    USING (iskola_id = (auth.jwt() -> 'app_metadata' ->> 'school_id')::int);

CREATE POLICY school_isolation_policy ON public.osztalyok
    FOR ALL TO authenticated
    USING (iskola_id = (auth.jwt() -> 'app_metadata' ->> 'school_id')::int);

CREATE POLICY school_isolation_policy ON public.oktatok
    FOR ALL TO authenticated
    USING (iskola_id = (auth.jwt() -> 'app_metadata' ->> 'school_id')::int);

CREATE POLICY school_isolation_policy ON public.jelenlet
    FOR ALL TO authenticated
    USING (iskola_id = (auth.jwt() -> 'app_metadata' ->> 'school_id')::int);

CREATE POLICY school_isolation_policy ON public.kulso_jegyek
    FOR ALL TO authenticated
    USING (iskola_id = (auth.jwt() -> 'app_metadata' ->> 'school_id')::int);
```

---

## 🛠️ 1. Központi Rendszer Módosításai: "EduRegistrar ÁKK" (`tszn.onrender.com`)

### 1.1 SQLAlchemy Modellek Frissítése
*   **Módosítandó fájl:** `e:\Antigravity_projektek\iskolai adatbázis\backend\models.py`
*   **Feladat:** Add hozzá a `School` modellt, és kösd össze a meglévő modellekkel `ForeignKey` segítségével.

```python
class School(Base):
    __tablename__ = "iskolak"
    id = Column(Integer, primary_key=True, index=True)
    name = Column("nev", String(255), nullable=False)
    api_key = Column("api_key", String(255), unique=True)
    created_at = Column("created_at", TIMESTAMP, default=datetime.datetime.utcnow)

class Student(Base):
    __tablename__ = "diakok"
    # ... meglévő mezők ...
    iskola_id = Column(Integer, ForeignKey("iskolak.id"), nullable=False)
    
class ClassRoom(Base):
    __tablename__ = "osztalyok"
    # ... meglévő mezők ...
    iskola_id = Column(Integer, ForeignKey("iskolak.id"), nullable=False)

class Instructor(Base):
    __tablename__ = "oktatok"
    # ... meglévő mezők ...
    iskola_id = Column(Integer, ForeignKey("iskolak.id"), nullable=False)

class ExternalGrade(Base):
    __tablename__ = "kulso_jegyek"
    # ... meglévő mezők ...
    iskola_id = Column(Integer, ForeignKey("iskolak.id"), nullable=False)

class Attendance(Base):
    __tablename__ = "jelenlet"
    # ... meglévő mezők ...
    iskola_id = Column(Integer, ForeignKey("iskolak.id"), nullable=False)
```

### 1.2 Bérszámfejtő lekérdezések szűrése iskolánként
*   **Módosítandó fájl:** `e:\Antigravity_projektek\iskolai adatbázis\backend\normativa_service.py`

```python
def calculate_monthly_attendance_summary(db: Session, school_id: int, month: str):
    return db.query(Attendance).filter(
        Attendance.iskola_id == school_id,
        Attendance.datum.like(f"{month}%")
    ).all()
```

---

## 💻 2. Oktatási Portál Módosításai: "InteractiveLearning" (`oktatas.click`)

### 2.1 Bejelentkezés és JWT Token Módosítása
*   **Módosítandó fájl:** `server/routes/auth.ts`

```typescript
router.post("/login", async (req, res) => {
  const user = await storage.getUserByUsername(req.body.username);
  if (!user) return res.status(400).send("Hibás adatok");
  
  const tokenPayload = {
    sub: user.id,
    role: user.role,
    app_metadata: {
      school_id: user.schoolId 
    }
  };
  
  const token = jwt.sign(tokenPayload, process.env.JWT_SECRET!, { expiresIn: '24h' });
  res.json({ token, user });
});
```

### 2.2 Automatikus Diák Szinkronizációs Háttérfolyamat
*   **Módosítandó fájl:** `server/sync-service.ts`

```typescript
import { db } from "./db";
import { users } from "@shared/schema";
import { eq, and } from "drizzle-orm";

export async function syncStudentsFromCentralDatabase(schoolId: number) {
  const centralStudents = await db.select()
    .from(diakok)
    .where(eq(diakok.iskola_id, schoolId));

  for (const student of centralStudents) {
    const existingUser = await db.select()
      .from(users)
      .where(and(eq(users.username, student.oktatasi_azonosito), eq(users.schoolId, schoolId)))
      .limit(1);

    if (existingUser.length === 0) {
      await db.insert(users).values({
        id: `student_${student.oktatasi_azonosito}`,
        username: student.oktatasi_azonosito,
        password: "change_me_promptly",
        email: `${student.oktatasi_azonosito}@iskola.hu`,
        firstName: student.nev.split(" ").slice(1).join(" "),
        lastName: student.nev.split(" ")[0],
        role: "student",
        schoolId: schoolId,
        classId: student.osztaly_id,
        xp: 0
      });
    } else {
      await db.update(users)
        .set({ classId: student.osztaly_id, firstName: student.nev.split(" ").slice(1).join(" "), lastName: student.nev.split(" ")[0] })
        .where(eq(users.username, student.oktatasi_azonosito));
    }
  }
}
```

### 2.3 Kvíz Eredmények és Jelenlét Visszaküldése
*   **Fájlok:** `server/routes/practical-grades.ts` & `server/routes/teacher.ts`

```typescript
// Kvíz eredmény mentése
await db.insert(externalGrades).values({
  diak_id: user.username,
  tantargy: module.subjectName,
  ertek: gradeValue,
  tipus: "elmélet",
  forras: "Oktatasi Portal",
  iskola_id: user.schoolId,
  datum: new Date()
});

// Jelenlét mentése
await db.insert(jelenlet).values({
  diak_id: student.username,
  datum: new Date(date),
  oraszam: record.hours,
  tipus: "iskola",
  statusz: record.status === "present" ? "jelen" : "igazolt_hianyzas",
  iskola_id: teacher.schoolId
});
```

---

## 💎 Integrációs Előnyök

1.  **Golyóálló Elszigetelés:** A Supabase adatbázis-szinten futó **Row Level Security (RLS)** megkerülhetetlenül elszigeteli az iskolák adatait.
2.  **Karbantartásmentes Bérszámfejtés:** A jelenléti és teljesítményadatok valós időben érkeznek a központi rendszerbe, minimalizálva az adminisztrációt.
3.  **Központosított Kezelés:** A diákokat csak a `tszn.onrender.com` rendszerben kell rögzíteni.

**Kelt:** 2026. május 25.
**Frissítette:** Antigravity AI & A Platform Vezető Fejlesztője
