# Normatíva és Költségkalkulátor - Lépésről Lépésre Implementációs Terv

Ez a dokumentum a CRM rendszer "Normatíva és Költségkalkulátor" moduljának pontos, lépésről-lépésre történő megvalósítását írja le.

## 🎯 Az Alapképlet: `T = Ö × S × M`
*   **Ö (Önköltségi alap)**: Aktuális éves önköltségi alapösszeg (pl. 1.200.000 Ft).
*   **S (Szakmaszorzó)**: A szakmához rendelt szorzó a törzsadatbázisból (pl. Szoftverfejlesztő: 1.2, Hegesztő: 2.42).
*   **M (Munkanap arány)**: A hónapban ténylegesen teljesített (jelenlét + igazolt távollétek, amik beleszámítanak) munkanapok aránya az elvárt munkanapokhoz képest.

---

## 🚀 Fejlesztési Lépések

### LÉPÉS 1: Adatmodell felépítése és bővítése (`backend/models.py`)
*Cél: Megteremteni a számításokhoz szükséges adatstruktúrát.*

1.  **Új tábla: `SzakmaTorzs` (Szakma-törzsadatbázis)**
    *   Mezők: `id`, `szakma_szam` (pl. 4-0611-16-Y), `megnevezes`, `agazat`, `szorzo` (Numeric), `onkoltsegi_alap` (Integer), `aktiv` (Boolean).
    *   *Ez az adminon szerkeszthető lesz.*
2.  **Új tábla: `NormativaKonfig` (Éves/Globális beállítások)**
    *   Mezők: `id`, `tanev_nev`, `onkoltsegi_alap_alapertelmezett`, `sikerdij_szazalek` (default 20.0), `aktiv`.
3.  **Új tábla: `KoltsegTetel` (Egyéb költségek nyilvántartása)**
    *   Mezők: `id`, `osztaly_id`, `diak_id` (opcionális), `idoszak` (pl. 2025-09), `tetel_nev`, `osszeg`, `kategoria`.
4.  **Meglévő `Student` modell bővítése:**
    *   Adjunk hozzá egy `szakma_torzs_id` (ForeignKey) mezőt.
5.  **Meglévő `Attendance` modell bővítése:**
    *   A `statusz` bővítése: `betegszabadsag`, `szunet`, `munkaszuneti_nap`. (Figyelem: A jelenlétnek le kell tudnia kezelni a *napokat*, nem csak az órákat).

### LÉPÉS 2: Adatcsere Sémák elkészítése (`backend/schemas.py`)
*Cél: Biztonságos adatkommunikáció az API-n keresztül.*

1.  Készítsünk Pydantic sémákat a `SzakmaTorzs`-höz (Create, Update, Response).
2.  Készítsünk sémákat a kalkulátor kimenetéhez (pl. `NormativaHaviResponse`, `SikerdijResponse`, `WhatIfRequest`, `WhatIfResponse`).

### LÉPÉS 3: A Kalkulátor Motor (Service) elkészítése (`backend/normativa_service.py`)
*Cél: Egy független, tesztelhető modul létrehozása az üzleti logikának.*

Hozzuk létre a `NormativaService` osztályt a következő metódusokkal:
1.  **`get_munkanap_arany(diak_id, ev, honap)`**:
    *   Lekéri a naptárból az adott hónap elvárt munkanapjait.
    *   Lekéri az `Attendance` táblából az igazolt jelenléteket/betegszabadságokat.
    *   Visszaadja az `M` (Munkanap arány) értékét (0.0 - 1.0 között).
2.  **`kalkulal_havi(diak_id, ev, honap)`**:
    *   Lekéri az `Ö` és `S` értékeket a diákhoz kötött `SzakmaTorzs`-ből.
    *   Lefuttatja a `T = Ö × S × M` képletet (ahol T az *éves* összeg).
    *   Kiszámolja a havi összeget (`T / 12`).
    *   Kiszámolja az adókedvezményt (duális képzésnél a normatíva 100%-a).
3.  **`kalkulal_eves_prognozis(diak_id, tanev)`**:
    *   Várható éves keretösszeg számítása a múltbeli tényadatok és a jövőbeli (1.0-ás `M`-mel feltételezett) adatok alapján.
