from playwright.async_api import async_playwright
import datetime
import logging
from . import models, database

# --- KONFIGURÁCIÓ ---
EXTERNAL_LOG_URL = "https://autokobot.onrender.com/login"
SYNC_USER = "admin_tiszalok"
SYNC_PASS = "titkos_jelszo_123"

class SyncService:
    def __init__(self):
        self.logger = logging.getLogger("sync_service")

    async def sync_external_data(self):
        self.logger.info(f"Szinkronizálás indítása: {datetime.datetime.now()}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_context().new_page()
            
            try:
                # 1. Bejelentkezés a külső felületre
                await page.goto(EXTERNAL_LOG_URL)
                await page.fill("#username", SYNC_USER)
                await page.fill("#password", SYNC_PASS)
                await page.click("#login-btn")
                await page.wait_for_selector(".grades-table") # Várakozás a betöltésre

                # 2. Jegyek kinyerése (scraping)
                # Ez egy példa szelektorkeresés, az oldal struktúrájától függ!
                grades = await page.evaluate("""() => {
                    const rows = Array.from(document.querySelectorAll('.grades-table tr'));
                    return rows.map(row => {
                        const cells = row.querySelectorAll('td');
                        return {
                            diak_id: cells[0]?.innerText,
                            tantargy: cells[1]?.innerText,
                            ertek: cells[2]?.innerText,
                            datum: cells[3]?.innerText
                        };
                    }).filter(g => g.diak_id); // Csak ahol van adat
                }""")

                # 3. Adatok mentése a helyi adatbázisba
                await self.save_to_local_db(grades)
                
                self.logger.info(f"Sikeres szinkron: {len(grades)} jegy rögzítve.")
            except Exception as e:
                self.logger.error(f"Hiba a szinkron során: {str(e)}")
            finally:
                await browser.close()

    async def save_to_local_db(self, grades):
        db = database.SessionLocal()
        try:
            for g in grades:
                # Ellenőrizzük, létezik-e már ez a jegy (kulso_azonosito alapján)
                # Itt egy egyszerűsített insert logic:
                db_grade = models.ExternalGrade(
                    diak_id=g['diak_id'],
                    tantargy=g['tantargy'],
                    ertek=int(g['ertek']),
                    datum=datetime.datetime.now(), # Vagy a kinyert dátum
                    forras="Kréta"
                )
                db.add(db_grade)
            db.commit()
        finally:
            db.close()

sync_service = SyncService()
