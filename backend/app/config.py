"""
Ayarlar: .env dosyasındaki değerleri tek bir yerden okuruz.
Diğer dosyalar ayarlara ihtiyaç duyunca buradan alır:  from app.config import NASA_API_KEY
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Proje kök klasörü (uzay_günlüğü/). Bu dosya: uzay_günlüğü/backend/app/config.py
PROJE_KLASORU = Path(__file__).resolve().parents[2]

# .env dosyasını kök klasörden yükle
load_dotenv(PROJE_KLASORU / ".env")

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")

# --- Veritabanı ---
# DATABASE_URL doluysa (internette) PostgreSQL kullanılır, boşsa (bilgisayarında) SQLite dosyası.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
VERITABANI = PROJE_KLASORU / "uzay_gunlugu.db"   # .gitignore'da (*.db), GitHub'a gitmez

# --- Güvenlik ---
# Site internetteyken hatırlatma kurma/silme ve test e-postası sadece bu anahtarı bilene açık.
# Boşsa (bilgisayarında) herkes kullanabilir.
YONETICI_ANAHTARI = os.getenv("YONETICI_ANAHTARI", "").strip()

# --- E-posta ---
# İnternette (Render): Resend API anahtarı. Render ücretsiz planda Gmail SMTP'yi engellediği için.
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
# Bilgisayarında: Gmail SMTP
GMAIL_ADRESI = os.getenv("GMAIL_ADRESI", "").strip()
GMAIL_UYGULAMA_SIFRESI = os.getenv("GMAIL_UYGULAMA_SIFRESI", "").replace(" ", "")  # Google boşluklu gösteriyor
# Hatırlatmalar kime gitsin? Boş bırakılırsa Gmail adresinin kendisine.
HATIRLATMA_ALICISI = os.getenv("HATIRLATMA_ALICISI", "").strip() or GMAIL_ADRESI

# --- Çeviri ---
# MyMemory çeviri servisine istekle birlikte gönderilen e-posta. Tanımlıysa günlük kota
# (paylaşılan) IP adresine değil bu adrese bağlanır: 5.000 yerine 50.000 karakter/gün.
# Render'da gerekli: Google ve anahtarsız MyMemory bulut sunucularından gelen istekleri engelliyor.
MYMEMORY_EPOSTA = os.getenv("MYMEMORY_EPOSTA", "").strip()
# DeepL çeviri anahtarı (deepl.com > hesap > API Keys). Ücretsiz anahtarlar ":fx" ile biter.
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "").strip()

# E-postadaki "takvimi aç" linki için sitenin adresi
SITE_ADRESI = os.getenv("SITE_ADRESI", "http://127.0.0.1:8000").rstrip("/")
