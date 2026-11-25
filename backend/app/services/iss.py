"""
ISS Şu An Nerede + Şu An Uzayda Kimler Var

1) ISS'in konumu HESAPLANIR (dış servise her saniye sormuyoruz):
   - CelesTrak, ISS'in yörüngesini "TLE" (Two-Line Element) denen iki satırlık bir metinle yayınlar:
       1 25544U 98067A   26328.88031537  .00004718  00000+0  91905-4 0  9993
       2 25544  51.6319 224.8621 0007433  61.9046 298.2693 15.49577477596662
     İçinde yörüngenin eğimi, şekli, istasyonun günde kaç tur attığı (15.49) gibi bilgiler var.
   - sgp4 kütüphanesi bu bilgiyle istasyonun herhangi bir andaki konumunu hesaplar.
   - TLE birkaç günde bir eskir (atmosfer sürtünmesi yörüngeyi yavaşça değiştirir), o yüzden
     6 saatte bir yenisini indiriyoruz.

2) Uzaydaki insanlar: Launch Library 2 (takvimde de kullandığımız kaynak).

Koordinat dönüşümü hakkında: sgp4 konumu Dünya'nın merkezine göre, uzaya sabitlenmiş bir eksen
takımında verir (TEME). Ama Dünya kendi etrafında dönüyor! Haritada göstermek için bu konumu
Dünya ile birlikte dönen eksenlere çeviriyor (GMST açısı kadar döndürme), sonra enlem/boylama
dönüştürüyoruz.
"""
import math
from datetime import datetime, timedelta, timezone

import astronomy as A
import httpx
from sgp4.api import Satrec, jday

from app import cache
from app.services import events

ISS_NUMARASI = 25544            # ISS'in uydu katalog numarası

# Yörünge verisi kaynakları: sırayla denenir, ilk cevap veren kullanılır.
# (CelesTrak, Render gibi bulut sunuculardan gelen istekleri bazen yanıtlamıyor.)
#   (ad, adres, biçim)  biçim: "metin" = iki satır düz metin, "json" = {"line1": ..., "line2": ...}
TLE_KAYNAKLARI = [
    ("CelesTrak", f"https://celestrak.org/NORAD/elements/gp.php?CATNR={ISS_NUMARASI}&FORMAT=TLE", "metin"),
    ("ARISS", "https://live.ariss.org/iss.txt", "metin"),
    ("wheretheiss.at", f"https://api.wheretheiss.at/v1/satellites/{ISS_NUMARASI}/tles", "json"),
    ("TLE API", f"https://tle.ivanstanojevic.me/api/tle/{ISS_NUMARASI}", "json"),
]

# /api/saglik'te gösterilir: hangi kaynak kullanıldı, son hatalar neydi
durum: dict = {"tle_kaynagi": None, "tle_hatalari": {}}
DUNYA_YARICAPI = 6378.137       # km (ekvatorda)
BASIKLIK = 1 / 298.257223563    # Dünya tam küre değil, kutuplardan hafifçe basık (WGS84 modeli)
AU_KM = 149_597_870.7           # 1 astronomik birim (Dünya-Güneş uzaklığı) km cinsinden


class IssHatasi(Exception):
    """Yörünge verisi alınamadı."""


# =====================================================================
# Yörünge verisi (TLE)
# =====================================================================
def tle_ayikla(metin_ya_da_json, bicim: str) -> tuple[str, str]:
    """Kaynağın cevabından TLE'nin iki satırını çıkarır. Bulamazsa ValueError."""
    if bicim == "json":
        satir1, satir2 = metin_ya_da_json.get("line1", ""), metin_ya_da_json.get("line2", "")
    else:
        satirlar = [s.strip() for s in metin_ya_da_json.strip().splitlines()]
        satir1 = next((s for s in satirlar if s.startswith("1 ")), "")
        satir2 = next((s for s in satirlar if s.startswith("2 ")), "")
    # Doğru uydu mu? Her iki satırda da katalog numarası (25544) 3. karakterden başlar.
    if not (satir1.startswith(f"1 {ISS_NUMARASI}") and satir2.startswith(f"2 {ISS_NUMARASI}")):
        raise ValueError("Cevapta ISS'in yörünge verisi yok")
    return satir1.strip(), satir2.strip()


