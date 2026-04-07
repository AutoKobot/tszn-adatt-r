-- Tiszalöki Szakképzési ÁKK - Átfogó Adatbázis Séma
-- Dialektus: PostgreSQL

-- 1. EGYÉNI TÍPUSOK ÉS ENUMOK
-- ---------------------------------------------------------
CREATE TYPE tagozat_tipus AS ENUM ('nappali', 'felnőtt');
CREATE TYPE szerzodes_statusz AS ENUM ('aktív', 'felfüggesztett', 'lezárt', 'megszűnt');
CREATE TYPE forras_tipus AS ENUM ('Kréta', 'Belső', 'Importált');

-- 2. TÖRZSADATOK (Szakmák, Osztályok, Oktatók)
-- ---------------------------------------------------------
-- Szakmák táblája
CREATE TABLE szakmak (
    id SERIAL PRIMARY KEY,
    szakma_kod VARCHAR(20) UNIQUE NOT NULL, -- pl. 4 0713 04 07
    megnevezes VARCHAR(255) NOT NULL,
    agazat VARCHAR(100), -- pl. Informatika és távközlés
    leiras TEXT,
    metadata JSONB DEFAULT '{}' -- Speciális képzési követelmények
);

-- Osztályok táblája
CREATE TABLE osztalyok (
    id SERIAL PRIMARY KEY,
    megnevezes VARCHAR(50) NOT NULL UNIQUE, -- pl. 11.A, F-2024
    tanev VARCHAR(20), -- pl. 2023/2024
    szakma_id INT REFERENCES szakmak(id),
    metadata JSONB DEFAULT '{}'
);

-- Oktatók táblája
CREATE TABLE oktatok (
    id SERIAL PRIMARY KEY,
    nev VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    telefon VARCHAR(20),
    szakterulet VARCHAR(255),
    metadata JSONB DEFAULT '{}' -- pl. végzettségek, minősítések
);

-- 3. SZEMÉLYI ADATOK (Diákok, Szülők)
-- ---------------------------------------------------------
-- Diákok táblája
CREATE TABLE diakok (
    id SERIAL PRIMARY KEY,
    oktatasi_azonosito CHAR(11) UNIQUE,
    nev VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    telefon VARCHAR(20),
    lakhely TEXT,
    ertesitesi_cim TEXT,
    tagozat tagozat_tipus DEFAULT 'nappali',
    osztaly_id INT REFERENCES osztalyok(id),
    letrehozva TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    megjegyzesek JSONB DEFAULT '{}' -- Minden egyéb rugalmas adat (allergia, kedvezmények)
);

-- Gondviselők (Szülők) táblája
CREATE TABLE gondviselok (
    id SERIAL PRIMARY KEY,
    diak_id INT NOT NULL REFERENCES diakok(id) ON DELETE CASCADE,
    nev VARCHAR(255) NOT NULL,
    telefon VARCHAR(20),
    email VARCHAR(255),
    kapcsolat_tipusa VARCHAR(50), -- apa, anya, gyám
    metadata JSONB DEFAULT '{}'
);

-- 4. SZAKIRÁNYÚ OKTATÁSI SZERZŐDÉSEK (ÁKK Duális képzés)
-- ---------------------------------------------------------
-- Gazdálkodó szervezetek (Partnervállalatok)
CREATE TABLE partnerek (
    id SERIAL PRIMARY KEY,
    cegnev VARCHAR(255) NOT NULL,
    adoszam VARCHAR(13) UNIQUE,
    szekhely TEXT,
    kapcsolattarto_neve VARCHAR(255),
    email VARCHAR(255),
    metadata JSONB DEFAULT '{}' -- pl. bankszámlaszám, cégjegyzékszám
);

-- Szakirányú oktatási szerződések
CREATE TABLE szakiranyu_szerzodesek (
    id SERIAL PRIMARY KEY,
    diak_id INT NOT NULL REFERENCES diakok(id) ON DELETE CASCADE,
    partner_id INT NOT NULL REFERENCES partnerek(id),
    szerzodes_szama VARCHAR(100) UNIQUE,
    ervenyesseg_kezdet DATE NOT NULL,
    ervenyesseg_vege DATE,
    statusz szerzodes_statusz DEFAULT 'aktív',
    dokumentum_path TEXT, -- Lokális fájlszerver elérhetőség
    metadata JSONB DEFAULT '{}', -- pl. óradíj, speciális záradékok
    CONSTRAINT check_datuma CHECK (ervenyesseg_vege >= ervenyesseg_kezdet)
);

-- 5. KÉPZÉSI ÉS VIZSGAEREDMÉNYEK
-- ---------------------------------------------------------
-- Elvégzett modulok (Haladási napló)
CREATE TABLE modul_eredmenyek (
    id SERIAL PRIMARY KEY,
    diak_id INT NOT NULL REFERENCES diakok(id) ON DELETE CASCADE,
    modul_nev VARCHAR(255) NOT NULL,
    modul_kod VARCHAR(50),
    teljesites_datuma DATE,
    ertekeles VARCHAR(50), -- pl. Megfelelt, Kiválóan megfelelt
    oktato_id INT REFERENCES oktatok(id),
    metadata JSONB DEFAULT '{}'
);

-- Külső forrásból érkező jegyek (pl. Kréta szinkron)
CREATE TABLE kulso_jegyek (
    id SERIAL PRIMARY KEY,
    diak_id INT NOT NULL REFERENCES diakok(id) ON DELETE CASCADE,
    tantargy VARCHAR(100) NOT NULL,
    ertek INT NOT NULL CHECK (ertek BETWEEN 1 AND 5),
    datum TIMESTAMP NOT NULL,
    forras forras_tipus DEFAULT 'Kréta',
    kulso_azonosito VARCHAR(100), -- Kréta belső ID az ütközések elkerülésére
    metadata JSONB DEFAULT '{}'
);

-- 6. FELHASZNÁLÓK ÉS RBAC JOGOSULTSÁGOK
-- ---------------------------------------------------------
CREATE TYPE felhasznalo_szerep AS ENUM ('admin', 'oktato', 'titkarsag');

CREATE TABLE felhasznalok (
    id SERIAL PRIMARY KEY,
    felhasznalonev VARCHAR(50) UNIQUE NOT NULL,
    jelszo_hash TEXT NOT NULL,
    szerep felhasznalo_szerep NOT NULL,
    teljes_nev VARCHAR(255),
    szakma_id INT REFERENCES szakmak(id), -- Csak oktatók esetén releváns
    statusz BOOLEAN DEFAULT TRUE,
    utolso_bejelentkezes TIMESTAMP
);

-- 7. JOGOSULTSÁG-KEZELÉS ÉS AUDIT
-- ---------------------------------------------------------
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    felhasznalo_id INT REFERENCES felhasznalok(id),
    esemeny TEXT,
    idopont TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Indexek a teljesítmény optimalizáláshoz
CREATE INDEX idx_diak_nev ON diakok(nev);
CREATE INDEX idx_szerzodes_partner ON szakiranyu_szerzodesek(partner_id);
CREATE INDEX idx_jegyek_diak ON kulso_jegyek(diak_id);
CREATE INDEX idx_modul_diak ON modul_eredmenyek(diak_id);
