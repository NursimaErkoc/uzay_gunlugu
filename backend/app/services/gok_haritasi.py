"""
Gök Haritası: Güneş, Ay ve gezegenlerin gökyüzündeki konumu.

Yıldızlar yerlerinden kıpırdamaz; onların koordinatları frontend/veri/gok.json'da sabit duruyor ve
haritayı tarayıcı çiziyor. Ama Güneş, Ay ve gezegenler yıldızların arasında yer değiştirir; onları
astronomy-engine ile burada hesaplıyoruz.

Döndürdüğümüz koordinatlar yıldız verisiyle AYNI sistemde (ekvator koordinatları, J2000):
  ra  (sağ açıklık) : gökyüzündeki "boylam", 0-360°
  dec (dik açıklık) : gökyüzündeki "enlem", -90..+90°
Tarayıcı bunları saat ve konuma göre ufuk koordinatlarına (yükseklik + yön) çeviriyor.
"""
from datetime import datetime, timezone

import astronomy as A

from app.services.gokyuzu import _astro_zaman, _iso, ay_evresi_adi

CISIMLER = [
    (A.Body.Sun, "Güneş", "gunes"),
    (A.Body.Moon, "Ay", "ay"),
    (A.Body.Mercury, "Merkür", "gezegen"),
    (A.Body.Venus, "Venüs", "gezegen"),
    (A.Body.Mars, "Mars", "gezegen"),
    (A.Body.Jupiter, "Jüpiter", "gezegen"),
    (A.Body.Saturn, "Satürn", "gezegen"),
]


def cisimler(enlem: float, boylam: float, zaman: datetime | None = None) -> dict:
    """Verilen an ve konum için Güneş, Ay ve gezegenlerin ra/dec koordinatları."""
    zaman = zaman or datetime.now(timezone.utc)
    t = _astro_zaman(zaman)
    # Konum özellikle Ay için önemli: Ay çok yakın olduğu için farklı şehirlerden bakınca
    # yıldızların önünde biraz farklı yerde görünür (1°'ye kadar).
    gozlemci = A.Observer(enlem, boylam, 0)

    liste = []
    for govde, ad, tur in CISIMLER:
        ekvator = A.Equator(govde, t, gozlemci, False, True)   # False = J2000 (yıldız verisiyle aynı)
        bilgi = {
            "ad": ad,
            "tur": tur,
            "ra": round(ekvator.ra * 15, 3),   # astronomy-engine saat cinsinden veriyor (1 saat = 15°)
            "dec": round(ekvator.dec, 3),
            "kadir": round(A.Illumination(govde, t).mag, 1),
        }
        if govde == A.Body.Moon:
            aci = A.MoonPhase(t)
            bilgi["evre"] = ay_evresi_adi(aci)
            bilgi["aydinlik"] = round(A.Illumination(govde, t).phase_fraction, 3)
            bilgi["buyuyen"] = aci < 180
        liste.append(bilgi)

    return {"zaman": _iso(t), "konum": {"enlem": enlem, "boylam": boylam}, "cisimler": liste}
