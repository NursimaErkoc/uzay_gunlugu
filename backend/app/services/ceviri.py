"""
Çeviri servisi: İngilizce metni Türkçeye çevirir.

Google Translate'in ücretsiz, anahtarsız uç noktasını kullanıyoruz.
Bu "resmi olmayan" bir uç nokta: bir gün değişebilir. O yüzden hata olursa
None döndürüyoruz ve site sadece İngilizce metni gösteriyor (çökmüyor).
İleride istersen resmi bir servise (ör. DeepL) geçmek için sadece bu dosyayı değiştirmek yeterli.
"""
import asyncio

import httpx

from app import cache

CEVIRI_URL = "https://translate.googleapis.com/translate_a/single"

# Aynı anda en fazla 5 çeviri isteği gitsin. 70 isteği birden gönderirsek
# servis bizi "saldırı" sanıp engelleyebilir. Semaphore = "aynı anda en fazla N kişi" kapısı.
_kapi = asyncio.Semaphore(5)


async def turkceye_cevir(metin: str | None) -> str | None:
    """Metni İngilizceden Türkçeye çevirir. Başarısız olursa None döner."""
    if not metin:
        return None

    # Aynı metni daha önce çevirdiysek tekrar sorma
    onbellek_anahtari = f"ceviri:{metin}"
    kayitli = cache.getir(onbellek_anahtari)
    if kayitli is not None:
        return kayitli

    parametreler = {
        "client": "gtx",
        "sl": "en",   # kaynak dil (source language)
        "tl": "tr",   # hedef dil (target language)
        "dt": "t",    # "bize çeviriyi ver"
        "q": metin,
    }
    try:
        async with _kapi:
            async with httpx.AsyncClient(timeout=15) as istemci:
                # Uzun metinlerde GET adresi çok uzar, o yüzden POST ile gönderiyoruz
                cevap = await istemci.post(CEVIRI_URL, data=parametreler)
        cevap.raise_for_status()   # 200 değilse hata fırlat
        # Cevap iç içe listeler: [[["Çeviri cümle 1", "Original 1", ...], ["Çeviri cümle 2", ...]], ...]
        cumleler = cevap.json()[0]
        sonuc = "".join(cumle[0] for cumle in cumleler if cumle[0])
    except Exception:
        return None

    cache.kaydet(onbellek_anahtari, sonuc, 7 * 24 * 60 * 60, kalici=True)   # 1 hafta, diskte de
    return sonuc
