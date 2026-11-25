"""
Dünya'nın Bugünkü Fotoğrafı: NASA EPIC (Earth Polychromatic Imaging Camera)
Dokümantasyon: https://epic.gsfc.nasa.gov/about/api

EPIC kamerası DSCOVR uydusunun üzerinde. Uydu, Dünya ile Güneş arasında, Dünya'dan ~1,5 milyon km
uzaktaki "L1 noktası"nda duruyor: orada Dünya'nın ve Güneş'in çekimi dengelenir. Hep Güneş'e dönük
tarafa baktığı için Dünya'yı her zaman tamamen aydınlık görür. Günde 10-20 fotoğraf çeker;
fotoğraflar işlenip yayınlanana kadar 1-2 gün geçer.

Anahtar gerekmez (epic.gsfc.nasa.gov doğrudan kullanılabiliyor).
"""
import math
from datetime import datetime, timezone

import httpx

from app import cache
from app.services import events

EPIC_API = "https://epic.gsfc.nasa.gov/api/natural"
EPIC_ARSIV = "https://epic.gsfc.nasa.gov/archive/natural"
TURKIYE = (39.0, 35.0)        # Türkiye'nin yaklaşık ortası (enlem, boylam)
GORUNURLUK_ACISI = 70         # Fotoğrafın merkezine bu kadar dereceden yakın yerler rahatça görünür


class EpicHatasi(Exception):
    """EPIC'ten veri alınamadı."""


def bolge_adi(enlem: float, boylam: float) -> str:
    """Fotoğrafın ortasındaki noktaya göre, Dünya'nın görünen yüzünün kabaca adı."""
    bolgeler = [
        (-180, -130, "Pasifik Okyanusu"),
        (-130, -90, "Kuzey Amerika ve Pasifik"),
        (-90, -50, "Amerika kıtaları"),
        (-50, -15, "Atlantik Okyanusu ve Güney Amerika"),
        (-15, 20, "Afrika ve Avrupa"),
        (20, 55, "Afrika, Orta Doğu ve Türkiye"),
        (55, 90, "Hindistan ve Orta Asya"),
        (90, 130, "Doğu Asya ve Avustralya"),
        (130, 181, "Pasifik, Japonya ve Avustralya"),
    ]
    return next(ad for bas, son, ad in bolgeler if bas <= boylam < son)


def aci_uzakligi(nokta1: tuple[float, float], nokta2: tuple[float, float]) -> float:
    """İki nokta arasındaki açı (derece), Dünya'nın merkezinden bakınca. 0 = aynı yer, 180 = tam karşı taraf."""
    f1, l1 = map(math.radians, nokta1)
    f2, l2 = map(math.radians, nokta2)
    cos_aci = math.sin(f1) * math.sin(f2) + math.cos(f1) * math.cos(f2) * math.cos(l2 - l1)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_aci))))


def _kare(ham: dict) -> dict:
    """EPIC kaydından sayfanın ihtiyaç duyduğu alanları çıkarır."""
    zaman = datetime.strptime(ham["date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    yol = f"{EPIC_ARSIV}/{zaman:%Y/%m/%d}"
    merkez = ham["centroid_coordinates"]
    konum = ham["dscovr_j2000_position"]
    uzaklik = math.sqrt(konum["x"] ** 2 + konum["y"] ** 2 + konum["z"] ** 2)
    return {
        "zaman": zaman.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "resim": f"{yol}/jpg/{ham['image']}.jpg",          # 2048x2048, ~250 KB
        "onizleme": f"{yol}/thumbs/{ham['image']}.jpg",    # küçük, ~7 KB
        "merkez": {"enlem": round(merkez["lat"], 1), "boylam": round(merkez["lon"], 1)},
        "bolge": bolge_adi(merkez["lat"], merkez["lon"]),
        "turkiye_gorunur": aci_uzakligi(TURKIYE, (merkez["lat"], merkez["lon"])) < GORUNURLUK_ACISI,
        "uzaklik_km": int(round(uzaklik, -3)),   # en yakın bin km'ye yuvarla
    }


async def _getir(adres: str, anahtar: str, sure: int):
    kayitli = cache.getir(anahtar)
    if kayitli is not None:
        return kayitli
    try:
        async with httpx.AsyncClient(timeout=30, headers=events.ISTEK_BASLIKLARI) as istemci:
            cevap = await istemci.get(adres)
        cevap.raise_for_status()
        veri = cevap.json()
    except (httpx.HTTPError, ValueError) as hata:
        raise EpicHatasi(f"NASA EPIC verisi alınamadı ({type(hata).__name__})") from None
    cache.kaydet(anahtar, veri, sure, kalici=True)
    return veri


async def dunya_fotograflari(tarih: str | None = None) -> dict:
    """
    Bir günün EPIC fotoğrafları, zamana göre sıralı. Tarih verilmezse en son yayınlanan gün.
    Geçmiş günler değişmez: 7 gün saklıyoruz. En son gün 3 saatte bir yenilensin.
    """
    if tarih:
        ham = await _getir(f"{EPIC_API}/date/{tarih}", f"epic:{tarih}", 7 * 24 * 60 * 60)
    else:
        ham = await _getir(EPIC_API, "epic:son", 3 * 60 * 60)

    kareler = sorted((_kare(k) for k in ham), key=lambda k: k["zaman"])
    return {
        "tarih": kareler[0]["zaman"][:10] if kareler else tarih,
        "kareler": kareler,
    }
