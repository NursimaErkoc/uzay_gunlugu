"""
Güncel uzay haberleri: Spaceflight News API (ücretsiz, anahtarsız).
Dokümantasyon: https://api.spaceflightnewsapi.net/v4/docs/
"""
import asyncio

import httpx

from app import cache
from app.services import ceviri

HABER_URL = "https://api.spaceflightnewsapi.net/v4/articles/"


class HaberHatasi(Exception):
    """Haber servisi cevap vermediğinde fırlatılır."""


async def son_haberler(adet: int = 6) -> list[dict]:
    """En son uzay haberlerini (başlık ve özet Türkçeye çevrilmiş) döndürür."""
    onbellek_anahtari = f"haberler:{adet}"
    kayitli = cache.getir(onbellek_anahtari)
    if kayitli is not None:
        return kayitli

    # APOD yazıları da haber olarak geliyor, onları ayıklayacağımız için biraz fazla iste
    try:
        async with httpx.AsyncClient(timeout=20) as istemci:
            cevap = await istemci.get(HABER_URL, params={"limit": adet + 6})
        cevap.raise_for_status()
    except httpx.HTTPError as hata:
        raise HaberHatasi(f"Haber servisine ulaşılamadı: {type(hata).__name__}") from hata

    ham_haberler = cevap.json()["results"]
    haberler = [
        {
            "baslik": h["title"],
            "ozet": h["summary"],
            "gorsel": h["image_url"],
            "kaynak": h["news_site"],
            "url": h["url"],
            "tarih": h["published_at"],
        }
        for h in ham_haberler
        if not h["title"].startswith("APOD")   # günün fotoğrafını zaten gösteriyoruz
    ][:adet]

    # Tüm başlık ve özetleri aynı anda çevir
    cevirmeler = await asyncio.gather(
        *(ceviri.turkceye_cevir(h["baslik"]) for h in haberler),
        *(ceviri.turkceye_cevir(h["ozet"]) for h in haberler),
    )
    for i, haber in enumerate(haberler):
        haber["baslik_tr"] = cevirmeler[i]
        haber["ozet_tr"] = cevirmeler[len(haberler) + i]

    # Tüm çeviriler başarılıysa 30 dk sakla. Bir kısmı başarısızsa (servis yoğun olabilir)
    # sadece 5 dk sakla ki kısa süre sonra tekrar denensin; yoksa 30 dk İngilizce kalır.
    eksik_ceviri = any(h["baslik"] and not h["baslik_tr"] for h in haberler)
    cache.kaydet(onbellek_anahtari, haberler, 5 * 60 if eksik_ceviri else 30 * 60)
    return haberler
