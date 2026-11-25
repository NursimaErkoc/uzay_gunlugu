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
    return {"r": r, "v": v, "dunya_xyz": (x, y, r[2]), "gmst": aci,
            "enlem": enlem, "boylam": boylam, "yukseklik": yukseklik}


def _astro_zaman(an: datetime) -> A.Time:
    return A.Time.Make(an.year, an.month, an.day, an.hour, an.minute, an.second + an.microsecond / 1e6)


def _gunes_yonu(an: datetime) -> list[float]:
    """Dünya'nın merkezinden Güneş'e doğru birim vektör (uzaya sabit eksenlerde, sgp4 ile aynı)."""
    g = A.GeoVector(A.Body.Sun, _astro_zaman(an), True)
    uzunluk = math.sqrt(g.x**2 + g.y**2 + g.z**2)
    return [g.x / uzunluk, g.y / uzunluk, g.z / uzunluk]


def _gunes_durumu(r: tuple, an: datetime) -> tuple[bool, bool]:
    """
    (ISS Güneş ışığında mı?, ISS'in altındaki bölgede gündüz mü?)
    Dünya'nın gölgesini basitçe bir silindir gibi düşünüyoruz: ISS, Güneş'in tam ters tarafında
    ve Dünya'nın yarıçapı kadar bir silindirin içindeyse gölgededir.
    """
    birim = _gunes_yonu(an)
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
# ISS'i Gör: gözlemcinin bulunduğu yerden görünür geçişler
# =====================================================================
KABA_ADIM = 30         # saniye: ISS ufkun üstüne çıktı mı diye bu aralıkla bakılır
INCE_ADIM = 10         # saniye: ufkun üstündeyken bu aralıkla ayrıntılı hesaplanır
EN_AZ_YUKSEKLIK = 10   # derece: bunun altı ağaçlar/binalar yüzünden genelde görülmez
KARANLIK = -6          # derece: gözlemcinin yerinde Güneş bundan alçaktaysa hava yeterince karanlık
ISS_STANDART_KADIR = -1.8   # 1000 km uzaktan, yarısı aydınlık ISS'in parlaklığı


def _gozlemci_xyz(enlem: float, boylam: float) -> tuple[float, float, float]:
    """Gözlemcinin konumu, Dünya ile dönen eksenlerde (km). (Rakımı 0 kabul ediyoruz.)"""
    e2 = BASIKLIK * (2 - BASIKLIK)
    f, l = math.radians(enlem), math.radians(boylam)
    n = DUNYA_YARICAPI / math.sqrt(1 - e2 * math.sin(f) ** 2)
    return n * math.cos(f) * math.cos(l), n * math.cos(f) * math.sin(l), n * (1 - e2) * math.sin(f)


def _gozlemciden(iss_xyz, gozlemci_xyz, enlem, boylam) -> tuple[float, float, float]:
    """
    ISS gözlemciden nasıl görünüyor? -> (yükseklik°, azimut°, uzaklık km)
    Aradaki farkı gözlemcinin "Doğu - Kuzey - Yukarı" eksenlerine çeviriyoruz:
    yukarı bileşeni büyükse ISS tepede, doğu/kuzey oranı da hangi yönde olduğunu verir.
    """
    dx, dy, dz = (a - b for a, b in zip(iss_xyz, gozlemci_xyz))
    f, l = math.radians(enlem), math.radians(boylam)
    dogu = -math.sin(l) * dx + math.cos(l) * dy
    kuzey = -math.sin(f) * math.cos(l) * dx - math.sin(f) * math.sin(l) * dy + math.cos(f) * dz
    yukari = math.cos(f) * math.cos(l) * dx + math.cos(f) * math.sin(l) * dy + math.sin(f) * dz
    yukseklik = math.degrees(math.atan2(yukari, math.hypot(dogu, kuzey)))
    azimut = math.degrees(math.atan2(dogu, kuzey)) % 360
    return yukseklik, azimut, math.sqrt(dx * dx + dy * dy + dz * dz)


def _kadir(nokta: dict, gozlemci_xyz, uzaklik: float, an: datetime) -> float:
    """
    ISS'in tahmini parlaklığı (kadir). İki şeye bağlı:
      - uzaklık: uzaklaştıkça sönükleşir
      - evre açısı: Güneş ISS'i bizim baktığımız taraftan aydınlatıyorsa daha parlak görünür (Ay gibi)
    """
    # Gözlemciyi de uzaya sabit eksenlere çevir (ISS'in konumu ve Güneş yönü o eksenlerde)
    g = nokta["gmst"]
    ox, oy, oz = gozlemci_xyz
    gozlemci = (ox * math.cos(g) - oy * math.sin(g), ox * math.sin(g) + oy * math.cos(g), oz)
    bize = [a - b for a, b in zip(gozlemci, nokta["r"])]
    bize_uzunluk = math.sqrt(sum(c * c for c in bize))
    cos_aci = sum(a * b / bize_uzunluk for a, b in zip(bize, _gunes_yonu(an)))
    aci = math.acos(max(-1.0, min(1.0, cos_aci)))   # 0 = tam aydınlık yüz bize dönük
    aydinlik = (math.sin(aci) + (math.pi - aci) * math.cos(aci)) / math.pi
    aydinlik = max(aydinlik, 1e-3)
    return ISS_STANDART_KADIR + 5 * math.log10(uzaklik / 1000) - 2.5 * math.log10(aydinlik * math.pi)


