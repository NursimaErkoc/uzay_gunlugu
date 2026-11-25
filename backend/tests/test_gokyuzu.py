"""
Bu Gece Gökyüzü testleri.
Hesaplamalar internetsiz olduğu için gerçek tarihlerle test edebiliyoruz.
"""
from datetime import datetime, timezone

import pytest

from app.services import gokyuzu

ANKARA = (39.93, 32.86)


def _an(*parcalar):
    return datetime(*parcalar, tzinfo=timezone.utc)


def test_dolunay_gecesi():
    # 24 Aralık 2026, 01:28 UTC: dolunay
    sonuc = gokyuzu.bu_gece(*ANKARA, simdi=_an(2026, 12, 24, 1, 28))
    assert sonuc["ay"]["evre"] == "Dolunay"
    assert sonuc["ay"]["aydinlik"] > 0.99


def test_gunduz_sorulunca_bu_aksamin_gecesi():
    # Ankara, 25 Kasım 2026 öğlen (TR 13:00): gün batımı bugün ~17:26 TR (14:26 UTC)
    gunes = gokyuzu.bu_gece(*ANKARA, simdi=_an(2026, 11, 25, 10, 0))["gunes"]
    assert gunes["gun_batimi"].startswith("2026-11-25T14:2")
    assert gunes["gun_dogumu"].startswith("2026-11-26")
    # Sıra doğru mu: gün batımı < tam karanlık < karanlığın bitişi < gün doğumu
    assert gunes["gun_batimi"] < gunes["karanlik_baslangici"] < gunes["karanlik_bitisi"] < gunes["gun_dogumu"]


def test_gece_yarisi_sorulunca_ayni_gece():
    # Saat 02:00 TR (23:00 UTC) iken "bu gece" = dün akşamki gün batımı ile bu sabahki gün doğumu arası
    gunes = gokyuzu.bu_gece(*ANKARA, simdi=_an(2026, 11, 25, 23, 0))["gunes"]
    assert gunes["gun_batimi"].startswith("2026-11-25")
    assert gunes["gun_dogumu"].startswith("2026-11-26")


def test_gorunen_gezegenlerin_bilgileri_tam():
    gezegenler = gokyuzu.bu_gece(*ANKARA, simdi=_an(2026, 11, 25, 10, 0))["gezegenler"]
    assert len(gezegenler) == 5
    gorunenler = [g for g in gezegenler if g["gorunur"]]
    assert gorunenler, "Bu gece en az bir gezegen görünmeli"
    for g in gorunenler:
        assert g["yukseklik"] >= gokyuzu.GORUNUR_YUKSEKLIK
        assert g["yon"] in gokyuzu.YONLER
    # Görünenler listenin başında
    assert gezegenler[: len(gorunenler)] == gorunenler


@pytest.mark.parametrize("simdi, not_parcasi", [
    (_an(2026, 6, 21, 12), "batmıyor"),       # Svalbard'da yaz: gece yarısı güneşi
    (_an(2026, 12, 21, 12), "kutup gecesi"),  # Svalbard'da kış: Güneş hiç doğmuyor
])
def test_kutup_bolgesi_cokmez(simdi, not_parcasi):
    sonuc = gokyuzu.bu_gece(78.0, 15.0, simdi=simdi)
    assert not_parcasi in sonuc["gunes"]["not"]


@pytest.mark.parametrize("aci, ad", [
    (0, "Yeni Ay"), (45, "Büyüyen Hilal"), (90, "İlk Dördün"), (135, "Büyüyen Şişkin Ay"),
    (180, "Dolunay"), (225, "Küçülen Şişkin Ay"), (270, "Son Dördün"), (315, "Küçülen Hilal"), (358, "Yeni Ay"),
])
def test_ay_evresi_adlari(aci, ad):
    assert gokyuzu.ay_evresi_adi(aci) == ad


@pytest.mark.parametrize("azimut, yon", [(0, "Kuzey"), (90, "Doğu"), (135, "Güneydoğu"), (350, "Kuzey"), (260, "Batı")])
def test_yon_adlari(azimut, yon):
    assert gokyuzu.yon_adi(azimut) == yon


# --- API ---
def test_gece_api_varsayilan_ankara(istemci):
    cevap = istemci.get("/api/gece")
    assert cevap.status_code == 200
    veri = cevap.json()
    assert veri["konum"] == {"enlem": 39.9, "boylam": 32.9}
    assert {"gunes", "ay", "gezegenler"} <= veri.keys()


def test_gece_api_konumu_yuvarlar(istemci):
    # Tam konum sunucuda tutulmaz: 1 ondalığa yuvarlanır
    veri = istemci.get("/api/gece?enlem=41.01234&boylam=28.97891").json()
    assert veri["konum"] == {"enlem": 41.0, "boylam": 29.0}


@pytest.mark.parametrize("sorgu", ["enlem=95", "boylam=-200", "enlem=abc"])
def test_gece_api_hatali_konum(istemci, sorgu):
    assert istemci.get(f"/api/gece?{sorgu}").status_code == 422
