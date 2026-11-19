"""
NASA APOD servisi: NASA ile konuşan kod sadece bu dosyada.
deneme.py'deki mantığın aynısı, ama artık tekrar kullanılabilir bir fonksiyon.
"""
from datetime import date, timedelta

import httpx

from app import cache
from app.config import NASA_API_KEY

APOD_URL = "https://api.nasa.gov/planetary/apod"


class NasaHatasi(Exception):
    """NASA'dan beklenmeyen bir cevap geldiğinde fırlatılır."""


async def gunun_fotografi(tarih: str | None = None) -> dict:
    """
    APOD verisini döndürür. tarih verilmezse bugünün fotoğrafı gelir.
    Bugünün fotoğrafı alınamazsa (NASA hata verirse) dünkünü dener.
    """
    if tarih is not None:
        return await _apod_getir(tarih)

    # Yakın zamanda yedeğe düştüysek NASA'yı tekrar bekletmeden onu döndür
    yedek = cache.getir("apod:yedek")
    if yedek is not None:
        return yedek

    try:
        return await _apod_getir(None)
    except NasaHatasi:
        # Yedek plan: dünün fotoğrafı
        dun = (date.today() - timedelta(days=1)).isoformat()
        sonuc = {**await _apod_getir(dun), "yedek": True}  # frontend "dünkü gösteriliyor" diyebilsin
        cache.kaydet("apod:yedek", sonuc, 15 * 60)   # 15 dk sonra bugünkünü yeniden dene
        return sonuc


async def _apod_getir(tarih: str | None) -> dict:
    """
    NASA'dan tek bir günün APOD verisini çeker (önbellekli).
    tarih biçimi: "YYYY-AA-GG", örn. "2024-04-08". None = bugün.
    """
    onbellek_anahtari = f"apod:{tarih or 'bugun'}"

    # 1) Önce önbelleğe bak
    kayitli = cache.getir(onbellek_anahtari)
    if kayitli is not None:
        return kayitli

    # 2) Yoksa NASA'ya sor
    parametreler = {"api_key": NASA_API_KEY, "thumbs": "true"}
    if tarih:
        parametreler["date"] = tarih

    try:
        async with httpx.AsyncClient(timeout=20) as istemci:
            cevap = await istemci.get(APOD_URL, params=parametreler)
    except httpx.HTTPError as hata:   # internet yok, zaman aşımı vb.
        raise NasaHatasi(f"NASA'ya ulaşılamadı: {hata}") from hata

    if cevap.status_code != 200:
        raise NasaHatasi(f"NASA {cevap.status_code} döndürdü: {cevap.text[:200]}")

    ham = cevap.json()

    # 3) Sadece ihtiyacımız olan alanları al (veriyi sadeleştir)
    sonuc = {
        "tarih": ham.get("date"),
        "baslik": ham.get("title"),
        "aciklama": ham.get("explanation"),
        "tur": ham.get("media_type"),          # "image" veya "video"
        "url": ham.get("url"),
        "hd_url": ham.get("hdurl"),
        "kucuk_resim": ham.get("thumbnail_url"),  # video günleri için
        "telif": ham.get("copyright"),
        "yedek": False,
    }

    # 4) Önbelleğe kaydet: bugünün fotoğrafı 1 saat, eski tarihler 1 gün
    sure = 60 * 60 if tarih is None else 24 * 60 * 60
    cache.kaydet(onbellek_anahtari, sonuc, sure)
    return sonuc
