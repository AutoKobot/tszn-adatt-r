import pytesseract
import re
from PIL import Image
import io

class OCRService:
    def __init__(self):
        # A Tesseract végrehajtó fájlhoz a rendszer útvonal (Render Docker-ben alapértelmezett)
        pass

    async def process_image(self, image_bytes):
        # 1. OCR végrehajtása Pytesseract használatával (Memóriabarát módszer)
        image = Image.open(io.BytesIO(image_bytes))
        full_text = pytesseract.image_to_string(image, lang="hun+eng")

        
        # 2. Adatok kinyerése Regex segítségével (Magyar kártyákhoz optimalizálva)
        data = {
            "nev": self.extract_name(full_text),
            "anyja_neve": self.extract_regex(full_text, r"Anyja neve:\s*([A-Za-zÁÉÍÓÖŐÚÜŰ\s]+)"),
            "szuletesi_hely": self.extract_regex(full_text, r"Születési hely:\s*([A-Za-zÁÉÍÓÖŐÚÜŰ]+)"),
            "lakcim": self.extract_regex(full_text, r"Lakóhely:\s*([^\d]+[\d]+[\.a-zA-Z\s]+)"),
            "azonosito_szam": self.extract_regex(full_text, r"([A-Z]{2}\d{6})") # pl. AB123456
        }
        
        return data, full_text

    def extract_name(self, text):
        # Egyszerűsített név keresés (gyakran az első nagyobb blokk)
        names = re.findall(r"Név:\s*([A-Za-zÁÉÍÓÖŐÚÜŰ\s]+)", text)
        return names[0].strip() if names else "Nincs adat"

    def extract_regex(self, text, pattern):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else "Nincs adat"

ocr_service = OCRService()
