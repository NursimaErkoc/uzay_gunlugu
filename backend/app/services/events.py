"""
Ayın uzay olayları: üç farklı kaynağı tek bir takvimde birleştirir.

1) Gökyüzü olayları (dolunay, tutulma, ekinoks, gezegenler) -> astronomy-engine ile HESAPLANIR
   (internet gerekmez, binlerce yıl ileri/geri doğru sonuç verir)
2) Meteor yağmurları -> kendi meteor_showers.json dosyamız (her yıl aynı tarihler)
3) Roket fırlatmaları ve uzay etkinlikleri -> Launch Library 2 API
   Dokümantasyon: https://ll.thespacedevs.com/docs/
   DİKKAT: Ücretsiz kullanımda saatte 15 istek sınırı var -> önbellek şart!

Her olay aynı biçimde bir sözlük (dict) olur, böylece frontend hepsini aynı şekilde gösterir:
    {"id", "tur", "ikon", "baslik", "tarih", "kesinlik", "aciklama", "alt_bilgi", "gorsel", "link", ...}
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone

import astronomy as A
import httpx

from app import cache
from app.config import PROJE_KLASORU
from app.services import ceviri

LL2_URL = "https://ll.thespacedevs.com/2.3.0"
ISTEK_BASLIKLARI = {"User-Agent": "UzayGunlugu/0.1 (ogrenci projesi)"}

TURKIYE = timezone(timedelta(hours=3))           # Türkiye 2016'dan beri sürekli UTC+3
ANKARA = A.Observer(39.93, 32.86, 900)           # enlem, boylam, rakım (m)

with open(PROJE_KLASORU / "backend" / "data" / "meteor_showers.json", encoding="utf-8") as _dosya:
    METEOR_YAGMURLARI = json.load(_dosya)

GEZEGEN_ADLARI = {
    A.Body.Mercury: "Merkür", A.Body.Venus: "Venüs", A.Body.Mars: "Mars",
    A.Body.Jupiter: "Jüpiter", A.Body.Saturn: "Satürn", A.Body.Uranus: "Uranüs", A.Body.Neptune: "Neptün",
}


# =====================================================================
# Yardımcılar
# =====================================================================
def _ay_araligi(yil: int, ay: int) -> tuple[datetime, datetime]:
    """Ayın başlangıcı ve bir sonraki ayın başlangıcı (Türkiye saatine göre, UTC'ye çevrilmiş)."""
    bas = datetime(yil, ay, 1, tzinfo=TURKIYE)
    son = datetime(yil + (ay == 12), ay % 12 + 1, 1, tzinfo=TURKIYE)
    return bas.astimezone(timezone.utc), son.astimezone(timezone.utc)


def _astro_zaman(dt: datetime) -> A.Time:
    """Python datetime -> astronomy-engine zamanı."""
    return A.Time.Make(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


def _olay(tur, ikon, baslik, zaman, aciklama, kesinlik="dakika", **ekstra) -> dict:
    """Tüm olaylar için ortak biçim."""
    tarih = str(zaman) if isinstance(zaman, A.Time) else zaman
    return {
        "id": f"{tur}:{baslik}:{tarih[:10]}",
        "tur": tur,               # "gokyuzu" | "firlatma" | "etkinlik"
        "ikon": ikon,
        "baslik": baslik,
        "tarih": tarih,           # ISO biçimi, UTC: "2026-12-24T01:28:45Z"
        "kesinlik": kesinlik,     # "dakika" | "saat" | "gun" | "ay"
        "aciklama": aciklama,
        "alt_bilgi": None,
        "gorsel": None,
        "link": None,
        **ekstra,
    }


def _yuzde(oran: float) -> str:
    return f"%{round(oran * 100)}"


# =====================================================================
# 1) Gökyüzü olayları (hesaplama)
# =====================================================================
def gokyuzu_olaylari(yil: int, ay: int) -> list[dict]:
    bas, son = _ay_araligi(yil, ay)
    t_bas, t_son = _astro_zaman(bas), _astro_zaman(son)

    def bu_ayda(t: A.Time) -> bool:
        return t_bas.ut <= t.ut < t_son.ut

    olaylar = []

    # --- Dolunay ve Yeni Ay ---
    evre = A.SearchMoonQuarter(t_bas)
    while evre.time.ut < t_son.ut:
        if evre.quarter == 2:
            olaylar.append(_olay("gokyuzu", "dolunay", "Dolunay", evre.time,
                                 "Ay, Dünya'nın Güneş'e göre tam karşısında ve bütün gece gökyüzünde."))
        elif evre.quarter == 0:
            olaylar.append(_olay("gokyuzu", "yeni-ay", "Yeni Ay", evre.time,
                                 "Ay görünmez. Yıldız, gezegen ve galaksi gözlemi için ayın en karanlık geceleri."))
        evre = A.NextMoonQuarter(evre)

    # --- Ekinoks ve Gündönümleri ---
    mevsim = A.Seasons(yil)
    for zaman, baslik, aciklama in [
        (mevsim.mar_equinox, "İlkbahar Ekinoksu", "Gece ve gündüz yaklaşık eşit. Kuzey Yarımküre'de ilkbahar başlıyor."),
        (mevsim.jun_solstice, "Yaz Gündönümü", "Kuzey Yarımküre'de yılın en uzun günü. Yaz başlıyor."),
        (mevsim.sep_equinox, "Sonbahar Ekinoksu", "Gece ve gündüz yaklaşık eşit. Kuzey Yarımküre'de sonbahar başlıyor."),
        (mevsim.dec_solstice, "Kış Gündönümü", "Kuzey Yarımküre'de yılın en uzun gecesi. Bundan sonra günler uzamaya başlar."),
    ]:
        if bu_ayda(zaman):
            olaylar.append(_olay("gokyuzu", "mevsim", baslik, zaman, aciklama))

    # --- Ay tutulmaları ---
    tutulma = A.SearchLunarEclipse(t_bas)
    while tutulma.peak.ut < t_son.ut:
        tur = {A.EclipseKind.Penumbral: "Yarıgölge", A.EclipseKind.Partial: "Parçalı",
               A.EclipseKind.Total: "Tam"}[tutulma.kind]
        # Tutulma anında Ay Ankara'dan ufkun üstünde mi?
        ekvator = A.Equator(A.Body.Moon, tutulma.peak, ANKARA, True, True)
        ufuk = A.Horizon(tutulma.peak, ANKARA, ekvator.ra, ekvator.dec, A.Refraction.Normal)
        gorunur = ufuk.altitude > 0
        aciklama = ("Türkiye'den görülebilir (tutulma anında Ay ufkun üstünde)." if gorunur
                    else "Türkiye'den görülemeyecek (tutulma anında Ay ufkun altında).")
        if tutulma.kind == A.EclipseKind.Penumbral:
            aciklama += " Yarıgölge tutulmasında Ay sadece hafifçe kararır, çıplak gözle fark etmek zordur."
        olaylar.append(_olay("gokyuzu", "ay-tutulmasi", f"{tur} Ay Tutulması", tutulma.peak, aciklama,
                             turkiyeden_gorunur=gorunur))
        tutulma = A.NextLunarEclipse(tutulma.peak)

    # --- Güneş tutulmaları ---
    tutulma = A.SearchGlobalSolarEclipse(t_bas)
    while tutulma.peak.ut < t_son.ut:
        tur = {A.EclipseKind.Partial: "Parçalı", A.EclipseKind.Annular: "Halkalı",
               A.EclipseKind.Total: "Tam"}.get(tutulma.kind, "Hibrit")
        # Ankara'dan görülüyor mu? Yerel tutulma aramasının sonucu aynı güne denk geliyorsa evet.
        yerel = A.SearchLocalSolarEclipse(tutulma.peak.AddDays(-1), ANKARA)
        gorunur = abs(yerel.peak.time.ut - tutulma.peak.ut) < 0.5
        if gorunur:
            aciklama = (f"Ankara'dan parçalı olarak görülecek: Güneş yaklaşık {_yuzde(yerel.obscuration)} oranında kapanacak. "
                        "Güneş'e asla korumasız gözle veya normal güneş gözlüğüyle bakma!")
        else:
            aciklama = "Türkiye'den görülemeyecek. Canlı yayınlardan izlenebilir."
        olaylar.append(_olay("gokyuzu", "gunes-tutulmasi", f"{tur} Güneş Tutulması", tutulma.peak, aciklama,
                             turkiyeden_gorunur=gorunur))
        tutulma = A.NextGlobalSolarEclipse(tutulma.peak)

    # --- Dış gezegenlerin karşı konumu (en parlak ve en iyi gözlem zamanı) ---
    for gezegen in [A.Body.Mars, A.Body.Jupiter, A.Body.Saturn, A.Body.Uranus, A.Body.Neptune]:
        zaman = A.SearchRelativeLongitude(gezegen, 0, t_bas)
        if bu_ayda(zaman):
            ad = GEZEGEN_ADLARI[gezegen]
            ek = " Uranüs ve Neptün için dürbün veya teleskop gerekir." if gezegen in (A.Body.Uranus, A.Body.Neptune) else ""
            olaylar.append(_olay("gokyuzu", "gezegen", f"{ad} Karşı Konumda", zaman,
                                 f"{ad} Dünya'ya en yakın ve en parlak döneminde. Gün batımında doğar, "
                                 f"bütün gece görülebilir. Gözlem için yılın en iyi zamanı!{ek}"))

    # --- Venüs ve Merkür'ün en büyük uzanımı (Güneş'ten en uzak göründüğü an) ---
    for gezegen in [A.Body.Venus, A.Body.Mercury]:
        uzanim = A.SearchMaxElongation(gezegen, t_bas)
        while uzanim.time.ut < t_son.ut:
            ad = GEZEGEN_ADLARI[gezegen]
            ne_zaman = ("sabahları gün doğumundan önce doğu ufkunda" if uzanim.visibility == A.Visibility.Morning
                        else "akşamları gün batımından sonra batı ufkunda")
            olaylar.append(_olay("gokyuzu", "uzanim", f"{ad} En Büyük Uzanımda", uzanim.time,
                                 f"{ad}, Güneş'ten en uzak göründüğü noktada ({round(uzanim.elongation)}°). "
                                 f"Onu {ne_zaman} görmek için en iyi zaman."))
            uzanim = A.SearchMaxElongation(gezegen, uzanim.time.AddDays(1))

    # --- Meteor yağmurları ---
    for yagmur in METEOR_YAGMURLARI:
        if yagmur["tepe_ay"] != ay:
            continue
        tepe = A.Time.Make(yil, ay, yagmur["tepe_gun"], 0, 0, 0)
        ay_isigi = A.Illumination(A.Body.Moon, tepe).phase_fraction   # 0 = karanlık, 1 = dolunay
        if ay_isigi < 0.35:
            ay_notu = f"Ay ışığı az ({_yuzde(ay_isigi)}), bu yıl gözlem koşulları iyi."
        elif ay_isigi > 0.65:
            ay_notu = f"Ay oldukça aydınlık ({_yuzde(ay_isigi)}), sönük meteorlar görünmeyebilir."
        else:
            ay_notu = f"Ay {_yuzde(ay_isigi)} aydınlık."
        olaylar.append(_olay(
            "gokyuzu", "meteor", f"{yagmur['ad']} Meteor Yağmuru", tepe,
            f"Tepe gecesi: ideal koşullarda saatte ~{yagmur['saatlik']} meteor. Kaynağı: {yagmur['kaynak']}. "
            f"{ay_notu} En iyi gözlem gece yarısından sonra, şehir ışıklarından uzakta.",
            kesinlik="gun",
        ))

    return olaylar


# =====================================================================
# 2) Fırlatmalar ve uzay etkinlikleri (Launch Library 2)
# =====================================================================
# LL2 durum kodu -> (ekranda yazılacak metin, renk için kod)
# Renk ve görünüm kararı sayfaya (CSS) ait; backend sadece "ne durumda" bilgisini verir.
DURUMLAR = {
    "Go": ("Hazır", "hazir"),
    "TBD": ("Tarih belirsiz", "belirsiz"),
    "TBC": ("Teyit bekleniyor", "belirsiz"),
    "Hold": ("Beklemede", "beklemede"),
    "Success": ("Başarılı", "basarili"),
    "Failure": ("Başarısız", "basarisiz"),
    "Partial Failure": ("Kısmen başarısız", "kismen"),
    "In Flight": ("Uçuşta", "ucusta"),
}
ETKINLIK_TURLERI = {
    "EVA": "Uzay Yürüyüşü", "Static Fire": "Motor Testi", "Press Event": "Basın Toplantısı",
    "Spacecraft Docking": "Kenetlenme", "Spacecraft Undocking": "Ayrılma", "Spacecraft Landing": "İniş",
    "Spacecraft Capture": "Yakalama", "Spacecraft Release": "Serbest Bırakma", "Moon Landing": "Ay'a İniş",
    "Celestial Event": "Gök Olayı", "Test Flight": "Test Uçuşu", "Spacecraft Event": "Uzay Aracı Etkinliği",
    "Flyby": "Yakın Geçiş", "Orbital Insertion": "Yörüngeye Giriş", "Abort Test": "Acil Durum Testi",
}


def _kesinlik(kisaltma: str | None) -> str:
    """LL2'nin kesinlik kodunu bizimkine çevir. Örneğin 'DAY' -> 'gun'."""
    return {"SEC": "dakika", "MIN": "dakika", "HR": "saat", "DAY": "gun"}.get(kisaltma or "", "ay")


async def _ll2_getir(yol: str, parametreler: dict) -> list[dict]:
    """
    Launch Library'den veri çeker. Saatte sadece 15 istek hakkımız olduğu için
    cevabı 6 saat DİSKTE saklıyoruz: sunucu yeniden başlasa bile tekrar sormayız.
    """
    onbellek_anahtari = f"ll2:{yol}:{json.dumps(parametreler, sort_keys=True)}"
    kayitli = cache.getir(onbellek_anahtari)
    if kayitli is not None:
        return kayitli

    async with httpx.AsyncClient(timeout=30, headers=ISTEK_BASLIKLARI) as istemci:
        cevap = await istemci.get(f"{LL2_URL}/{yol}/", params=parametreler)
    cevap.raise_for_status()   # 429 (istek sınırı) vb. durumlarda hata fırlatır
    sonuc = cevap.json()["results"]
    cache.kaydet(onbellek_anahtari, sonuc, 6 * 60 * 60, kalici=True)
    return sonuc


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


async def firlatmalar(yil: int, ay: int) -> list[dict]:
    bas, son = _ay_araligi(yil, ay)
    ham = await _ll2_getir("launches", {
        "net__gte": _iso(bas), "net__lt": _iso(son), "ordering": "net", "limit": 100, "mode": "normal",
    })
    olaylar = []
    for f in ham:
        gorev = f.get("mission") or {}
        roket = f["rocket"]["configuration"]["full_name"]
        firma = (f.get("launch_service_provider") or {}).get("name", "")
        yer = f["pad"]["location"]["name"]
        durum_metni, durum_kodu = DURUMLAR.get(f["status"]["abbrev"], (f["status"]["name"], "belirsiz"))
        olay = _olay(
            "firlatma", "roket", gorev.get("name") or f["name"], f["net"], gorev.get("description"),
            kesinlik=_kesinlik((f.get("net_precision") or {}).get("abbrev")),
            durum=durum_metni,
            durum_kodu=durum_kodu,
            starlink="Starlink" in f["name"],
        )
        olay["id"] = f"firlatma:{f['id']}"
        olay["alt_bilgi"] = f"{roket} · {firma} · {yer}"
        olay["gorsel"] = (f.get("image") or {}).get("thumbnail_url")
        if f.get("vid_urls"):
            olay["link"] = f["vid_urls"][0]["url"]
        olaylar.append(olay)
    return olaylar


async def uzay_etkinlikleri(yil: int, ay: int) -> list[dict]:
    bas, son = _ay_araligi(yil, ay)
    ham = await _ll2_getir("events", {
        "date__gte": _iso(bas), "date__lt": _iso(son), "ordering": "date", "limit": 100,
    })
    olaylar = []
    for e in ham:
        tur = e["type"]["name"]
        olay = _olay(
            "etkinlik", "uydu", e["name"], e["date"], e.get("description"),
            kesinlik=_kesinlik((e.get("date_precision") or {}).get("abbrev")) if e.get("date_precision") else "dakika",
        )
        olay["id"] = f"etkinlik:{e['id']}"
        olay["alt_bilgi"] = " · ".join(x for x in [ETKINLIK_TURLERI.get(tur, tur), e.get("location")] if x)
        olay["gorsel"] = (e.get("image") or {}).get("thumbnail_url")
        if e.get("vid_urls"):
            olay["link"] = e["vid_urls"][0]["url"]
        olaylar.append(olay)
    return olaylar


# =====================================================================
# 3) Hepsini birleştir
# =====================================================================
async def ayin_olaylari(yil: int, ay: int) -> dict:
    onbellek_anahtari = f"olaylar:{yil}-{ay:02d}"
    kayitli = cache.getir(onbellek_anahtari)
    if kayitli is not None:
        return kayitli

    gokyuzu = gokyuzu_olaylari(yil, ay)

    # İki LL2 isteğini aynı anda gönder. return_exceptions=True: biri hata verirse
    # diğeri yine de gelsin (hata, sonuç yerine bir Exception nesnesi olarak döner).
    sonuclar = await asyncio.gather(firlatmalar(yil, ay), uzay_etkinlikleri(yil, ay), return_exceptions=True)
    eksik = []
    for i, ad in enumerate(["fırlatmalar", "uzay etkinlikleri"]):
        if isinstance(sonuclar[i], Exception):
            eksik.append(ad)
            sonuclar[i] = []
    firlatma_listesi, etkinlik_listesi = sonuclar

    # İngilizce açıklamaları (ve etkinlik adlarını) Türkçeye çevir
    disaridan = firlatma_listesi + etkinlik_listesi
    cevirmeler = await asyncio.gather(*(ceviri.turkceye_cevir(o["aciklama"]) for o in disaridan))
    eksik_ceviri = False
    for olay, tr in zip(disaridan, cevirmeler):
        if olay["aciklama"] and not tr:
            eksik_ceviri = True
        olay["aciklama_en"] = olay["aciklama"]
        olay["aciklama"] = tr or olay["aciklama"]
    adlar = await asyncio.gather(*(ceviri.turkceye_cevir(o["baslik"]) for o in etkinlik_listesi))
    for olay, tr in zip(etkinlik_listesi, adlar):
        if not tr:
            eksik_ceviri = True
        olay["baslik"] = tr or olay["baslik"]

    hepsi = sorted(gokyuzu + firlatma_listesi + etkinlik_listesi, key=lambda o: o["tarih"])
    sonuc = {"ay": f"{yil}-{ay:02d}", "olaylar": hepsi, "eksik": eksik}

    # Her şey tam geldiyse 6 saat sakla. Bir kaynak alınamadıysa ya da bazı çeviriler
    # başarısız olduysa kısa sakla ki birkaç dakika sonra tekrar denensin.
    # (Başarılı çeviriler ve LL2 cevapları zaten ayrıca diskte saklı; tekrar denemek ucuz.)
    if eksik:
        sure = 10 * 60
    elif eksik_ceviri:
        sure = 5 * 60
    else:
        sure = 6 * 60 * 60
    cache.kaydet(onbellek_anahtari, sonuc, sure)
    return sonuc
