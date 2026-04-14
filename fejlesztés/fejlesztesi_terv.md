# EduRegistrar Fejlesztési Terv 🚀

Ebben a dokumentumban követjük nyomon a rendszer további fejlesztési lépéseit, szétválasztva az oktatói és adminisztrációs feladatokat.

---

## 📅 Ütemterv és Fázisok

### 1. FÁZIS: Jelenlét és Alapadatok (Március vége - Április eleje)
*Cél: Megbízható adatforrás létrehozása a későbbi kalkulációkhoz.*

- [ ] **Jelenléti Napló (Oktató):** Napi jelenlét rögzítése diák és dátum alapján.
- [ ] **Egészségügyi papírok (Admin):** Orvosi alkalmassági vizsgák lejáratának rögzítése és követése.
- [ ] **Diák adatlap bővítése:** Bankszámlaszám, tajszám, adóazonosító mezők hozzáadása.

### 2. FÁZIS: Értékelés és Haladás (Április közepe)
*Cél: A diákok szakmai fejlődésének dokumentálása.*

- [ ] **Érdemjegy Module (Oktató):** Elméleti és gyakorlati jegyek beírása.
- [ ] **Haladási Napló (Oktató):** Napi elvégzett szakmai feladatok rögzítése.
- [ ] **Vizsga eredmények (Admin):** Modulzáró és záróvizsgák adminisztrálása.

### 3. FÁZIS: Pénzügy és Riportok (Május eleje)
*Cél: A papírmunka automatizálása.*

- [ ] **Ösztöndíj kalkulátor (Admin):** Jelenléti adatokból havi kifizetési lista generálása.
- [ ] **Bérfeladó Export (Admin):** Kulcs-Soft barát Excel/CSV fájl előállítása partnercégenként.
- [ ] **Statisztikai Dashboard (Admin):** Grafikonok a hiányzásokról és érdemjegyekról osztályszinten.

---

## 📋 Funkciók Részletezése

### 👨‍🏫 OKTATÓI MODUL (Pedagógiai fázis)

| Funkció | Leírás | Státusz |
| :--- | :--- | :--- |
| **Digitális Jelenlét** | Napi szintű jelenléti rögzítés (Iskola/Cég) | ⏳ Tervezés alatt |
| **Jegybeírás** | 1-5 skálán szakmai jegyek és érdemjegyek rögzítése | ⏳ Tervezés alatt |
| **Üzenőfal** | Hirdetmények küldése a diákok számára | ⏳ Tervezés alatt |
| **Osztály nézet** | Állapot-dashboard az oktató saját osztályairól | ⏳ Tervezés alatt |

### 👔 ADMINISZTRÁCIÓS MODUL (Hivatali fázis)

| Funkció | Leírás | Státusz |
| :--- | :--- | :--- |
| **Bérfeladó Export** | Valós óraszám alapon generált havi elszámolás | ⏳ Tervezés alatt |
| **Compliance Követés** | Orvosi és munkavédelmi papírok lejárati figyelmeztetője | ✅ Részben kész |
| **Digitális Adattár** | Szkennelt szerződések és okiratok tárolása | ⏳ Tervezés alatt |
| **Rendszernapló** | Ki, mikor, mit módosított (GDPR) | ✅ Kész |

---

## 🛠 Technikai Teendők

1. **Adatbázis módosítások (`models.py`):**
   * `Jelenlet` tábla létrehozása (diak_id, datum, tipus, oraszam).
   * `ExternalGrade` bővítése vagy UI bekötése.
   * `User` és `Student` táblák mezőinek bővítése a hiányzó adatokkal.
2. **Backend Endpontok (`main.py`):**
   * Pénzügyi kalkulációs logika megírása.
   * Export modul (Excel/CSV generátor) elkészítése.
3. **Frontend Fejlesztés:**
   * Új naptár-nézet a jelenléthez.
   * Jegybeíró felület.
   * Admin dashboard grafikonok (Chart.js vagy hasonló).

---

> [!TIP]
> **Hogyan tovább?**
> Ezt a fájlt a `fejlesztés/` mappában találod. Folyamatosan frissítsük, ahogy haladunk előre a megvalósításban.
