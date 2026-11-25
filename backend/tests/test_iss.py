"""
ISS testleri. İnternete çıkmamak için sabit bir yörünge verisi (TLE) ve sahte astronot listesi kullanıyoruz.
"""
import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from app.services import events, iss

# 24 Kasım 2026 tarihli gerçek ISS yörünge verisi
TLE = (
    "1 25544U 98067A   26328.88031537  .00004718  00000+0  91905-4 0  9993",
    "2 25544  51.6319 224.8621 0007433  61.9046 298.2693 15.49577477596662",
)
# Bu andaki konumu ayrı bir ISS takip servisinden (wheretheiss.at) kontrol ettik:
# enlem -12.02, boylam -144.22, yükseklik 424.3 km, hız 27560 km/sa, Dünya'nın gölgesinde
KONTROL_ANI = datetime(2026, 11, 25, 8, 47, 58, tzinfo=timezone.utc)


@pytest.fixture
def sabit_tle(monkeypatch):
    async def tle():
        return TLE
    monkeypatch.setattr(iss, "tle_getir", tle)


def test_konum_bagimsiz_servisle_ayni(sabit_tle):
    k = asyncio.run(iss.iss_konumu(KONTROL_ANI))
    assert k["enlem"] == pytest.approx(-12.02, abs=0.2)
    assert k["boylam"] == pytest.approx(-144.22, abs=0.2)
    assert k["yukseklik_km"] == pytest.approx(424.3, abs=2)
    assert k["hiz_kmsa"] == pytest.approx(27560, abs=50)
    assert k["gunes_isiginda"] is False


def test_yorunge_izi(sabit_tle):
    k = asyncio.run(iss.iss_konumu(KONTROL_ANI))
    assert len(k["iz"]) == 136                            # -45 ... +90 dakika
    assert k["iz"][45] == [round(k["enlem"], 3), round(k["boylam"], 3)]   # ortadaki nokta = şu an
    # ISS'in yörünge eğimi 51.6°: hiçbir zaman bundan daha kuzeye/güneye gitmez
    assert all(abs(enlem) <= 52 for enlem, _ in k["iz"])
    assert all(-180 <= boylam <= 180 for _, boylam in k["iz"])


def test_tle_zamani(sabit_tle):
    # TLE'deki "26328.88031537" = 2026 yılının 328. günü, günün %88'i -> 24 Kasım 21:07
    assert asyncio.run(iss.iss_konumu(KONTROL_ANI))["tle_zamani"] == "2026-11-24T21:07:39Z"


def test_iss_api(istemci, sabit_tle):
    cevap = istemci.get("/api/iss")
    assert cevap.status_code == 200
    assert 380 < cevap.json()["yukseklik_km"] < 460


def test_iss_api_veri_alinamazsa_502(istemci, monkeypatch):
    async def bozuk():
        raise iss.IssHatasi("bağlantı yok")
    monkeypatch.setattr(iss, "tle_getir", bozuk)
    assert istemci.get("/api/iss").status_code == 502


# --- Uzaydakiler ---
def _astronot(id, ad, **ekstra):
    a = {"id": id, "name": ad, "type": {"name": "Government"}, "date_of_death": None,
         "agency": {"abbrev": "NASA"}, "nationality": [{"alpha_2_code": "US", "name": "USA"}],
         "time_in_space": "P120DT3H", "flights_count": 2, "image": None, "wiki": None}
    a.update(ekstra)
    return a


@pytest.fixture
def sahte_ll2(monkeypatch):
    async def ll2(yol, parametreler):
        if yol == "astronauts":
            return [
                _astronot(1, "Ayşe Yıldız"),
                _astronot(2, "Wang Li", agency={"abbrev": "CNSA"}, nationality=[{"alpha_2_code": "CN"}]),
                _astronot(3, "Yeni Giden"),
                _astronot(4, "Starman", type={"name": "Non-Human"}),
                _astronot(5, "Laika", date_of_death="1957-11-03"),
            ]
        return [
            {"spacestation": {"name": "Tiangong space station"},
             "crew": [{"astronaut": {"id": 2}, "role": {"role": "Commander"}}]},
            {"spacestation": {"name": "International Space Station"},
             "crew": [{"astronaut": {"id": 1}, "role": {"role": "Flight Engineer"}}]},
        ]
    monkeypatch.setattr(events, "_ll2_getir", ll2)


def test_uzaydakiler_gruplanir_ve_insan_olmayanlar_ayiklanir(sahte_ll2):
    sonuc = asyncio.run(iss.uzaydakiler())
    assert sonuc["toplam"] == 3
    gruplar = {g["ad"]: g["kisiler"] for g in sonuc["gruplar"]}
    # ISS ilk sırada
    assert sonuc["gruplar"][0]["ad"] == "Uluslararası Uzay İstasyonu (ISS)"
    ayse = gruplar["Uluslararası Uzay İstasyonu (ISS)"][0]
    assert (ayse["ad"], ayse["ulke"], ayse["gorev"], ayse["uzayda_gun"]) == ("Ayşe Yıldız", "ABD", "Uçuş Mühendisi", 120)
    assert gruplar["Tiangong Uzay İstasyonu (Çin)"][0]["gorev"] == "Komutan"
    assert [k["ad"] for k in gruplar["Yolda ya da başka bir araçta"]] == ["Yeni Giden"]


def test_uzaydakiler_api_hata(istemci, monkeypatch):
    async def bozuk(yol, parametreler):
        raise httpx.ConnectError("bağlantı yok")
    monkeypatch.setattr(events, "_ll2_getir", bozuk)
    assert istemci.get("/api/uzaydakiler").status_code == 502


@pytest.mark.parametrize("sure, gun", [("P224DT13H57M38S", 224), ("PT5H", 0), (None, None)])
def test_gun_sayisi(sure, gun):
    assert iss._gun_sayisi(sure) == gun
