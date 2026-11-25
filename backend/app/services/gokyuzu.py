"""
Bu Gece Gökyüzü: verilen konum için bu gecenin gökyüzünü HESAPLAR.

- Ay: evresi, yüzde kaçı aydınlık, doğuş/batış, sonraki dolunay ve yeni ay
- Güneş: gün batımı, tam karanlık (astronomik alacakaranlık), gün doğumu
- Gezegenler: bu gece görünüyor mu, en iyi ne zaman, hangi yönde, ne kadar parlak

Hepsi astronomy-engine ile hesaplanır, internete gerek yok.

Birkaç astronomi terimi:
  yükseklik (altitude) : cismin ufuktan kaç derece yukarıda olduğu (0 = ufuk, 90 = tam tepede)
  azimut               : cismin yönü, derece cinsinden (0 = Kuzey, 90 = Doğu, 180 = Güney, 270 = Batı)
  kadir (magnitude)    : parlaklık ölçüsü. Sayı KÜÇÜLDÜKÇE cisim PARLAKLAŞIR (Venüs ≈ -4, sönük yıldız ≈ 6)
  alacakaranlık        : Güneş battıktan sonra gökyüzünün hâlâ aydınlık olduğu süre.
                         Güneş ufkun 18° altına inince gökyüzü tamamen kararır ("tam karanlık").

Tüm zamanlar UTC ve ISO biçiminde döner; tarayıcı bunları kullanıcının kendi saatine çevirir.
"""
from datetime import datetime, timezone

import astronomy as A

GEZEGENLER = {
    A.Body.Mercury: "Merkür", A.Body.Venus: "Venüs", A.Body.Mars: "Mars",
    A.Body.Jupiter: "Jüpiter", A.Body.Saturn: "Satürn",
}   # Uranüs ve Neptün çıplak gözle görülmediği için listede yok

YONLER = ["Kuzey", "Kuzeydoğu", "Doğu", "Güneydoğu", "Güney", "Güneybatı", "Batı", "Kuzeybatı"]

ORNEKLEME_DAKIKA = 10      # gece boyunca kaç dakikada bir bakılsın
GORUNUR_YUKSEKLIK = 10     # gezegen ufkun en az kaç derece üstündeyse "görünür" sayılsın
KARANLIK_GUNES = -6        # Güneş bu kadar derece aşağıdaysa gökyüzü gezegen görecek kadar karanlık


# =====================================================================
# Yardımcılar
# =====================================================================
def _astro_zaman(dt: datetime) -> A.Time:
    dt = dt.astimezone(timezone.utc)
    return A.Time.Make(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)


def _iso(t: A.Time | None) -> str | None:
    """astronomy-engine zamanı -> "2026-12-24T01:28:45Z" (saniyeye yuvarlanmış)."""
    if t is None:
        return None
    return t.Utc().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ufuk(cisim: A.Body, t: A.Time, gozlemci: A.Observer) -> A.HorizontalCoordinates:
    """Cismin gözlemciye göre yüksekliği ve yönü (ışığın havada kırılması da hesaba katılır)."""
    ekvator = A.Equator(cisim, t, gozlemci, True, True)
    return A.Horizon(t, gozlemci, ekvator.ra, ekvator.dec, A.Refraction.Normal)


def yon_adi(azimut: float) -> str:
    """Azimut derecesini yön adına çevirir: 0 -> Kuzey, 135 -> Güneydoğu ..."""
    return YONLER[round(azimut / 45) % 8]


def ay_evresi_adi(aci: float) -> str:
    """
    Ay'ın evre açısı (0-360°) -> evrenin adı.
    0° = Yeni Ay, 90° = İlk Dördün, 180° = Dolunay, 270° = Son Dördün.
    Ay her gün yaklaşık 12° ilerler; tam evre adlarını ±6°'lik (yaklaşık bir günlük) aralıkta veriyoruz.
    """
    aci %= 360
    if aci < 6 or aci >= 354:
        return "Yeni Ay"
    if aci < 84:
        return "Büyüyen Hilal"
    if aci < 96:
        return "İlk Dördün"
    if aci < 174:
        return "Büyüyen Şişkin Ay"
    if aci < 186:
        return "Dolunay"
    if aci < 264:
        return "Küçülen Şişkin Ay"
    if aci < 276:
        return "Son Dördün"
    return "Küçülen Hilal"