async def tle_getir() -> tuple[str, str]:
    """
    ISS'in güncel TLE'sini (iki satır) getirir.
      1) 6 saatlik önbellekte varsa onu kullan
      2) Yoksa kaynakları sırayla dene
      3) Hiçbiri cevap vermezse son 7 gün içinde alınmış eski TLE'yi kullan
         (birkaç günlük TLE de konumu oldukça iyi hesaplar; hiç göstermemekten iyidir)
    """
    kayitli = cache.getir("iss:tle")
    if kayitli is not None:
        return tuple(kayitli)

    async with httpx.AsyncClient(timeout=10, headers=events.ISTEK_BASLIKLARI) as istemci:
        for ad, adres, bicim in TLE_KAYNAKLARI:
            try:
                cevap = await istemci.get(adres)
                cevap.raise_for_status()
                satirlar = tle_ayikla(cevap.json() if bicim == "json" else cevap.text, bicim)
            except (httpx.HTTPError, ValueError) as hata:
                durum["tle_hatalari"][ad] = type(hata).__name__
                continue
            durum["tle_hatalari"].pop(ad, None)
            durum["tle_kaynagi"] = ad
            cache.kaydet("iss:tle", list(satirlar), 6 * 60 * 60, kalici=True)
            cache.kaydet("iss:tle:yedek", list(satirlar), 7 * 24 * 60 * 60, kalici=True)
            return satirlar

    yedek = cache.getir("iss:tle:yedek")
    if yedek is not None:
        durum["tle_kaynagi"] = "eski kayıt (hiçbir kaynak cevap vermedi)"
        return tuple(yedek)
    raise IssHatasi("ISS yörünge verisi hiçbir kaynaktan alınamadı")


# =====================================================================
# Konum hesabı
# =====================================================================
def _gmst(jd: float) -> float:
    """
    Greenwich Yıldız Zamanı (radyan): Dünya'nın, uzaydaki sabit eksenlere göre ne kadar döndüğü.
    Standart formül (IAU 1982). jd = Jülyen günü (gökbilimcilerin kullandığı sürekli gün sayacı).
    """
    t = (jd - 2451545.0) / 36525   # 1 Ocak 2000'den bu yana geçen yüzyıl
    saniye = 67310.54841 + (876600 * 3600 + 8640184.812866) * t + 0.093104 * t**2 - 6.2e-6 * t**3
    return math.radians((saniye % 86400) / 240)


