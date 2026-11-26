"""
Bugün Uzay Tarihinde: kendi hazırladığımız uzay_tarihi.json dosyasından o günün olaylarını seçer.

Her olayın sadece ayı ve günü var ("07-20"), yılı ayrı ("yil": 1969). Böylece her yıl
aynı gün yine çıkar. Yılın her gününde olay yok; olay olmayan günlerde en yakın günün
olayını gösteririz ("3 gün sonra, 1977'de ...").
"""
import json
from datetime import date, timedelta

from app.config import PROJE_KLASORU

TARIH_DOSYASI = PROJE_KLASORU / "backend" / "data" / "uzay_tarihi.json"

with open(TARIH_DOSYASI, encoding="utf-8") as dosya:
    OLAYLAR: list[dict] = json.load(dosya)

# "07-20" -> o günün olayları (eskiden yeniye). Her istekte bütün listeyi taramamak için bir kez hazırla.
GUNLERE_GORE: dict[str, list[dict]] = {}
for _olay in sorted(OLAYLAR, key=lambda o: o["yil"]):
    GUNLERE_GORE.setdefault(_olay["tarih"], []).append(_olay)


def _ay_gun(gun: date) -> str:
    return f"{gun.month:02d}-{gun.day:02d}"


def gunun_olaylari(gun: date | None = None) -> dict:
    """
    Verilen günün (verilmezse bugünün) uzay tarihi olaylarını döndürür.
    O gün olay yoksa en yakın günü arar: önce 1 gün önce, sonra 1 gün sonra, 2 gün önce...
    fark: olayların gününün bugünden kaç gün uzakta olduğu (eksi = geçmişte, 0 = bugün).
    """
    gun = gun or date.today()
    for uzaklik in range(0, 184):                       # yarım yıl içinde mutlaka bir olay var
        for fark in ((0,) if uzaklik == 0 else (-uzaklik, uzaklik)):
            hedef = gun + timedelta(days=fark)           # yıl geçişlerini timedelta kendisi halleder
            olaylar = GUNLERE_GORE.get(_ay_gun(hedef))
            if olaylar:
                return {
                    "tarih": hedef.isoformat(),
                    "fark": fark,
                    "olaylar": [{**o, "yil_once": hedef.year - o["yil"]} for o in olaylar],
                }
    raise ValueError("Uzay tarihi dosyası boş")