def _iss_parlakligi(kadir: float) -> str:
    if kadir < -3:
        return "Çok parlak"
    if kadir < -1.5:
        return "Parlak"
    return "Görülebilir"


def _nokta(an: datetime, yukseklik: float, azimut: float) -> dict:
    from app.services.gokyuzu import yon_adi
    return {"zaman": an.strftime("%Y-%m-%dT%H:%M:%SZ"), "yukseklik": round(yukseklik),
            "azimut": round(azimut), "yon": yon_adi(azimut)}


def _gecisi_incele(uydu, bas: datetime, son: datetime, enlem, boylam, gozlemci_xyz, astro_gozlemci) -> dict | None:
    """ISS'in ufkun üstünde olduğu bir aralığı ince adımlarla inceler. Görünür kısmı yoksa None."""
    gorunur = []          # (an, yükseklik, azimut, uzaklık, nokta)
    golgeye_girdi = False
    an = bas
    while an <= son:
        nokta = _hesapla(uydu, an)
        yukseklik, azimut, uzaklik = _gozlemciden(nokta["dunya_xyz"], gozlemci_xyz, enlem, boylam)
        if yukseklik >= EN_AZ_YUKSEKLIK:
            isikta, _ = _gunes_durumu(nokta["r"], an)
            t = _astro_zaman(an)
            gunes = A.Equator(A.Body.Sun, t, astro_gozlemci, True, True)
            karanlik = A.Horizon(t, astro_gozlemci, gunes.ra, gunes.dec, A.Refraction.Normal).altitude < KARANLIK
            if isikta and karanlik:
                gorunur.append((an, yukseklik, azimut, uzaklik, nokta))
            elif gorunur and not isikta:
                golgeye_girdi = True   # görünürken Dünya'nın gölgesine girdi: gökyüzünün ortasında kaybolur
                break
        an += timedelta(seconds=INCE_ADIM)

    if not gorunur:
        return None
    en_yuksek = max(gorunur, key=lambda g: g[1])
    kadir = _kadir(en_yuksek[4], gozlemci_xyz, en_yuksek[3], en_yuksek[0])
    ilk, sonuncu = gorunur[0], gorunur[-1]
    return {
        "baslangic": _nokta(ilk[0], ilk[1], ilk[2]),
        "en_yuksek": _nokta(en_yuksek[0], en_yuksek[1], en_yuksek[2]),
        "bitis": _nokta(sonuncu[0], sonuncu[1], sonuncu[2]),
        "sure_sn": int((sonuncu[0] - ilk[0]).total_seconds()) + INCE_ADIM,
        "golgeye_girer": golgeye_girdi,
        "kadir": round(kadir, 1),
        "parlaklik": _iss_parlakligi(kadir),
        "yol": [[round(g[2]), round(g[1])] for g in gorunur],   # gökyüzü diyagramı için [azimut, yükseklik]
    }


async def gorunur_gecisler(enlem: float, boylam: float, gun: int = 10, simdi: datetime | None = None) -> dict:
    """
    Önümüzdeki `gun` gün içinde ISS'in bu konumdan çıplak gözle görülebileceği geçişler.
    Görünmesi için üç şart: ISS ufkun 10° üstünde + gözlemcinin yerinde hava karanlık +
    ISS'in kendisi Güneş ışığında (yüksekte olduğu için Güneş'i biz görmesek de o görür).
    """
    simdi = simdi or datetime.now(timezone.utc)
    satir1, satir2 = await tle_getir()
    uydu = Satrec.twoline2rv(satir1, satir2)
    gozlemci_xyz = _gozlemci_xyz(enlem, boylam)
    astro_gozlemci = A.Observer(enlem, boylam, 0)

    gecisler = []
    an, bitis = simdi, simdi + timedelta(days=gun)
    ufukta_bas = None
    while an <= bitis:
        nokta = _hesapla(uydu, an)
        yukseklik, _, _ = _gozlemciden(nokta["dunya_xyz"], gozlemci_xyz, enlem, boylam)
        if yukseklik > 0 and ufukta_bas is None:
            ufukta_bas = an - timedelta(seconds=KABA_ADIM)    # ufuktan çıktı (biraz geriden başla)
        elif yukseklik <= 0 and ufukta_bas is not None:
            gecis = _gecisi_incele(uydu, max(ufukta_bas, simdi), an, enlem, boylam, gozlemci_xyz, astro_gozlemci)
            if gecis:
                gecisler.append(gecis)
            ufukta_bas = None
        an += timedelta(seconds=KABA_ADIM)

    return {
        "konum": {"enlem": enlem, "boylam": boylam},
        "hesaplama_zamani": simdi.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gun": gun,
        "gecisler": gecisler,
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
