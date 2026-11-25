"""
Dünya'nın Bugünkü Fotoğrafı (NASA EPIC) testleri. NASA'ya bağlanmadan, sahte cevaplarla.
"""
import asyncio

import httpx
import pytest

from app.services import epic


def _ham_kare(saat, enlem, boylam, ad):
    """EPIC cevabındaki bir fotoğraf kaydının taklidi (gerçek cevapla aynı biçim)."""
    return {
        "image": ad,
        "date": f"2026-11-23 {saat}",
        "centroid_coordinates": {"lat": enlem, "lon": boylam},
        "dscovr_j2000_position": {"x": -853690.8, "y": -1032069.3, "z": -428888.1},
    }


SAHTE_GUN = [
    _ham_kare("10:30:00", -10.0, 20.0, "epic_1b_3"),     # Afrika: Türkiye görünür
    _ham_kare("00:50:27", -17.9, 155.0, "epic_1b_1"),    # Pasifik: Türkiye görünmez
    _ham_kare("05:00:00", -12.0, 90.0, "epic_1b_2"),     # Hindistan doğusu
]


@pytest.fixture
def sahte_epic(monkeypatch):
    durum = {"kod": 200, "govde": SAHTE_GUN, "adresler": []}

    def isleyici(istek):
        durum["adresler"].append(str(istek.url))
        return httpx.Response(durum["kod"], json=durum["govde"])

    gercek = httpx.AsyncClient

    class SahteIstemci(gercek):
        def __init__(self, **ayarlar):
            super().__init__(transport=httpx.MockTransport(isleyici), **ayarlar)

    monkeypatch.setattr(httpx, "AsyncClient", SahteIstemci)
    return durum


def test_kareler_zamana_gore_sirali_ve_adresler_dogru(sahte_epic):
    sonuc = asyncio.run(epic.dunya_fotograflari("2026-11-23"))
    assert sonuc["tarih"] == "2026-11-23"
    assert [k["zaman"][11:16] for k in sonuc["kareler"]] == ["00:50", "05:00", "10:30"]
    ilk = sonuc["kareler"][0]
    assert ilk["resim"] == "https://epic.gsfc.nasa.gov/archive/natural/2026/11/23/jpg/epic_1b_1.jpg"
    assert ilk["onizleme"].endswith("/thumbs/epic_1b_1.jpg")
    assert sahte_epic["adresler"][0].endswith("/api/natural/date/2026-11-23")


def test_turkiye_gorunurlugu_ve_bolge(sahte_epic):
    kareler = asyncio.run(epic.dunya_fotograflari("2026-11-23"))["kareler"]
    pasifik, _, afrika = kareler
    assert pasifik["turkiye_gorunur"] is False
    assert afrika["turkiye_gorunur"] is True
    assert afrika["bolge"] == "Afrika, Orta Doğu ve Türkiye"
    assert pasifik["bolge"] == "Pasifik, Japonya ve Avustralya"


def test_uydu_uzakligi(sahte_epic):
    kare = asyncio.run(epic.dunya_fotograflari("2026-11-23"))["kareler"][0]
    assert 1_300_000 < kare["uzaklik_km"] < 1_600_000   # L1 noktası: ~1,5 milyon km


def test_tarihsiz_istek_en_son_gunu_ister(sahte_epic):
    asyncio.run(epic.dunya_fotograflari())
    assert sahte_epic["adresler"][0] == "https://epic.gsfc.nasa.gov/api/natural"


def test_api(istemci, sahte_epic):
    cevap = istemci.get("/api/dunya?tarih=2026-11-23")
    assert cevap.status_code == 200
    assert len(cevap.json()["kareler"]) == 3


@pytest.mark.parametrize("tarih", ["2010-01-01", "2999-01-01", "23-11-2026"])
def test_api_hatali_tarih(istemci, tarih):
    assert istemci.get(f"/api/dunya?tarih={tarih}").status_code == 422


def test_api_nasa_hata_verirse_502(istemci, sahte_epic):
    sahte_epic["kod"] = 503
    assert istemci.get("/api/dunya?tarih=2026-11-23").status_code == 502


@pytest.mark.parametrize("nokta, beklenen", [
    (((39, 35), (39, 35)), 0),          # aynı yer
    (((0, 0), (0, 90)), 90),            # ekvatorda çeyrek tur
    (((0, 0), (0, 180)), 180),          # tam karşı taraf
])
def test_aci_uzakligi(nokta, beklenen):
    assert epic.aci_uzakligi(*nokta) == pytest.approx(beklenen, abs=0.01)
