"""
Yaklaşan Asteroitler: NASA NeoWs (Near Earth Object Web Service)
Dokümantasyon: https://api.nasa.gov  ("Asteroids - NeoWs")

Önümüzdeki 7 günde Dünya'nın yakınından geçecek asteroitleri getirir ve sayıları
anlaşılır karşılaştırmalara çevirir ("Ay'dan 3 kat uzak", "bir futbol sahası kadar").

GÜVENLİK: NASA'nın cevabında her asteroidin "links" alanında NASA anahtarımız da yazıyor!
O yüzden cevabı olduğu gibi tarayıcıya göndermiyoruz; sadece ihtiyacımız olan alanları
seçip yeni bir sözlük oluşturuyoruz. Hata mesajlarına da istek adresini koymuyoruz
(adreste anahtar var).
"""
import re
from datetime import date, datetime, timedelta, timezone

import httpx

from app import cache
from app.config import NASA_API_KEY

NEOWS_URL = "https://api.nasa.gov/neo/rest/v1/feed"
AY_UZAKLIGI_KM = 384_400
MERMI_HIZI_KMS = 1.0   # bir tüfek mermisi yaklaşık saniyede 1 km gider
YOLCU_UCAGI_KMS = 0.25  # yolcu uçağı ~900 km/sa

# (bu boydan küçükse, karşılaştırma)  metre cinsinden
BOYUTLAR = [
    (4, "Bir araba kadar"),
    (15, "Bir otobüs kadar"),
    (40, "Bir basketbol sahası kadar"),
    (80, "Galata Kulesi kadar"),             # 63 m
    (140, "Bir futbol sahası kadar"),         # 105 m
    (400, "Eyfel Kulesi kadar"),              # 330 m
    (1200, "Boğaziçi Köprüsü'nün iki kulesi arası kadar"),   # 1074 m
    (float("inf"), "Bir dağ kadar"),
]


class AsteroitHatasi(Exception):
    """NASA'dan veri alınamadı."""


def boyut_karsilastirma(metre: float) -> str:
    return next(metin for sinir, metin in BOYUTLAR if metre < sinir)


def uzaklik_karsilastirma(ay_kati: float) -> str:
    if ay_kati < 1:
        return "Ay'dan daha yakın!"
    return f"Ay'ın {ay_kati:.1f} katı uzaklıkta".replace(".", ",")


def hiz_karsilastirma(kms: float) -> str:
    if kms < 0.75:
        # Mermiden yavaş: yolcu uçağıyla karşılaştır (~900 km/sa = 0,25 km/sn)
        return f"Bir yolcu uçağından {max(round(kms / YOLCU_UCAGI_KMS), 1)} kat hızlı"
    if kms < 1.5:
        return "Bir tüfek mermisi kadar hızlı"
    return f"Bir tüfek mermisinden {round(kms / MERMI_HIZI_KMS)} kat hızlı"


def _kisa_ad(ad: str) -> str:
    """'455659 (2005 BO1)' -> '2005 BO1'  ·  '(2026 WK3)' -> '2026 WK3'"""
    parantez = re.search(r"\(([^)]+)\)", ad)
    return parantez.group(1) if parantez else ad.strip()


async def _neows_getir(baslangic: date, bitis: date) -> dict:
    anahtar = f"neows:{baslangic}:{bitis}"
    kayitli = cache.getir(anahtar)
    if kayitli is not None:
        return kayitli
    try:
        async with httpx.AsyncClient(timeout=30) as istemci:
            cevap = await istemci.get(NEOWS_URL, params={
                "start_date": baslangic.isoformat(), "end_date": bitis.isoformat(), "api_key": NASA_API_KEY,
            })
        cevap.raise_for_status()
        veri = cevap.json()
    except (httpx.HTTPError, ValueError) as hata:
        # str(hata) istek adresini (ve dolayısıyla anahtarı) içerebilir; sadece hatanın türünü yazıyoruz
        durum = getattr(getattr(hata, "response", None), "status_code", None)
        raise AsteroitHatasi(f"NASA asteroit verisi alınamadı ({type(hata).__name__}{f', HTTP {durum}' if durum else ''})") from None
    cache.kaydet(anahtar, veri, 6 * 60 * 60, kalici=True)
    return veri


def _asteroit(ham: dict) -> dict | None:
    """NASA'nın kaydından sadece gereken alanları seçer (anahtar içeren 'links' alanı ALINMAZ)."""
    yaklasma = next((y for y in ham.get("close_approach_data", []) if y.get("orbiting_body") == "Earth"), None)
    if yaklasma is None:
        return None
    cap = ham["estimated_diameter"]["meters"]
    cap_min, cap_max = cap["estimated_diameter_min"], cap["estimated_diameter_max"]
    ortalama = (cap_min + cap_max) / 2
    uzaklik_km = float(yaklasma["miss_distance"]["kilometers"])
    ay_kati = uzaklik_km / AY_UZAKLIGI_KM
    hiz = float(yaklasma["relative_velocity"]["kilometers_per_second"])
    zaman = datetime.fromtimestamp(yaklasma["epoch_date_close_approach"] / 1000, tz=timezone.utc)
    return {
        "id": str(ham["id"]),
        "ad": _kisa_ad(ham["name"]),
        "zaman": zaman.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "uzaklik_km": round(uzaklik_km),
        "ay_kati": round(ay_kati, 2),
        "uzaklik_metni": uzaklik_karsilastirma(ay_kati),
        "cap_min_m": round(cap_min),
        "cap_max_m": round(cap_max),
        "boyut_metni": boyut_karsilastirma(ortalama),
        "hiz_kms": round(hiz, 1),
        "hiz_metni": hiz_karsilastirma(hiz),
        "tehlikeli": bool(ham.get("is_potentially_hazardous_asteroid")),
        "jpl": ham.get("nasa_jpl_url"),
    }


async def yaklasan_asteroitler(bugun: date | None = None) -> dict:
    """Bugünden itibaren 7 gün içinde Dünya'ya yaklaşacak asteroitler, zamana göre sıralı."""
    bugun = bugun or datetime.now(timezone.utc).date()
    bitis = bugun + timedelta(days=7)   # NeoWs tek seferde en fazla 7 gün veriyor
    veri = await _neows_getir(bugun, bitis)

    asteroitler = [a for gun in veri.get("near_earth_objects", {}).values() for h in gun if (a := _asteroit(h))]
    asteroitler.sort(key=lambda a: a["zaman"])

    ozet = None
    if asteroitler:
        en_yakin = min(asteroitler, key=lambda a: a["uzaklik_km"])
        en_buyuk = max(asteroitler, key=lambda a: a["cap_max_m"])
        en_hizli = max(asteroitler, key=lambda a: a["hiz_kms"])
        ozet = {
            "toplam": len(asteroitler),
            "aydan_yakin": sum(a["ay_kati"] < 1 for a in asteroitler),
            "tehlikeli": sum(a["tehlikeli"] for a in asteroitler),
            "en_yakin": en_yakin["id"],
            "en_buyuk": en_buyuk["id"],
            "en_hizli": en_hizli["id"],
        }
    return {
        "baslangic": bugun.isoformat(),
        "bitis": bitis.isoformat(),
        "ozet": ozet,
        "asteroitler": asteroitler,
    }
