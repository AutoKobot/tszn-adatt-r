-- Tiszalöki Szakképzési ÁKK - Komplett Tesztadatok
-- PostgreSQL

-- 1. Szakmák
INSERT INTO szakmak (szakma_kod, megnevezes, agazat)
VALUES 
('4 0713 04 07', 'Szoftverfejlesztő és -tesztelő', 'Informatika és távközlés'),
('4 0812 05 02', 'Logisztikai technikus', 'Kereskedelem és logisztika');

-- 2. Osztályok
INSERT INTO osztalyok (megnevezes, tanev, szakma_id)
VALUES 
('11.A', '2023/2024', 1),
('F-2024', '2024/2025', 2);

-- 3. Oktatók
INSERT INTO oktatok (nev, email, telefon, szakterulet)
VALUES 
('Dr. Nagy Elemér', 'nagy.elemer@akk.hu', '+36 30 555 1255', 'Szoftvertechnológia'),
('Kiss Julianna', 'kiss.juli@akk.hu', '+36 30 555 9876', 'Raktárlogisztika');

-- 4. Diákok
INSERT INTO diakok (oktatasi_azonosito, nev, email, tagozat, osztaly_id, megjegyzesek)
VALUES 
('72004455112', 'Kovács Péter', 'kovacs.p@diak.hu', 'nappali', 1, '{"diakigazolvany": "123456BC", "allergia": ["mogyoró"]}'),
('72559988776', 'Szabó Éva', 'szabo.e@felnott.hu', 'felnőtt', 2, '{"munkaltato": "Példa Kft.", "diakigazolvany": "987654XY"}');

-- 5. Gondviselők
INSERT INTO gondviselok (diak_id, nev, telefon, kapcsolat_típusa)
VALUES 
(1, 'Kovács Ferenc', '+36 70 123 4567', 'apa');

-- 6. Partnerek (Gazdálkodó szervezetek)
INSERT INTO partnerek (cegnev, adoszam, szekhely, kapcsolattarto_neve)
VALUES 
('Software Dev Zrt.', '11223344-2-13', 'Tiszalök, 4450 Kossuth út 10.', 'Takács László');

-- 7. Szakirányú oktatási szerződések
INSERT INTO szakiranyu_szerzodesek (diak_id, partner_id, szerzodes_szama, ervenyesseg_kezdet, ervenyesseg_vege, statusz)
VALUES 
(1, 1, 'TSZ-2023/001', '2023-09-01', '2026-06-15', 'aktív');

-- 8. Elvégzett modulok (Haladási napló)
INSERT INTO modul_eredmenyek (diak_id, modul_nev, modul_kod, teljesites_datuma, ertekeles, oktato_id)
VALUES 
(1, 'Hálózati alapok', 'MOD-01', '2026-03-15', 'Kiválóan megfelelt', 1);

-- 9. Külső forrásból érkező jegyek (Kréta szinkron)
INSERT INTO kulso_jegyek (diak_id, tantargy, ertek, datum, forras, kulso_azonosito)
VALUES 
(1, 'Programozás', 5, '2026-04-01 08:30:00', 'Kréta', 'KR-98321'),
(1, 'Idegen nyelv', 4, '2026-04-02 10:15:00', 'Kréta', 'KR-98335'),
(2, 'Logisztikai alapok', 5, '2026-04-01 14:00:00', 'Kréta', 'KR-98511');