4.  **`sikerdij_celtartalek(diak_id)`**:
    *   Virtuális számláló: Az eddig felhalmozott normatíva `X` százaléka (pl. 20%), amit vizsga után kaphatnak meg.
5.  **`what_if_szimulator(tervezett_diakok_lista)`**:
    *   Szimulációs metódus. Paraméterként kap egy listát (milyen szakmákból hány új diákot terveznek felvenni), és visszaadja a várható havi és éves cash-flow növekedést.

### LÉPÉS 4: API Végpontok (Integráció) (`backend/main.py`)
*Cél: A motor elérhetővé tétele a frontend számára.*

1.  **Szakmatörzs CRUD:** `GET, POST, PUT /admin/szakmak/`
2.  **Kalkulátor Végpontok:**
    *   `GET /api/normativa/diak/{id}/havi?ev=2025&honap=09` (Havi adókedvezmény/normatíva)
    *   `GET /api/normativa/diak/{id}/eves` (Éves prognózis + Sikerdíj számláló)
    *   `POST /api/normativa/what-if` (What-if szimulátor indítása)
3.  **Jelenlét egyszerűsített felvitele:**
    *   `POST /api/attendance/napi-pipa` (Egyszerű "jelen volt" rögzítés egész osztályra).

### LÉPÉS 5: Frontend és UI Fejlesztés (`admin_dashboard.html`, `script.js`)
*Cél: Intuitív, vezetőbarát felület biztosítása.*

1.  **Szakma-törzsadatbázis Szerkesztő (Admin nézet)**
    *   Egy táblázatos felület az új szakmák, szorzók és önköltségi alapok beállítására.
2.  **Egyszerűsített Jelenléti Naptár (Mentor/Oktató nézet)**
    *   Egy "pipálós" naptár nézet, ahol a mentorok gyorsan rögzíthetik a diákok havi munkanapjait.
3.  **Diák Adatlap "Pénzügyi Fül"**
    *   A diák modaljába (vagy részletező oldalára) egy új tab.
    *   Mutatja: Generált havi adókedvezmény, Éves várható keret, **Sikerdíj-céltartalék** folyamatjelzője.
4.  **Vezetői Dashboard (Aggregált nézet & What-if)**
    *   Kártyák, amik mutatják a cég teljes havi adókedvezmény-keretét.
    *   **What-if szimulátor panel:** Egy doboz, ahol meg lehet adni: "+3 Asztalos, +2 Hegesztő". Gombnyomásra frissíti a várható pénzügyi mutatókat (Milyen lesz a cash-flow szeptembertől?).
5.  **Sikerdíj Értesítő (Frontend logika)**
    *   Vizsgaidőszak közeledtével vizuális jelzés (pl. sárga badge), hogy "X Ft sikerdíj várható a sikeres vizsgák után".

### LÉPÉS 6: Export Modul (Könyvelési kimenet)
*Cél: Összekötni a rendszert a valós pénzügyi szoftverekkel.*

1.  Bővítsük a meglévő CSV exportot (vagy hozzunk létre XML exportot).
2.  Tartalma: Diák neve, Szakmaszám, Havi ledolgozott napok, Kiszámolt normatíva, Érvényesíthető adókedvezmény.
3.  Formátum legyen kompatibilis a bérszámfejtő rendszerek (pl. 08-as bevallás) adatigényeivel.

---

## ❓ Fontos Tisztázandó Kérdések (Döntési Pontok)
*Mielőtt az egyes lépéseket programozni kezdjük, ezeket véglegesíteni kell:*

1.  **Munkanap vs Óra:** A jelenlegi `Attendance` órákban számol. Átállunk napi pipálásra a duálisnál (1 pipa = 1 munkanap), vagy továbbra is órákat osztunk vissza napokká (pl. napi 8 óra = 1 munkanap)?
2.  **Munkaszüneti napok:** Honnan tudja a rendszer (pl. október 23., karácsony), hogy aznap nem kellett menni? (Adjon meg az admin éves munkaszüneti naptárat, vagy API-ból húzzuk Magyarország ünnepnapjait?)
3.  **Vizsga sikeressége:** A "Sikerdíj" jóváírásához kell egy flag a rendszerbe (pl. "Záróvizsga sikeres"). Hová kerüljön ez? (A `Student` adatlapra egy checkbox, vagy egy külön vizsga-esemény táblába?)
