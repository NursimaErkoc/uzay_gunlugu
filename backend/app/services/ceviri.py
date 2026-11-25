"""
Çeviri servisi: İngilizce metni Türkçeye çevirir.

Sırayla şunlara bakar:
  1) Hafızadaki önbellek          (en hızlı)
  2) Veritabanındaki çeviriler    (kalıcı: sunucu yeniden başlasa da kaybolmaz)
  3) DeepL (anahtar tanımlıysa; ayda 500 bin karakter ücretsiz, en kaliteli)
  4) Google Translate (ücretsiz, resmi olmayan uç nokta; Render'dan gelen istekleri engelliyor)
  5) MyMemory (son yedek; Render'da kotası başka sitelerle paylaşıldığı için çabuk doluyor)

Neden veritabanı? Render'ın ücretsiz sunucusu uyuyup uyanınca diski siliniyor. Çevirileri
sadece diskte tutunca her uyanışta yüzlerce metni baştan çevirtiyorduk; bu kadar çok istek
gelince ücretsiz servisler bizi engelliyor. Artık her metin ömründe BİR KEZ çevriliyor.

Çeviri tamamen başarısız olursa None döner ve site İngilizce metni gösterir (çökmez).
"""
import asyncio
import hashlib
import html
import re
from datetime import datetime, timezone

import httpx

from app import cache, db
from app.config import DEEPL_API_KEY, MYMEMORY_EPOSTA

GOOGLE_URL = "https://translate.googleapis.com/translate_a/single"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"
# Ücretsiz DeepL anahtarları ":fx" ile biter ve ayrı bir adres kullanır
DEEPL_URL = ("https://api-free.deepl.com" if DEEPL_API_KEY.endswith(":fx") else "https://api.deepl.com") + "/v2/translate"

# Aynı anda en fazla 5 çeviri isteği gitsin (servisler toplu isteği saldırı sanabilir)
_kapi = asyncio.Semaphore(5)

# Her servisin son hatası. /api/saglik bunu gösterir: canlı sitede sorunu görebilmek için.
son_hatalar: dict[str, str | None] = {"deepl": None, "google": None, "mymemory": None}


async def turkceye_cevir(metin: str | None) -> str | None:
    """Metni İngilizceden Türkçeye çevirir. Başarısız olursa None döner."""
    if not metin:
        return None

    # Uzun metinleri anahtar olarak kullanmak yerine kısa bir "parmak izi" (hash) üretiyoruz
    anahtar = hashlib.sha256(metin.encode("utf-8")).hexdigest()

    # 1) Hafıza
    kayitli = cache.getir(f"ceviri:{anahtar}")
    if kayitli is not None:
        return kayitli

    # 2) Veritabanı
    kayitli = _veritabanindan_oku(anahtar)
    if kayitli is None:
        # 3-5) Çeviri servisleri sırayla: biri başarısız olursa sonrakine geçilir
        async with _kapi:
            kayitli = await _deepl_ile(metin) or await _google_ile(metin) or await _mymemory_ile(metin)
        if kayitli is None:
            return None
        _veritabanina_yaz(anahtar, kayitli)

    cache.kaydet(f"ceviri:{anahtar}", kayitli, 7 * 24 * 60 * 60)
    return kayitli


# ---------------------------------------------------------------------
# Veritabanı
# ---------------------------------------------------------------------
def _veritabanindan_oku(anahtar: str) -> str | None:
    try:
        with db.baglan() as baglanti:
            satir = baglanti.execute("SELECT ceviri FROM ceviriler WHERE anahtar = ?", (anahtar,)).fetchone()
        return satir["ceviri"] if satir else None
    except Exception:
        return None   # veritabanına ulaşılamazsa çeviri servisine sorulur


def _veritabanina_yaz(anahtar: str, ceviri: str) -> None:
    try:
        with db.baglan() as baglanti:
            # ON CONFLICT DO NOTHING: aynı anahtar zaten varsa hata verme, geç
            baglanti.execute(
                "INSERT INTO ceviriler (anahtar, ceviri, olusturma) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                (anahtar, ceviri, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
            )
    except Exception:
        pass   # kaydedemezsek de çeviriyi kullanmaya devam ederiz


