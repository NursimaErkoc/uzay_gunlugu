"""
Çeviri servisi: İngilizce metni Türkçeye çevirir.

Google Translate'in ücretsiz, anahtarsız uç noktasını kullanıyoruz.
Bu "resmi olmayan" bir uç nokta: bir gün değişebilir. O yüzden hata olursa
None döndürüyoruz ve site sadece İngilizce metni gösteriyor (çökmüyor).
İleride istersen resmi bir servise (ör. DeepL) geçmek için sadece bu dosyayı değiştirmek yeterli.
"""
import httpx

CEVIRI_URL = "https://translate.googleapis.com/translate_a/single"


async def turkceye_cevir(metin: str | None) -> str | None:
    """Metni İngilizceden Türkçeye çevirir. Başarısız olursa None döner."""
    if not metin:
        return None

    parametreler = {
        "client": "gtx",
        "sl": "en",   # kaynak dil (source language)
        "tl": "tr",   # hedef dil (target language)
        "dt": "t",    # "bize çeviriyi ver"
        "q": metin,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as istemci:
            # Uzun metinlerde GET adresi çok uzar, o yüzden POST ile gönderiyoruz
            cevap = await istemci.post(CEVIRI_URL, data=parametreler)
        cevap.raise_for_status()   # 200 değilse hata fırlat
        # Cevap iç içe listeler: [[["Çeviri cümle 1", "Original 1", ...], ["Çeviri cümle 2", ...]], ...]
        cumleler = cevap.json()[0]
        return "".join(cumle[0] for cumle in cumleler if cumle[0])
    except Exception:
        return None