def _enlem_boylam(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Dünya ile dönen eksenlerdeki konum (km) -> enlem, boylam (derece), yükseklik (km)."""
    e2 = BASIKLIK * (2 - BASIKLIK)
    p = math.hypot(x, y)
    enlem = math.atan2(z, p * (1 - e2))
    for _ in range(5):   # basık Dünya için enlem birkaç adımda yaklaşarak bulunur
        n = DUNYA_YARICAPI / math.sqrt(1 - e2 * math.sin(enlem) ** 2)
        yukseklik = p / math.cos(enlem) - n
        enlem = math.atan2(z, p * (1 - e2 * n / (n + yukseklik)))
    return math.degrees(enlem), math.degrees(math.atan2(y, x)), yukseklik


def _hesapla(uydu: Satrec, an: datetime) -> dict:
    jd, kesir = jday(an.year, an.month, an.day, an.hour, an.minute, an.second + an.microsecond / 1e6)
    hata, r, v = uydu.sgp4(jd, kesir)    # r: konum (km), v: hız (km/s)
    if hata:
        raise IssHatasi(f"Yörünge hesaplanamadı (sgp4 hata kodu {hata})")

    # Uzaya sabit eksenlerden Dünya ile dönen eksenlere
    aci = _gmst(jd + kesir)
    x = r[0] * math.cos(aci) + r[1] * math.sin(aci)
    y = -r[0] * math.sin(aci) + r[1] * math.cos(aci)
    enlem, boylam, yukseklik = _enlem_boylam(x, y, r[2])
    return {"r": r, "v": v, "enlem": enlem, "boylam": boylam, "yukseklik": yukseklik}


def _gunes_durumu(r: tuple, an: datetime) -> tuple[bool, bool]:
    """
    (ISS Güneş ışığında mı?, ISS'in altındaki bölgede gündüz mü?)
    Dünya'nın gölgesini basitçe bir silindir gibi düşünüyoruz: ISS, Güneş'in tam ters tarafında
    ve Dünya'nın yarıçapı kadar bir silindirin içindeyse gölgededir.
    """
    t = A.Time.Make(an.year, an.month, an.day, an.hour, an.minute, an.second)
    g = A.GeoVector(A.Body.Sun, t, True)
    gunes = (g.x * AU_KM, g.y * AU_KM, g.z * AU_KM)
    gunes_uzunluk = math.sqrt(sum(c * c for c in gunes))
    birim = [c / gunes_uzunluk for c in gunes]

    izdusum = sum(a * b for a, b in zip(r, birim))   # ISS'in Güneş yönündeki bileşeni
    merkeze_uzaklik = math.sqrt(sum(c * c for c in r))
    eksene_uzaklik = math.sqrt(max(merkeze_uzaklik**2 - izdusum**2, 0))
    golgede = izdusum < 0 and eksene_uzaklik < DUNYA_YARICAPI
    return not golgede, izdusum > 0


async def iss_konumu(simdi: datetime | None = None) -> dict:
    """ISS'in şu anki konumu ve -45 dk ile +90 dk arasındaki yörünge izi (bir tur ≈ 92 dk)."""
    simdi = simdi or datetime.now(timezone.utc)
    satir1, satir2 = await tle_getir()
    uydu = Satrec.twoline2rv(satir1, satir2)

    su_an = _hesapla(uydu, simdi)
    hiz = math.sqrt(sum(c * c for c in su_an["v"])) * 3600   # km/s -> km/sa
    gunes_isiginda, altta_gunduz = _gunes_durumu(su_an["r"], simdi)

    iz = []
    for dakika in range(-45, 91):
        nokta = _hesapla(uydu, simdi + timedelta(minutes=dakika))
        iz.append([round(nokta["enlem"], 3), round(nokta["boylam"], 3)])

    # TLE'nin ne zaman ölçüldüğü (yörünge verisinin yaşı)
    tle_zamani = datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(
        days=uydu.jdsatepoch + uydu.jdsatepochF - 2451545.0)

    return {
        "zaman": simdi.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "enlem": round(su_an["enlem"], 4),
        "boylam": round(su_an["boylam"], 4),
        "yukseklik_km": round(su_an["yukseklik"], 1),
        "hiz_kmsa": round(hiz),
        "gunes_isiginda": gunes_isiginda,
        "altta_gunduz": altta_gunduz,
        "iz": iz,                 # [enlem, boylam] listesi, dakikada bir
        "iz_baslangic_dk": -45,   # iz[45] = şu an
        "tle_zamani": tle_zamani.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# =====================================================================
# Şu an uzayda kimler var
# =====================================================================
ISTASYON_ADLARI = {
    "International Space Station": "Uluslararası Uzay İstasyonu (ISS)",
    "Tiangong space station": "Tiangong Uzay İstasyonu (Çin)",
}
GOREVLER = {"Commander": "Komutan", "Flight Engineer": "Uçuş Mühendisi", "Operator": "Operatör",
            "Pilot": "Pilot", "Mission Specialist": "Görev Uzmanı", "Payload Specialist": "Yük Uzmanı",
            "Spaceflight Participant": "Uzay Turisti"}
ULKELER = {"US": "ABD", "RU": "Rusya", "CN": "Çin", "JP": "Japonya", "CA": "Kanada", "DE": "Almanya",
           "FR": "Fransa", "IT": "İtalya", "GB": "Birleşik Krallık", "TR": "Türkiye", "IN": "Hindistan",
           "AE": "BAE", "SA": "Suudi Arabistan", "ES": "İspanya", "NL": "Hollanda", "BE": "Belçika",
           "DK": "Danimarka", "SE": "İsveç", "PL": "Polonya", "HU": "Macaristan", "PK": "Pakistan",
           "HK": "Hong Kong", "KZ": "Kazakistan", "BY": "Belarus", "IL": "İsrail", "AU": "Avustralya"}


def _gun_sayisi(iso_sure: str | None) -> int | None:
    """'P224DT13H57M38S' (ISO 8601 süre) -> 224 gün."""
    if not iso_sure or not iso_sure.startswith("P") or "D" not in iso_sure:
        return 0 if iso_sure else None
    try:
        return int(iso_sure[1:iso_sure.index("D")])
    except ValueError:
        return None


def _insan_mi(astronot: dict) -> bool:
    """LL2 listesinde Starman (Tesla'daki manken) ve Laika (köpek) da 'uzayda' görünüyor; onları ayıkla."""
    tur = ((astronot.get("type") or {}).get("name") or "").lower()
    return not astronot.get("date_of_death") and "non-human" not in tur and astronot.get("name") != "Starman"


async def uzaydakiler() -> dict:
    """Şu an uzayda bulunan insanlar, bulundukları istasyona göre gruplanmış."""
    astronotlar = await events._ll2_getir("astronauts", {"in_space": "true", "limit": 50})
    try:
        ekipler = await events._ll2_getir("expeditions", {"is_active": "true", "mode": "detailed", "limit": 10})
    except httpx.HTTPError:
        ekipler = []   # istasyon bilgisi alınamazsa herkes tek listede görünür

    # Astronot kimliği -> (istasyon, görev)
    nerede = {}
    for ekip in ekipler:
        istasyon = (ekip.get("spacestation") or {}).get("name", "")
        for uye in ekip.get("crew") or []:
            nerede[uye["astronaut"]["id"]] = (istasyon, (uye.get("role") or {}).get("role"))

    gruplar: dict[str, list] = {}
    for a in filter(_insan_mi, astronotlar):
        istasyon, gorev = nerede.get(a["id"], (None, None))
        grup = ISTASYON_ADLARI.get(istasyon, istasyon) if istasyon else "Yolda ya da başka bir araçta"
        ulke = (a.get("nationality") or [{}])[0] if isinstance(a.get("nationality"), list) else {}
        gruplar.setdefault(grup, []).append({
            "ad": a["name"],
            "ajans": (a.get("agency") or {}).get("abbrev"),
            "ulke": ULKELER.get(ulke.get("alpha_2_code"), ulke.get("name")),
            "gorev": GOREVLER.get(gorev, gorev),
            "uzayda_gun": _gun_sayisi(a.get("time_in_space")),
            "ucus_sayisi": a.get("flights_count"),
            "fotograf": (a.get("image") or {}).get("thumbnail_url"),
            "wiki": a.get("wiki"),
        })

    # ISS önce, sonra Tiangong, en son diğerleri
    sira = list(ISTASYON_ADLARI.values())
    liste = sorted(gruplar.items(), key=lambda g: sira.index(g[0]) if g[0] in sira else len(sira))
    return {
        "toplam": sum(len(kisiler) for _, kisiler in liste),
        "gruplar": [{"ad": ad, "kisiler": kisiler} for ad, kisiler in liste],
    }
