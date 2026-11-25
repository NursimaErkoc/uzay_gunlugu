"""
Gök Haritası testleri: gezegen konumları, yıldız verisi ve haritadaki dönüşüm formülü.
"""
import json
import math
from datetime import datetime, timezone

import astronomy as A
import pytest

from app.config import PROJE_KLASORU
from app.services import gok_haritasi

AN = datetime(2026, 11, 25, 20, 0, tzinfo=timezone.utc)
ANKARA = (39.93, 32.86)
VERI = json.loads((PROJE_KLASORU / "frontend" / "veri" / "gok.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------
# gokharitasi.js'teki formülün Python kopyası (ikisi aynı kalmalı!)
# Tarayıcı her yıldız için bunu yapıyor: ra/dec + saat + konum -> yükseklik ve yön
# ---------------------------------------------------------------------
def _ufuk(ra, dec, zaman, enlem, boylam):
    jd = zaman.timestamp() / 86400 + 2440587.5                                  # julyenGunu()
    yildiz_zamani = (280.46061837 + 360.98564736629 * (jd - 2451545) + boylam) % 360  # yerelYildizZamani()
    h, d, f = math.radians(yildiz_zamani - ra), math.radians(dec), math.radians(enlem)
    yukseklik = math.degrees(math.asin(math.sin(f) * math.sin(d) + math.cos(f) * math.cos(d) * math.cos(h)))
    yon = math.degrees(math.atan2(-math.sin(h) * math.cos(d),
                                  math.sin(d) * math.cos(f) - math.cos(d) * math.cos(h) * math.sin(f))) % 360
    return yukseklik, yon


def _aci_farki(a, b):
    return abs((a - b + 180) % 360 - 180)


def test_yedi_cisim_dogru_bilgilerle():
    sonuc = gok_haritasi.cisimler(*ANKARA, AN)
    assert [c["ad"] for c in sonuc["cisimler"]] == ["Güneş", "Ay", "Merkür", "Venüs", "Mars", "Jüpiter", "Satürn"]
    for c in sonuc["cisimler"]:
        assert 0 <= c["ra"] < 360 and -90 <= c["dec"] <= 90
    ay = sonuc["cisimler"][1]
    assert 0 <= ay["aydinlik"] <= 1 and ay["evre"]
    assert sonuc["cisimler"][0]["kadir"] < -26   # Güneş


@pytest.mark.parametrize("saat", [0, 6, 13, 20])
def test_harita_formulu_astronomy_engine_ile_ayni_sonucu_verir(saat):
    """Haritadaki her gezegen, astronomy-engine'in hesapladığı yükseklik ve yönde çizilmeli."""
    an = AN.replace(hour=saat)
    t = A.Time.Make(an.year, an.month, an.day, an.hour, 0, 0)
    gozlemci = A.Observer(*ANKARA, 0)
    for c, (govde, _, _) in zip(gok_haritasi.cisimler(*ANKARA, an)["cisimler"], gok_haritasi.CISIMLER):
        yukseklik, yon = _ufuk(c["ra"], c["dec"], an, *ANKARA)
        esd = A.Equator(govde, t, gozlemci, True, True)
        dogru = A.Horizon(t, gozlemci, esd.ra, esd.dec, A.Refraction.Airless)
        # J2000 ile bugünkü eksen arasında ~0,4° fark var (yalpalama); harita için önemsiz
        assert abs(yukseklik - dogru.altitude) < 0.7, c["ad"]
        if abs(dogru.altitude) < 85:   # tam tepedeyken yön anlamsızlaşır
            assert _aci_farki(yon, dogru.azimuth) < 1.0, c["ad"]


def test_kutup_yildizi_hep_kuzeyde_ve_enlem_kadar_yukarida():
    kutup = next(a for a in VERI["adlar"] if a["ad"] == "Kutup Yıldızı")
    for saat in range(0, 24, 4):
        yukseklik, yon = _ufuk(kutup["ra"], kutup["dec"], AN.replace(hour=saat), *ANKARA)
        assert abs(yukseklik - ANKARA[0]) < 1.0
        assert _aci_farki(yon, 0) < 1.5


def test_yildiz_verisi():
    yildizlar = VERI["yildizlar"]
    assert 2500 < len(yildizlar) < 3200
    assert all(0 <= y[0] < 360 and -90 <= y[1] <= 90 and y[2] <= 5.5 for y in yildizlar)
    assert yildizlar[0][2] == pytest.approx(-1.44)   # en parlak: Sirius
    assert {"Sirius", "Vega", "Kutup Yıldızı", "Betelgeuse"} <= {a["ad"] for a in VERI["adlar"]}


def test_takimyildizlar_turkce_ve_cizgili():
    tk = VERI["takimyildizlar"]
    assert len({t["k"] for t in tk}) == 88
    adlar = {t["k"]: t["ad"] for t in tk}
    assert adlar["UMa"] == "Büyük Ayı" and adlar["Cas"] == "Kassiopeia" and adlar["Sco"] == "Akrep"
    for t in tk:
        assert t["k"] == "Ser" or t["cizgiler"], t["k"]
        for parca in t["cizgiler"]:
            assert len(parca) >= 2


def test_api(istemci):
    cevap = istemci.get("/api/gok-haritasi?enlem=39.93&boylam=32.86&zaman=2026-11-25T20:07:31Z")
    assert cevap.status_code == 200
    veri = cevap.json()
    assert veri["zaman"] == "2026-11-25T20:00:00Z"          # 10 dakikaya yuvarlanır
    assert veri["konum"] == {"enlem": 39.9, "boylam": 32.9}  # gizlilik için 1 ondalık
    assert len(veri["cisimler"]) == 7


def test_api_saat_dilimsiz_zaman_utc_sayilir(istemci):
    assert istemci.get("/api/gok-haritasi?zaman=2026-11-25T20:00:00").json()["zaman"] == "2026-11-25T20:00:00Z"


@pytest.mark.parametrize("sorgu", ["zaman=dun-aksam", "zaman=2300-01-01T00:00:00Z", "enlem=95"])
def test_api_hatali_istek(istemci, sorgu):
    assert istemci.get(f"/api/gok-haritasi?{sorgu}").status_code == 422
