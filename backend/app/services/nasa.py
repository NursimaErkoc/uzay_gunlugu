"""
NASA APOD servisi: NASA ile konuşan kod sadece bu dosyada.

NOT: NASA, APOD'u apod.nasa.gov'dan science.nasa.gov'a taşıdı. Eski API
(api.nasa.gov/planetary/apod) taşınmadan sonra fotoğraf yerine NASA logosu
döndürmeye başladı. Bu yüzden veriyi yeni sitenin WordPress API'sinden alıyoruz:
    https://science.nasa.gov/wp-json/wp/v2/image-article
Her APOD burada bir "image-article" yazısı. Anahtar gerekmiyor.

Gerçek hayatta da böyle olur: kullandığın API değişir, sen de uyum sağlarsın.
"""
import asyncio
import html
import re
from datetime import date, timedelta

import httpx

from app import cache
from app.services import ceviri

WP_URL = "https://science.nasa.gov/wp-json/wp/v2/image-article"
ISTEK_BASLIKLARI = {"User-Agent": "UzayGunlugu/0.1 (ogrenci projesi)"}

# APOD 16 Haziran 1995'te başladı; daha önceki bir gün için NASA'ya boşuna sormayız.
APOD_BASLANGIC = date(1995, 6, 16)


class NasaHatasi(Exception):
    """NASA'dan beklenmeyen bir cevap geldiğinde fırlatılır."""


class ApodBulunamadi(NasaHatasi):
    """İstenen tarihte APOD yoksa (örneğin gelecek bir tarih) fırlatılır."""


async def gunun_fotografi(tarih: str | None = None) -> dict:
    """
    APOD verisini döndürür. tarih verilmezse en son yayınlanan (bugünün) fotoğraf gelir.
    tarih biçimi: "YYYY-AA-GG", örn. "2024-04-08"
    """
    if tarih and date.fromisoformat(tarih) < APOD_BASLANGIC:
        raise ApodBulunamadi(f"APOD 16 Haziran 1995'te başladı, {tarih} tarihinde fotoğraf yok")

    onbellek_anahtari = f"apod:{tarih or 'bugun'}"

    # 1) Önce önbelleğe bak
    kayitli = cache.getir(onbellek_anahtari)
    if kayitli is not None:
        return kayitli

    # 2) Yoksa NASA'ya sor
    parametreler = {
        "search": "APOD",
        "per_page": 1,
        "_fields": "date,title,link,content,featured_image_url",  # sadece gerekli alanlar
    }
    if tarih:
        # WordPress tarih filtresi: "after" ile "before" arasındaki yazılar
        gun = date.fromisoformat(tarih)
        parametreler["after"] = f"{gun - timedelta(days=1)}T23:59:59"
        parametreler["before"] = f"{gun}T23:59:59"

    try:
        async with httpx.AsyncClient(timeout=30, headers=ISTEK_BASLIKLARI) as istemci:
            cevap = await istemci.get(WP_URL, params=parametreler)
    except httpx.HTTPError as hata:   # internet yok, zaman aşımı vb.
        raise NasaHatasi(f"NASA'ya ulaşılamadı: {type(hata).__name__}") from hata

    if cevap.status_code != 200:
        raise NasaHatasi(f"NASA {cevap.status_code} döndürdü")

    yazilar = cevap.json()   # bir liste döner
    if not yazilar:
        raise ApodBulunamadi(f"{tarih} tarihi için fotoğraf bulunamadı")

    sonuc = _sadelestir(yazilar[0])

    # 3) Başlığı ve açıklamayı Türkçeye çevir (ikisini aynı anda: asyncio.gather)
    sonuc["baslik_tr"], sonuc["aciklama_tr"] = await asyncio.gather(
        ceviri.turkceye_cevir(sonuc["baslik"]),
        ceviri.turkceye_cevir(sonuc["aciklama"]),
    )

    # 4) Önbelleğe kaydet: bugünün fotoğrafı 1 saat, eski tarihler 1 gün.
    #    Çeviri başarısız olduysa 5 dk sonra tekrar denensin diye kısa tut.
    sure = 60 * 60 if tarih is None else 24 * 60 * 60
    if sonuc["aciklama"] and not sonuc["aciklama_tr"]:
        sure = 5 * 60
    cache.kaydet(onbellek_anahtari, sonuc, sure)
    return sonuc


def _sadelestir(yazi: dict) -> dict:
    """WordPress'in karmaşık cevabından sadece ihtiyacımız olan alanları çıkarır."""
    icerik = yazi["content"]["rendered"]   # yazının HTML'i

    # Başlık: "APOD: 2024 April 8 – The Changing Ion Tail..." -> "The Changing Ion Tail..."
    baslik = html.unescape(yazi["title"]["rendered"])
    baslik = baslik.split(" – ", 1)[-1]

    # Görsel: NASA boyutu adresteki ?w=... ile ayarlıyor
    gorsel = (yazi.get("featured_image_url") or "").split("?")[0]

    return {
        "tarih": yazi["date"][:10],
        "baslik": baslik,
        "aciklama": _aciklamayi_bul(icerik),
        "tur": "image" if gorsel else "video",
        "url": f"{gorsel}?w=1600&fit=clip" if gorsel else None,  # sayfada gösterilecek boyut
        "hd_url": gorsel or None,                                # tam çözünürlük
        "telif": _telifi_bul(icerik),
        "kaynak": yazi.get("link"),                              # NASA'daki orijinal sayfa
    }


def _html_temizle(parca: str) -> str:
    """HTML etiketlerini sil, &amp; gibi kodları çöz, fazla boşlukları topla."""
    metin = re.sub(r"<[^>]+>", " ", parca)
    metin = html.unescape(metin)
    metin = re.sub(r"\s+", " ", metin)
    return re.sub(r"\s+([.,;:!?)])", r"\1", metin).strip()   # "kelime ." -> "kelime."


def _aciklamayi_bul(icerik: str) -> str | None:
    # Açıklama <p class="... media-detail-hero__description"> içinde, "Explanation:" ile başlıyor
    bulunan = re.search(r'media-detail-hero__description">(.*?)</p>', icerik, re.S)
    if not bulunan:
        return None
    paragraf = bulunan.group(1).split("<br")[0]   # alttaki ekstra linkleri at
    return _html_temizle(paragraf).removeprefix("Explanation:").strip()


def _telifi_bul(icerik: str) -> str | None:
    # "Image Credit & Copyright: ..." kısmını bul, "Authors & editors" öncesinde kes
    bulunan = re.search(r"((?:Image|Video|Illustration) Credit.*?)Authors", _html_temizle(icerik), re.S)
    if not bulunan:
        return None
    return bulunan.group(1).split(":", 1)[-1].strip(" ;")
