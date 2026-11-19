"""
Günün bilgisi: kendi hazırladığımız facts.json dosyasından her gün farklı bir bilgi seçer.
Burada dış API yok. Bazen en iyi "veri kaynağı" kendi dosyandır.
"""
import json
from datetime import date

from app.config import PROJE_KLASORU

BILGI_DOSYASI = PROJE_KLASORU / "backend" / "data" / "facts.json"

# Dosyayı sunucu açılırken bir kez oku, hafızada tut
with open(BILGI_DOSYASI, encoding="utf-8") as dosya:
    BILGILER: list[dict] = json.load(dosya)


def gunun_bilgisi(gun: date | None = None) -> dict:
    """
    Verilen günün bilgisini döndürür (verilmezse bugün).
    Mantık: yılın kaçıncı günüyse (1-366), bilgi sayısına bölümünden kalanı al.
    Böylece her gün sıradaki bilgi gelir, liste bitince başa döner.
    """
    gun = gun or date.today()
    sira = gun.timetuple().tm_yday % len(BILGILER)   # % = "bölümünden kalan" (mod)
    return {**BILGILER[sira], "sira": sira + 1, "toplam": len(BILGILER)}
