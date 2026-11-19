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
