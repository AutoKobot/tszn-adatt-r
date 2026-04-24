import calendar
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
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
        2. Pillér: Jelenlét-Logikai Motor
        Kiszámolja az M értéket (munkanap arány) az adott hónapra.
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

        # Státuszok szerinti összegzés (2. Pillér alapján)
        # Jár a normatíva: dualis_nap, betegszabadsag, fizetett_szabadsag
        # (A régi 'jelen' státuszt 'dualis_nap'-nak vesszük a kompatibilitás miatt)
        jogosult_státuszok = ['dualis_nap', 'betegszabadsag', 'fizetett_szabadsag', 'jelen']
        
        jelen_napok = 0
        for a in att_sorok:
            if a.statusz in jogosult_státuszok:
                jelen_napok += 1
            # Megjegyzés: itt lehetne óra-alapú számítás is (pl. sum(oraszam)/8)

        # Munkaszüneti napok lekérése a TanevRendje táblából
        munkaszuneti_napok_db = db.query(models.TanevRendje).filter(
            models.TanevRendje.datum >= datum_kezd,
            models.TanevRendje.datum <= datum_vege,
            models.TanevRendje.tipus == 'munkaszuneti'
        ).count()

        # Elvárt munkanapok = hétköznapok - munkaszüneti napok
        hetkonapok = 0
        for d in range(1, napok_szama + 1):
            if datetime.date(ev, honap, d).weekday() < 5:
                hetkonapok += 1
        
        elvart = max(hetkonapok - munkaszuneti_napok_db, 1)

        return round(min(jelen_napok / elvart, 1.0), 4)

    def kalkulal_havi(self, diak_id: int, ev: int, honap: int, db: Session) -> dict:
        """3. Pillér: Retrospektív számítás"""
        szakma = self.get_szakma(diak_id, db)
        konfig = self.get_aktiv_konfig(db)

        if not szakma:
            return {
                "diak_id": diak_id, "ev": ev, "honap": honap,
                "havi_normativa": 0, "adokedvezmeny": 0, "sikerdij_celtar": 0,
                "munkanap_arany": 0, "szorzo": 0, "onkoltsegi_alap": 0, "jogosult": False,
                "hiba": "Nincs szakma hozzárendelve"
            }

        O = szakma.onkoltsegi_alap
        S = float(szakma.szorzo)
        M = self.get_munkanap_arany(diak_id, ev, honap, db)

        eves_T = O * S              # Teljes éves összeg (M=1.0 esetén)
        havi_T = (eves_T * M) / 12  # Arányos havi összeg

        sikerdij_pct = float(konfig.sikerdij_szazalek / 100) if konfig else 0.20
        sikerdij = havi_T * sikerdij_pct

        return {
            "diak_id": diak_id,
            "ev": ev, "honap": honap,
            "havi_normativa": round(havi_T),
            "adokedvezmeny": round(havi_T),
            "sikerdij_celtar": round(sikerdij),
            "munkanap_arany": M,
            "szorzo": S,
            "onkoltsegi_alap": O,
            "jogosult": M >= 0.8  # Jogszabályi küszöb példa
        }

    def kalkulal_eves_prognozis(self, diak_id: int, tanev: str, db: Session) -> dict:
        """3. Pillér: Prediktív számítás"""
        ev_kezdet = int(tanev.split("/")[0])
        # Tanév hónapjai: szept(9) - jún(6)
        honapok = [(ev_kezdet, 9), (ev_kezdet, 10), (ev_kezdet, 11), (ev_kezdet, 12),
                   (ev_kezdet+1, 1), (ev_kezdet+1, 2), (ev_kezdet+1, 3), (ev_kezdet+1, 4), (ev_kezdet+1, 5), (ev_kezdet+1, 6)]

        tenyleges = 0
        prognozis = 0
        teljesitett_honapok = 0
        ma = datetime.date.today()

        for ev, honap in honapok:
            vizsgalt_datum = datetime.date(ev, honap, 1)
            if vizsgalt_datum <= ma.replace(day=1):
                res = self.kalkulal_havi(diak_id, ev, honap, db)
                tenyleges += res["havi_normativa"]
                teljesitett_honapok += 1
            else:
                # Jövőbeli hónap: M=1.0 feltételezés
                szakma = self.get_szakma(diak_id, db)
                if szakma:
                    prognozis += round((szakma.onkoltsegi_alap * float(szakma.szorzo)) / 12)

        konfig = self.get_aktiv_konfig(db)
        sikerdij_pct = float(konfig.sikerdij_szazalek / 100) if konfig else 0.20

        ossz_ertek = tenyleges + prognozis

        return {
            "diak_id": diak_id,
            "tanev": tanev,
            "tenyleges_osszeg": tenyleges,
            "prognozis_osszeg": ossz_ertek,
            "sikerdij_celtar_ossz": round(ossz_ertek * sikerdij_pct),
            "teljesitett_honapok": teljesitett_honapok,
            "osszes_honapok": 10
        }

    def roi_szamitas(self, diak_id: int, tanev: str, db: Session) -> dict:
        """3. Pillér: ROI számítás"""
        prog = self.kalkulal_eves_prognozis(diak_id, tanev, db)
        
        # Példa költség számítás: 
        # 1. Kifizetett tanulói bér (átlagosan havi 100.000 Ft)
        kifizetett_ber = prog["teljesitett_honapok"] * 100000
        
        # 2. Extra költségek a táblából
        extra_ktg = db.query(models.KoltsegTetel).filter(
            models.KoltsegTetel.diak_id == diak_id
        ).all()
        extra_sum = sum(k.osszeg for k in extra_ktg)

        ossz_ktg = kifizetett_ber + extra_sum
        bevétel = prog["tenyleges_osszeg"]
        haszon = bevétel - ossz_ktg

        return {
            "diak_id": diak_id,
            "tanev": tanev,
            "bevetel_normativa": bevétel,
            "kiadas_osszes": ossz_ktg,
            "netto_eredmeny": haszon,
            "roi_szazalek": round((haszon / max(ossz_ktg, 1)) * 100, 1)
        }

    def what_if(self, tervezett_diakok: list, db: Session) -> dict:
        """3. Pillér: Stratégiai szimulátor"""
        jelenlegi_havi = 0
        students = db.query(models.Student).all()
        ma = datetime.date.today()
        
        for s in students:
            res = self.kalkulal_havi(s.id, ma.year, ma.month, db)
            jelenlegi_havi += res["havi_normativa"]

        plusz_havi = 0
        reszletezes = []
        for item in tervezett_diakok:
            szakma = db.query(models.SzakmaTorzs).get(item["szakma_id"])
            if szakma:
                db_szam = item.get("db", 1)
                havi = round((szakma.onkoltsegi_alap * float(szakma.szorzo)) / 12) * db_szam
                plusz_havi += havi
                reszletezes.append({
                    "szakma": szakma.megnevezes,
                    "db": db_szam,
                    "plusz_havi": havi
                })

        return {
            "jelenlegi_havi_keret": jelenlegi_havi,
            "szimulalt_havi_keret": jelenlegi_havi + plusz_havi,
            "valtozas_havi": plusz_havi,
            "valtozas_eves": plusz_havi * 12,
            "reszletezes": reszletezes
        }

    def get_global_roi_summary(self, db: Session):
        """Összesített ROI kimutatás az összes aktív diákra, levonva az ösztöndíjakat és fix költségeket."""
        students = db.query(models.Student).all()
        
        # 1. BEVÉTELI OLDAL: Normatíva (M=1.0 éves prognózis)
        total_normativa_income = 0
        total_monthly_scholarship = 0
        for s in students:
            res = self.kalkulal_eves_prognozis(db, s.id)
            total_normativa_income += res.bevetel_osszes
            # Ösztöndíj (havi kiadás)
            if s.havi_osztondij:
                total_monthly_scholarship += s.havi_osztondij
        
        # 2. KIADÁSI OLDAL: Egyéb költségek (Adatbázisból)
        expenses = db.query(models.KoltsegTetel).all()
        fixed_one_time_costs = 0
        recurring_monthly_costs = 0
        
        for e in expenses:
            # Ha van gyakoriság mező (havi), akkor 12-vel szorozzuk az évesítéshez
            gyakorisag = getattr(e, "gyakorisag", "egyszeri")
            if gyakorisag == "havi":
                recurring_monthly_costs += e.osszeg
            else:
                fixed_one_time_costs += e.osszeg
        
        # Évesített kiadások
        total_annual_scholarship = total_monthly_scholarship * 12
        total_annual_recurring = recurring_monthly_costs * 12
        total_expense = fixed_one_time_costs + total_annual_scholarship + total_annual_recurring
        
        return {
            "bevetel_normativa": total_normativa_income,
            "kiadas_osztondij": total_annual_scholarship,
            "kiadas_egyeb": fixed_one_time_costs + total_annual_recurring,
            "kiadas_osszes": total_expense,
            "netto_eredmeny": total_normativa_income - total_expense,
            "havi_kiadas_osztondij": total_monthly_scholarship,
            "havi_kiadas_egyeb": recurring_monthly_costs
        }

normativa_service = NormativaService()