# ---------------------------------------------------------------------
# Çeviri servisleri
# ---------------------------------------------------------------------
async def _deepl_ile(metin: str) -> str | None:
    """DeepL resmi API'si. Anahtar yoksa hiç denenmez."""
    if not DEEPL_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=20) as istemci:
            cevap = await istemci.post(
                DEEPL_URL,
                headers={"Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"},
                json={"text": [metin], "source_lang": "EN", "target_lang": "TR"},
            )
        if cevap.status_code != 200:
            # 403: anahtar yanlış, 456: aylık kota doldu, 429: çok hızlı istek. (Anahtarı ASLA hataya yazma.)
            son_hatalar["deepl"] = f"HTTP {cevap.status_code}"
            return None
        sonuc = cevap.json()["translations"][0]["text"]
    except Exception as hata:
        son_hatalar["deepl"] = type(hata).__name__
        return None
    son_hatalar["deepl"] = None
    return sonuc or None


async def _google_ile(metin: str) -> str | None:
    parametreler = {"client": "gtx", "sl": "en", "tl": "tr", "dt": "t", "q": metin}
    try:
        async with httpx.AsyncClient(timeout=15) as istemci:
            # Uzun metinlerde GET adresi çok uzar, o yüzden POST ile gönderiyoruz
            cevap = await istemci.post(GOOGLE_URL, data=parametreler)
        if cevap.status_code != 200:
            son_hatalar["google"] = f"HTTP {cevap.status_code}"
            return None
        # Cevap iç içe listeler: [[["Çeviri cümle 1", "Original 1", ...], ...], ...]
        sonuc = "".join(cumle[0] for cumle in cevap.json()[0] if cumle[0])
    except Exception as hata:
        son_hatalar["google"] = type(hata).__name__
        return None
    son_hatalar["google"] = None
    return sonuc or None


async def _mymemory_ile(metin: str) -> str | None:
    """MyMemory tek seferde en fazla ~500 karakter çeviriyor; uzun metni cümle cümle parçalara bölüyoruz."""
    parcalar = _parcala(metin, 450)
    cevrilenler = []
    temel = {"langpair": "en|tr"}
    if MYMEMORY_EPOSTA:
        temel["de"] = MYMEMORY_EPOSTA   # kota bu adrese bağlansın (günde 50.000 karakter)
    try:
        async with httpx.AsyncClient(timeout=20) as istemci:
            for parca in parcalar:
                cevap = await istemci.get(MYMEMORY_URL, params={**temel, "q": parca})
                try:
                    veri = cevap.json()
                except ValueError:
                    veri = {}
                # MyMemory hata durumunu (ör. günlük kota doldu) cevabın içinde bildiriyor
                if cevap.status_code != 200 or str(veri.get("responseStatus")) != "200" or veri.get("quotaFinished"):
                    ayrinti = str(veri.get("responseDetails") or cevap.text)[:160]
                    son_hatalar["mymemory"] = (f"HTTP {cevap.status_code}, durum {veri.get('responseStatus')}: {ayrinti}")
                    return None
                cevrilenler.append(html.unescape(veri["responseData"]["translatedText"]))
    except Exception as hata:
        son_hatalar["mymemory"] = type(hata).__name__
        return None
    son_hatalar["mymemory"] = None
    return " ".join(cevrilenler)


def _parcala(metin: str, en_fazla: int) -> list[str]:
    """Metni cümle sınırlarından, her biri en_fazla karakteri geçmeyecek parçalara böler."""
    cumleler = re.split(r"(?<=[.!?])\s+", metin.strip())
    parcalar, simdiki = [], ""
    for cumle in cumleler:
        while len(cumle) > en_fazla:            # tek başına çok uzun cümle: zorla böl
            parcalar.append(cumle[:en_fazla])
            cumle = cumle[en_fazla:]
        if simdiki and len(simdiki) + 1 + len(cumle) > en_fazla:
            parcalar.append(simdiki)
            simdiki = cumle
        else:
            simdiki = f"{simdiki} {cumle}".strip()
    if simdiki:
        parcalar.append(simdiki)
    return parcalar
