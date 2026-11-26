"""
Uzay Sondaları Nerede: Voyager, New Horizons, Parker gibi araçların şu anki konumu.

Kaynak: NASA JPL Horizons (https://ssd.jpl.nasa.gov/api/horizons.api). Anahtar gerekmiyor.
Horizons, NASA'nın uzay araçlarını yönlendirirken kullandığı yörünge hesaplarını herkese açıyor.
Her araç için iki soru soruyoruz (QUANTITIES='19,20'):
  19 -> Güneş'e uzaklık (r, AB) ve Güneş'ten uzaklaşma hızı (rdot, km/sn)
  20 -> Dünya'ya uzaklık (delta, AB) ve Dünya'dan uzaklaşma hızı (deldot, km/sn)
AB (astronomik birim) = Dünya ile Güneş arası ortalama uzaklık = 149.597.870,7 km.

Hesap saat başına yuvarlanır ve 1 saat önbellekte tutulur. Tarayıcı, uzaklaşma hızını
kullanarak sayacı saniye saniye kendisi ilerletir; Horizons'a her saniye sormaya gerek yok.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from app import cache

HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
ISTEK_BASLIKLARI = {"User-Agent": "UzayGunlugu/0.1 (ogrenci projesi)"}
AB_KM = 149_597_870.7
ISIK_HIZI_KMS = 299_792.458
DENEME_SAYISI = 3        # Horizons meşgulse (503) kaç kez denensin
BEKLEME_SN = 2.0         # denemeler arası bekleme (testlerde 0 yapılır)

# horizons: JPL'nin araç numarası (uzay araçlarının numaraları eksi işaretlidir)
# durum: "aktif" = hâlâ haberleşiyor, "sessiz" = bağlantı kesildi, konumu hesapla biliniyor
SONDALAR = [
    {"kod": "voyager-1", "horizons": "-31", "ad": "Voyager 1", "firlatma": 1977, "durum": "aktif",
     "aciklama": "İnsan yapımı en uzak cisim. Jüpiter ve Satürn'ü ziyaret etti, 2012'de yıldızlararası uzaya geçti. "
                 "Üzerinde Dünya'dan sesler ve müzikler taşıyan altın bir plak var."},
    {"kod": "voyager-2", "horizons": "-32", "ad": "Voyager 2", "firlatma": 1977, "durum": "aktif",
     "aciklama": "Dört dev gezegenin dördünü de (Jüpiter, Satürn, Uranüs, Neptün) ziyaret eden tek araç. "
                 "2018'de yıldızlararası uzaya geçti."},
    {"kod": "pioneer-10", "horizons": "-23", "ad": "Pioneer 10", "firlatma": 1972, "durum": "sessiz",
     "son_sinyal": 2003,
     "aciklama": "Asteroit kuşağını geçen ve Jüpiter'i yakından gören ilk araç. Üzerinde insanların "
                 "ve Dünya'nın yerini gösteren bir plaka taşıyor."},
    {"kod": "pioneer-11", "horizons": "-24", "ad": "Pioneer 11", "firlatma": 1973, "durum": "sessiz",
     "son_sinyal": 1995,
     "aciklama": "Satürn'ün yanından geçen ilk araç. Kartal takımyıldızı yönünde ilerliyor."},
    {"kod": "new-horizons", "horizons": "-98", "ad": "New Horizons", "firlatma": 2006, "durum": "aktif",
     "aciklama": "2015'te Plüton'un, 2019'da Arrokoth'un yanından geçti. Arrokoth, bir aracın ziyaret ettiği "
                 "en uzak gök cismi. Şimdi Kuiper kuşağında ilerliyor."},
    {"kod": "lucy", "horizons": "-49", "ad": "Lucy", "firlatma": 2021, "durum": "aktif",
     "aciklama": "Jüpiter'le aynı yörüngede dolaşan Truva asteroitlerine gidiyor. Adını, ünlü insan atası "
                 "fosili Lucy'den alıyor."},
    {"kod": "europa-clipper", "horizons": "-159", "ad": "Europa Clipper", "firlatma": 2024, "durum": "aktif",
     "aciklama": "Jüpiter'in buzla kaplı uydusu Europa'ya gidiyor; buzun altında bir okyanus olduğu düşünülüyor. "
                 "Yolda Mars'tan ve Dünya'dan hız alıyor, 2030'da varacak."},
    {"kod": "juice", "horizons": "-28", "ad": "Juice", "firlatma": 2023, "durum": "aktif",
     "aciklama": "Avrupa Uzay Ajansı'nın Jüpiter aracı. Ganymede, Callisto ve Europa uydularını inceleyecek; "
                 "2031'de varacak."},
    {"kod": "psyche", "horizons": "-255", "ad": "Psyche", "firlatma": 2023, "durum": "aktif",
     "aciklama": "Büyük kısmı metalden oluşabilecek Psyche asteroitine gidiyor. Bir gezegenin çekirdeğinin "
                 "kalıntısı olabilir. 2029'da varacak."},
    {"kod": "jwst", "horizons": "-170", "ad": "James Webb", "firlatma": 2021, "durum": "aktif",
     "aciklama": "Tarihin en büyük uzay teleskobu. Dünya'nın gölge tarafında, 1,5 milyon km uzakta "
                 "Güneş'in etrafında Dünya'yla birlikte dönüyor."},
    {"kod": "parker", "horizons": "-96", "ad": "Parker Güneş Sondası", "firlatma": 2018, "durum": "aktif",
     "aciklama": "Güneş'e en çok yaklaşan araç: yüzeyine 6,1 milyon km'ye kadar sokuldu ve saatte "
                 "690.000 km hızla en hızlı insan yapımı cisim oldu."},
]


class SondaHatasi(Exception):
    """Hiçbir aracın konumu alınamadığında fırlatılır."""


def satiri_coz(sonuc_metni: str) -> tuple[float, float, float, float]:
    """
    Horizons'ın metin tablosundan ilk satırı ayıklar.
    Tablo $$SOE (başlangıç) ile $$EOE (bitiş) arasında:
        2026-Nov-26 12:00      172.4582135956  16.8815551  173.245723024289  22.1221033
    Son 4 sütun: r, rdot, delta, deldot
    """
    if "$$SOE" not in sonuc_metni:
        raise ValueError("Horizons cevabında tablo yok")
    tablo = sonuc_metni.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    ilk_satir = next(s for s in tablo.splitlines() if s.strip())
    r, rdot, delta, deldot = (float(x) for x in ilk_satir.split()[-4:])
    return r, rdot, delta, deldot


async def _konum_getir(istemci: httpx.AsyncClient, sonda: dict, zaman: datetime) -> dict:
    parametreler = {
        "format": "json",
        "COMMAND": f"'{sonda['horizons']}'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'500@399'",                     # Dünya'nın merkezinden bakış
        "START_TIME": f"'{zaman:%Y-%m-%d %H:%M}'",
        "STOP_TIME": f"'{zaman + timedelta(hours=1):%Y-%m-%d %H:%M}'",
        "STEP_SIZE": "'1h'",
        "QUANTITIES": "'19,20'",
        "OBJ_DATA": "'NO'",
    }
    # Horizons aynı anda gelen istekleri sevmiyor; meşgulse "503" der. Biraz bekleyip yeniden dene.
    for deneme in range(DENEME_SAYISI):
        cevap = await istemci.get(HORIZONS_URL, params=parametreler)
        if cevap.status_code not in (429, 503):
            break
        await asyncio.sleep(BEKLEME_SN * (deneme + 1))
    cevap.raise_for_status()
    veri = cevap.json()
    if "error" in veri:
        raise ValueError(veri["error"][:200])
    r, rdot, delta, deldot = satiri_coz(veri.get("result", ""))
    dunya_km = delta * AB_KM
    return {
        **{k: v for k, v in sonda.items() if k != "horizons"},
        "gunes_ab": r,
        "gunes_hiz_kms": rdot,          # + uzaklaşıyor, - yaklaşıyor
        "dunya_ab": delta,
        "dunya_km": dunya_km,
        "dunya_hiz_kms": deldot,
        "isik_suresi_sn": dunya_km / ISIK_HIZI_KMS,
    }


async def sondalarin_konumu(simdi: datetime | None = None) -> dict:
    """Bütün araçların şu anki (saat başına yuvarlanmış) konumu."""
    simdi = simdi or datetime.now(timezone.utc)
    zaman = simdi.replace(minute=0, second=0, microsecond=0)
    anahtar = f"sondalar:{zaman:%Y-%m-%dT%H}"

    kayitli = cache.getir(anahtar)
    if kayitli is not None:
        return kayitli

    # Horizons aynı anda birden fazla isteğe 503 veriyor: araçları sırayla soruyoruz.
    # (Her biri ~0,5 sn; sonuç 1 saat önbellekte kaldığı için kullanıcı bunu saatte bir hisseder.)
    sinir = asyncio.Semaphore(1)

    async def tek(sonda):
        async with sinir:
            try:
                return await _konum_getir(istemci, sonda, zaman)
            except (httpx.HTTPError, ValueError, KeyError, StopIteration):
                return None

    async with httpx.AsyncClient(timeout=30, headers=ISTEK_BASLIKLARI) as istemci:
        sonuclar = await asyncio.gather(*(tek(s) for s in SONDALAR))

    sondalar = [s for s in sonuclar if s]
    if not sondalar:
        raise SondaHatasi("JPL Horizons'a ulaşılamadı")

    eksik = [s["ad"] for s, sonuc in zip(SONDALAR, sonuclar) if sonuc is None]
    sonuc = {"zaman": zaman.isoformat(), "sondalar": sondalar, "eksik": eksik}
    # Eksik varsa 5 dk sonra yeniden dene; hepsi geldiyse 1 saat sakla
    cache.kaydet(anahtar, sonuc, 5 * 60 if eksik else 60 * 60, kalici=True)
    return sonuc