def parlaklik_adi(kadir: float) -> str:
    if kadir < -3:
        return "Çok parlak"
    if kadir < -1:
        return "Parlak"
    if kadir < 1:
        return "Kolayca görülür"
    return "Sönük ama çıplak gözle görülebilir"


# =====================================================================
# Ana fonksiyon
# =====================================================================
def bu_gece(enlem: float, boylam: float, simdi: datetime | None = None) -> dict:
    """Verilen konum için bu gecenin gökyüzü bilgileri. `simdi` testlerde sabit bir an vermek için."""
    simdi = simdi or datetime.now(timezone.utc)
    t = _astro_zaman(simdi)
    gozlemci = A.Observer(enlem, boylam, 0)

    gece = _gece_araligi(t, gozlemci)
    return {
        "konum": {"enlem": enlem, "boylam": boylam},
        "hesaplama_zamani": _iso(t),
        "gunes": gece["bilgi"],
        "ay": _ay_bilgisi(t, gece["baslangic"] or t, gozlemci),
        "gezegenler": _gezegenler(gece["baslangic"], gece["bitis"], gozlemci),
    }


# =====================================================================
# Güneş ve gecenin sınırları
# =====================================================================
def _gece_araligi(t: A.Time, gozlemci: A.Observer) -> dict:
    """
    "Bu gece" hangi zaman aralığı?
      - Şu an gündüzse: bugünkü gün batımından yarınki gün doğumuna kadar
      - Şu an geceyse (ör. saat 02:00): dün akşamki gün batımından bu sabahki gün doğumuna kadar
    Kutup bölgelerinde Güneş hiç batmayabilir veya hiç doğmayabilir; o durumlar da ele alınıyor.
    """
    gunes_yuksekligi = _ufuk(A.Body.Sun, t, gozlemci).altitude
    simdi_gece = gunes_yuksekligi < -0.833   # -0.833°: Güneş'in üst kenarının ufkun altına indiği an

    # Geceyse son 1 güne, gündüzse önümüzdeki 1 güne bakarak gün batımını ara
    arama_baslangici = t.AddDays(-1) if simdi_gece else t
    gun_batimi = A.SearchRiseSet(A.Body.Sun, gozlemci, A.Direction.Set, arama_baslangici, 1)
    if gun_batimi is not None and simdi_gece and gun_batimi.ut > t.ut:
        gun_batimi = None   # bulunan gün batımı gelecekte: Güneş aslında 1 günden uzun süredir batık

    if gun_batimi is None and not simdi_gece:
        # Güneş önümüzdeki 24 saatte hiç batmıyor (kutuplarda "gece yarısı güneşi")
        return {
            "baslangic": None, "bitis": None,
            "bilgi": {"gun_batimi": None, "karanlik_baslangici": None, "karanlik_bitisi": None,
                      "gun_dogumu": None, "gece_suresi_dakika": 0,
                      "not": "Bu konumda Güneş bu gece batmıyor."},
        }

    baslangic = gun_batimi or t   # Güneş hiç doğmuyorsa (kutup gecesi) geceyi şu andan başlat
    gun_dogumu = A.SearchRiseSet(A.Body.Sun, gozlemci, A.Direction.Rise, baslangic, 2)
    bitis = gun_dogumu or baslangic.AddDays(1)

    # Tam karanlık: Güneş ufkun 18° altına indiğinde başlar, sabah 18°'nin üstüne çıkınca biter
    # (Bu gecenin sınırları içinde kalmalı; yoksa "bu gece tam kararmıyor" demektir.)
    karanlik_bas = karanlik_bit = None
    if gun_batimi is not None:
        karanlik_bas = A.SearchAltitude(A.Body.Sun, gozlemci, A.Direction.Set, baslangic, 1, -18)
        if karanlik_bas is not None and karanlik_bas.ut > bitis.ut:
            karanlik_bas = None
        if karanlik_bas is not None:
            karanlik_bit = A.SearchAltitude(A.Body.Sun, gozlemci, A.Direction.Rise, karanlik_bas, 2, -18)
            if karanlik_bit is not None and karanlik_bit.ut > bitis.ut:
                karanlik_bit = None

    notu = None
    if gun_batimi is None:
        notu = "Bu konumda Güneş bugün hiç doğmuyor (kutup gecesi)."
    elif karanlik_bas is None:
        notu = "Bu gece gökyüzü tam olarak kararmıyor (Güneş ufkun 18° altına inmiyor)."

    return {
        "baslangic": baslangic,
        "bitis": bitis,
        "bilgi": {
            "gun_batimi": _iso(gun_batimi),
            "karanlik_baslangici": _iso(karanlik_bas),
            "karanlik_bitisi": _iso(karanlik_bit),
            "gun_dogumu": _iso(gun_dogumu),
            "gece_suresi_dakika": round((bitis.ut - baslangic.ut) * 24 * 60),
            "not": notu,
        },
    }


