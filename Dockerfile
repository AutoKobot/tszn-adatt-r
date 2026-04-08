# 1. Alap kép (Python 3.10)
FROM python:3.10-slim

# 2. Rendszer-függőségek telepítése (OCR, PDF)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-hun \
    libreoffice \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 3. Munkakönyvtár beállítása
WORKDIR /app

# 4. Függőségek másolása és telepítése
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Playwright böngésző ÉS annak függőségeinek telepítése
RUN playwright install chromium
RUN playwright install-deps chromium

# 6. Forráskód másolása
COPY . .

# 7. Alkalmazás indítása (Docker beépített env változókkal támogatva)
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000}
