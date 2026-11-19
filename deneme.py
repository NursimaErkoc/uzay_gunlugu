"""
Adım 1: İlk API çağrımız.
NASA'nın APOD (Astronomy Picture of the Day = Günün Astronomi Fotoğrafı) API'sine
istek atıp gelen cevabı ekrana yazdırıyoruz.

Çalıştırmak için:  .venv\\Scripts\\python deneme.py
"""
import os

import httpx                    # HTTP istekleri atmamızı sağlayan kütüphane
from dotenv import load_dotenv  # .env dosyasındaki ayarları okur

# 1) .env dosyasını oku ve API anahtarını al
load_dotenv()
api_key = os.getenv("NASA_API_KEY", "DEMO_KEY")

# 2) İsteği hazırla: adres (URL) + parametreler
url = "https://api.nasa.gov/planetary/apod"

# İstersen belirli bir günün fotoğrafını da isteyebilirsin:
parametreler = {"api_key": api_key, "date": "2024-04-08"}

# 3) İsteği gönder (GET = "bana veri ver")
print("NASA'ya istek gönderiliyor...")
cevap = httpx.get(url, params=parametreler, timeout=20)

# 4) Durum kodunu kontrol et
#    200 = başarılı, 403 = anahtar hatalı, 429 = çok fazla istek (limit doldu)
print("Durum kodu:", cevap.status_code)

if cevap.status_code != 200:
    print("Bir sorun oluştu:", cevap.text)
    raise SystemExit(1)

# 5) Gelen JSON'u Python sözlüğüne (dict) çevir ve kullan
veri = cevap.json()

print()
print("📅 Tarih     :", veri["date"])
print("🌌 Başlık    :", veri["title"])
print("🖼️  Tür       :", veri["media_type"])   # "image" veya "video"
print("🔗 Adres     :", veri["url"])
print("📝 Açıklama  :", veri["explanation"][:300], "...")
print()
print("Gelen JSON'daki tüm alanlar:", list(veri.keys()))
