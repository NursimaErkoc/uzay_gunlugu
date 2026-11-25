"""
Yaklaşan Asteroitler testleri. NASA'ya gerçekten bağlanmıyoruz: sahte bir internet bağlantısı
(httpx.MockTransport) NASA'nın cevabını taklit ediyor.
"""
import asyncio
import json
from datetime import date

import httpx
import pytest

from app.services import neo

SAHTE_ANAHTAR = "GIZLI-TEST-ANAHTARI-123"


def _ham_asteroit(id, ad, uzaklik_km, cap_min, cap_max, hiz_kms, zaman_ms, tehlikeli=False):
    """NASA NeoWs cevabındaki bir asteroit kaydının taklidi (gerçek cevapla aynı biçim)."""
    return {
        "id": id,
        "name": ad,
        # Gerçek NASA cevabında da böyle: anahtar bu adresin içinde!
        "links": {"self": f"http://api.nasa.gov/neo/rest/v1/neo/{id}?api_key={SAHTE_ANAHTAR}"},
        "nasa_jpl_url": f"https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr={id}",
        "is_potentially_hazardous_asteroid": tehlikeli,
        "estimated_diameter": {"meters": {"estimated_diameter_min": cap_min, "estimated_diameter_max": cap_max}},
        "close_approach_data": [{
            "orbiting_body": "Earth",
            "epoch_date_close_approach": zaman_ms,
            "miss_distance": {"kilometers": str(uzaklik_km)},
            "relative_velocity": {"kilometers_per_second": str(hiz_kms)},
        }],
    }


SAHTE_CEVAP = {
    "element_count": 3,
    "near_earth_objects": {
        "2026-11-26": [
            _ham_asteroit("1", "455659 (2005 BO1)", 72_735_857, 127, 284, 25.4, 1795709700000),  # 26 Kasım
        ],
        "2026-11-25": [
            _ham_asteroit("2", "(2026 WK3)", 192_200, 8, 18, 9.1, 1795623300000),                # 25 Kasım, Ay'dan yakın
            _ham_asteroit("3", "99942 Apophis (2004 MN4)", 5_000_000, 310, 690, 7.4, 1795640000000, tehlikeli=True),
        ],
    },
}


@pytest.fixture
def sahte_nasa(monkeypatch):
    """NASA'nın vereceği cevabı test belirler: durum["kod"] ve durum["govde"]."""
    durum = {"kod": 200, "govde": SAHTE_CEVAP, "istekler": []}
    monkeypatch.setattr(neo, "NASA_API_KEY", SAHTE_ANAHTAR)

    def isleyici(istek):
        durum["istekler"].append(istek)
        return httpx.Response(durum["kod"], json=durum["govde"])

    gercek = httpx.AsyncClient

    class SahteIstemci(gercek):
        def __init__(self, **ayarlar):
            super().__init__(transport=httpx.MockTransport(isleyici), **ayarlar)

    monkeypatch.setattr(httpx, "AsyncClient", SahteIstemci)
    return durum


def test_asteroitler_zamana_gore_sirali_ve_donusturulmus(sahte_nasa):
    sonuc = asyncio.run(neo.yaklasan_asteroitler(date(2026, 11, 25)))
    adlar = [a["ad"] for a in sonuc["asteroitler"]]
    assert adlar == ["2026 WK3", "2004 MN4", "2005 BO1"]   # zamana göre; parantez içi kısa ad

    yakin = sonuc["asteroitler"][0]
    assert yakin["ay_kati"] == pytest.approx(0.5, abs=0.01)
    assert yakin["uzaklik_metni"] == "Ay'dan daha yakın!"
    assert yakin["boyut_metni"] == "Bir otobüs kadar"         # ortalama 13 m
    assert yakin["hiz_metni"] == "Bir tüfek mermisinden 9 kat hızlı"


def test_ozet(sahte_nasa):
    ozet = asyncio.run(neo.yaklasan_asteroitler(date(2026, 11, 25)))["ozet"]
    assert ozet == {"toplam": 3, "aydan_yakin": 1, "tehlikeli": 1,
                    "en_yakin": "2", "en_buyuk": "3", "en_hizli": "1"}


def test_nasa_anahtari_kullaniliyor_ama_tarayiciya_gitmiyor(istemci, sahte_nasa):
    cevap = istemci.get("/api/asteroitler")
    assert cevap.status_code == 200
    # Anahtar NASA'ya gönderildi...
    assert sahte_nasa["istekler"][0].url.params["api_key"] == SAHTE_ANAHTAR
    # ...ama tarayıcıya giden cevapta hiçbir yerde yok
    assert SAHTE_ANAHTAR not in cevap.text
    assert "links" not in cevap.text


def test_nasa_hata_verirse_anahtar_sizmaz(istemci, sahte_nasa):
    sahte_nasa["kod"], sahte_nasa["govde"] = 403, {"error": "API_KEY_INVALID"}
    cevap = istemci.get("/api/asteroitler")
    assert cevap.status_code == 502
    assert "HTTP 403" in cevap.json()["detail"]
    assert SAHTE_ANAHTAR not in cevap.text


def test_bos_hafta(sahte_nasa):
    sahte_nasa["govde"] = {"element_count": 0, "near_earth_objects": {}}
    sonuc = asyncio.run(neo.yaklasan_asteroitler(date(2026, 11, 25)))
    assert sonuc["asteroitler"] == [] and sonuc["ozet"] is None


@pytest.mark.parametrize("metre, metin", [
    (2, "Bir araba kadar"), (10, "Bir otobüs kadar"), (60, "Galata Kulesi kadar"),
    (100, "Bir futbol sahası kadar"), (330, "Eyfel Kulesi kadar"), (5000, "Bir dağ kadar"),
])
def test_boyut_karsilastirma(metre, metin):
    assert neo.boyut_karsilastirma(metre) == metin


@pytest.mark.parametrize("kms, metin", [
    (0.4, "Bir yolcu uçağından 2 kat hızlı"),   # gerçek bir örnek: 2015 BG4
    (1.1, "Bir tüfek mermisi kadar hızlı"),
    (25.4, "Bir tüfek mermisinden 25 kat hızlı"),
])
def test_hiz_karsilastirma(kms, metin):
    assert neo.hiz_karsilastirma(kms) == metin


def test_uzaklik_karsilastirma():
    assert neo.uzaklik_karsilastirma(0.4) == "Ay'dan daha yakın!"
    assert neo.uzaklik_karsilastirma(3.25) == "Ay'ın 3,2 katı uzaklıkta"
