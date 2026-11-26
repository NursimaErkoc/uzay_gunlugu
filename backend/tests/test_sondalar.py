"""
Uzay Sondaları testleri. JPL Horizons'a gerçekten bağlanmıyoruz: Horizons'ın cevabını
taklit eden sahte bir sunucu (httpx.MockTransport) kullanıyoruz.
"""
import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from app.services import sondalar

# Horizons'ın gerçek cevabından kısaltılmış örnek (Voyager 1, 26 Kasım 2026)
ORNEK_SONUC = """
 Date__(UT)__HR:MN                   r        rdot             delta      deldot
********************************************************************************
$$SOE
 2026-Nov-26 12:00      172.4582135956  16.8815551  173.245723024289  22.1221033
 2026-Nov-26 13:00      172.4586198120  16.8815550  173.246255144103  22.1048247
$$EOE
"""
SIMDI = datetime(2026, 11, 26, 12, 34, tzinfo=timezone.utc)


def test_tablo_cozulur():
    assert sondalar.satiri_coz(ORNEK_SONUC) == (172.4582135956, 16.8815551, 173.245723024289, 22.1221033)


def test_tablo_yoksa_hata():
    with pytest.raises(ValueError):
        sondalar.satiri_coz("No ephemeris for target")


@pytest.fixture
def sahte_horizons(monkeypatch):
    """Horizons yerine geçen sahte sunucu.
    bozuk: bu araçlar için hata döner. mesgul: araç kodu -> kaç kez "503 meşgulüm" denecek."""
    bozuk = set()
    istekler = []
    mesgul = {}          # araç kodu -> kaç kez daha 503 dönülecek

    def cevapla(istek: httpx.Request):
        istekler.append(istek)
        kod = istek.url.params["COMMAND"].strip("'")
        if mesgul.get(kod, 0) > 0:
            mesgul[kod] -= 1
            return httpx.Response(503)
        if kod in bozuk:
            return httpx.Response(200, json={"error": "No ephemeris for target"})
        return httpx.Response(200, json={"result": ORNEK_SONUC})

    monkeypatch.setattr(sondalar, "BEKLEME_SN", 0)    # testte beklemeyelim
    gercek_istemci = httpx.AsyncClient
    monkeypatch.setattr(sondalar.httpx, "AsyncClient",
                        lambda **ayar: gercek_istemci(transport=httpx.MockTransport(cevapla), **ayar))
    return bozuk, istekler, mesgul


def test_butun_sondalar_hesaplanir(sahte_horizons):
    _, istekler, _ = sahte_horizons
    sonuc = asyncio.run(sondalar.sondalarin_konumu(SIMDI))

    assert sonuc["zaman"] == "2026-11-26T12:00:00+00:00"        # saat başına yuvarlandı
    assert sonuc["eksik"] == []
    assert len(sonuc["sondalar"]) == len(sondalar.SONDALAR)
    v1 = sonuc["sondalar"][0]
    assert v1["ad"] == "Voyager 1" and "horizons" not in v1
    assert v1["dunya_km"] == pytest.approx(25.917e9, rel=1e-3)   # ~26 milyar km
    assert v1["isik_suresi_sn"] / 3600 == pytest.approx(24.0, abs=0.1)   # ışık yaklaşık 1 günde ulaşıyor
    assert istekler[0].url.params["START_TIME"] == "'2026-11-26 12:00'"


def test_bir_sonda_bozuksa_digerleri_gelir(sahte_horizons):
    bozuk, _, _ = sahte_horizons
    bozuk.add("-98")                                            # New Horizons
    sonuc = asyncio.run(sondalar.sondalarin_konumu(SIMDI))
    assert sonuc["eksik"] == ["New Horizons"]
    assert len(sonuc["sondalar"]) == len(sondalar.SONDALAR) - 1


def test_horizons_mesgulse_yeniden_denenir(sahte_horizons):
    sahte_horizons[2]["-32"] = 2                         # Voyager 2: iki kez 503, sonra cevap
    sonuc = asyncio.run(sondalar.sondalarin_konumu(SIMDI))
    assert sonuc["eksik"] == []


def test_hep_mesgulse_eksik_sayilir(sahte_horizons):
    sahte_horizons[2]["-32"] = 99
    sonuc = asyncio.run(sondalar.sondalarin_konumu(SIMDI))
    assert sonuc["eksik"] == ["Voyager 2"]


def test_ikinci_istek_onbellekten(sahte_horizons):
    _, istekler, _ = sahte_horizons
    asyncio.run(sondalar.sondalarin_konumu(SIMDI))
    ilk = len(istekler)
    asyncio.run(sondalar.sondalarin_konumu(SIMDI.replace(minute=59)))  # aynı saat
    assert len(istekler) == ilk


def test_hepsi_bozuksa_hata(sahte_horizons):
    bozuk, _, _ = sahte_horizons
    bozuk.update(s["horizons"] for s in sondalar.SONDALAR)
    with pytest.raises(sondalar.SondaHatasi):
        asyncio.run(sondalar.sondalarin_konumu(SIMDI))


def test_api_hata_502(istemci, monkeypatch):
    async def hata():
        raise sondalar.SondaHatasi("JPL Horizons'a ulaşılamadı")
    monkeypatch.setattr(sondalar, "sondalarin_konumu", hata)
    assert istemci.get("/api/sondalar").status_code == 502


def test_sonda_bilgileri_eksiksiz():
    kodlar = [s["kod"] for s in sondalar.SONDALAR]
    assert len(kodlar) == len(set(kodlar))
    for s in sondalar.SONDALAR:
        assert s["horizons"].startswith("-")
        assert s["durum"] in ("aktif", "sessiz")
        assert ("son_sinyal" in s) == (s["durum"] == "sessiz")
        assert s["aciklama"].endswith(".")