# =====================================================================
# Ay
# =====================================================================
def _ay_bilgisi(t: A.Time, gece_baslangici: A.Time, gozlemci: A.Observer) -> dict:
    aci = A.MoonPhase(t)                                        # 0-360°
    aydinlik = A.Illumination(A.Body.Moon, t).phase_fraction    # 0-1 arası

    if aydinlik > 0.75:
        notu = "Ay çok parlak: sönük yıldızlar ve Samanyolu zor görünür. Ay'ı ve gezegenleri izlemek için güzel bir gece."
    elif aydinlik < 0.25:
        notu = "Ay sönük: yıldız gözlemi için iyi bir gece. Şehir ışıklarından uzaklaşırsan Samanyolu'nu bile görebilirsin."
    else:
        notu = "Ay yarı aydınlık: parlak yıldızlar ve gezegenler rahatça görünür. Ay batınca gökyüzü daha da kararır."

    return {
        "evre": ay_evresi_adi(aci),
        "evre_acisi": round(aci, 1),         # frontend Ay'ı bu açıya göre çiziyor
        "aydinlik": round(aydinlik, 3),
        "buyuyen": aci < 180,                # büyüyen mi küçülen mi (çizimde aydınlık taraf buna göre)
        "dogus": _iso(A.SearchRiseSet(A.Body.Moon, gozlemci, A.Direction.Rise, gece_baslangici, 1)),
        "batis": _iso(A.SearchRiseSet(A.Body.Moon, gozlemci, A.Direction.Set, gece_baslangici, 1)),
        "sonraki_dolunay": _iso(A.SearchMoonPhase(180, t, 40)),
        "sonraki_yeni_ay": _iso(A.SearchMoonPhase(0, t, 40)),
        "not": notu,
    }


# =====================================================================
# Gezegenler
# =====================================================================
def _gezegenler(baslangic: A.Time | None, bitis: A.Time | None, gozlemci: A.Observer) -> list[dict]:
    """
    Gece boyunca 10 dakikada bir her gezegenin yüksekliğine bakıyoruz.
    Gökyüzü yeterince karanlıkken (Güneş -6°'nin altında) gezegen ufkun 10° üstündeyse "görünür".
    En yüksekte olduğu an "en iyi zaman".
    """
    # Örnekleme anları ve o anlarda gökyüzü karanlık mı?
    anlar = []
    if baslangic is not None:
        adim = ORNEKLEME_DAKIKA / (24 * 60)   # gün cinsinden
        an = baslangic
        while an.ut <= bitis.ut:
            if _ufuk(A.Body.Sun, an, gozlemci).altitude < KARANLIK_GUNES:
                anlar.append(an)
            an = an.AddDays(adim)

    sonuc = []
    for cisim, ad in GEZEGENLER.items():
        gorunur_anlar = []   # (an, yükseklik, azimut)
        for an in anlar:
            ufuk = _ufuk(cisim, an, gozlemci)
            if ufuk.altitude >= GORUNUR_YUKSEKLIK:
                gorunur_anlar.append((an, ufuk.altitude, ufuk.azimuth))

        if not gorunur_anlar:
            sonuc.append({"ad": ad, "gorunur": False})
            continue

        en_iyi = max(gorunur_anlar, key=lambda x: x[1])
        kadir = A.Illumination(cisim, en_iyi[0]).mag
        sonuc.append({
            "ad": ad,
            "gorunur": True,
            "ilk_gorunus": _iso(gorunur_anlar[0][0]),
            "son_gorunus": _iso(gorunur_anlar[-1][0]),
            "en_iyi_zaman": _iso(en_iyi[0]),
            "yukseklik": round(en_iyi[1]),
            "yon": yon_adi(en_iyi[2]),
            "kadir": round(kadir, 1),
            "parlaklik": parlaklik_adi(kadir),
        })

    # Görünenler önce, sonra en parlaktan sönüğe
    sonuc.sort(key=lambda g: (not g["gorunur"], g.get("kadir", 99)))
    return sonuc
