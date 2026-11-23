"""
Uzay takvimi testleri.
Gökyüzü olayları internetsiz hesaplandığı için gerçek değerlerle test edebiliyoruz:
bilinen astronomik olayların doğru günde çıktığını kontrol ediyoruz.
"""
import asyncio

import httpx

from app.services import events


def _bul(olaylar, baslik_parcasi):
    return [o for o in olaylar if baslik_parcasi in o["baslik"]]


def test_aralik_2026_gokyuzu_olaylari():
    olaylar = events.gokyuzu_olaylari(2026, 12)
    gunler = {o["baslik"]: o["tarih"][:10] for o in olaylar}
    assert gunler["Geminid Meteor Yağmuru"] == "2026-12-14"
    assert gunler["Kış Gündönümü"] == "2026-12-21"
    assert gunler["Dolunay"] == "2026-12-24"


def test_tam_ay_tutulmasi_mart_2026():
    tutulma = _bul(events.gokyuzu_olaylari(2026, 3), "Ay Tutulması")
    assert len(tutulma) == 1
    assert tutulma[0]["baslik"] == "Tam Ay Tutulması"
    assert tutulma[0]["tarih"].startswith("2026-03-03")


def test_agustos_2027_gunes_tutulmasi_turkiyeden_gorunur():
    tutulma = _bul(events.gokyuzu_olaylari(2027, 8), "Güneş Tutulması")[0]
    assert tutulma["tarih"].startswith("2027-08-02")
    assert tutulma["turkiyeden_gorunur"] is True


def test_agustos_2026_gunes_tutulmasi_turkiyeden_gorunmez():
    tutulma = _bul(events.gokyuzu_olaylari(2026, 8), "Güneş Tutulması")[0]
    assert tutulma["tarih"].startswith("2026-08-12")
    assert tutulma["turkiyeden_gorunur"] is False


def test_her_ay_en_az_bir_dolunay_ve_yeni_ay():
    for ay in range(1, 13):
        olaylar = events.gokyuzu_olaylari(2027, ay)
        assert _bul(olaylar, "Dolunay"), f"{ay}. ayda dolunay yok"
        assert _bul(olaylar, "Yeni Ay"), f"{ay}. ayda yeni ay yok"


def test_olaylar_ay_sinirlarinin_disina_tasmaz():
    for olay in events.gokyuzu_olaylari(2026, 12):
        # Türkiye saatiyle Aralık'ta olmalı (UTC'de 30 Kasım 21:00 sonrası da olabilir)
        assert "2026-11-30T21:00:00" <= olay["tarih"][:19] < "2026-12-31T21:00:00"


def test_kesinlik_cevirisi():
    assert events._kesinlik("MIN") == "dakika"
    assert events._kesinlik("SEC") == "dakika"
    assert events._kesinlik("HR") == "saat"
    assert events._kesinlik("DAY") == "gun"
    assert events._kesinlik("M") == "ay"
    assert events._kesinlik(None) == "ay"


def test_launch_library_coktugunde_gokyuzu_olaylari_yine_gelir(monkeypatch):
    async def bozuk_servis(yol, parametreler):
        raise httpx.ConnectError("internet yok")
    monkeypatch.setattr(events, "_ll2_getir", bozuk_servis)

    sonuc = asyncio.run(events.ayin_olaylari(2026, 12))
    assert sonuc["eksik"] == ["fırlatmalar", "uzay etkinlikleri"]
    assert _bul(sonuc["olaylar"], "Geminid"), "Gökyüzü olayları yine de gelmeli"


def test_firlatmalar_ceviriliyor_ve_siralaniyor(monkeypatch):
    ornek_firlatma = {
        "id": "abc", "name": "Falcon 9 | Starlink Group 1", "net": "2026-12-05T10:00:00Z",
        "net_precision": {"abbrev": "MIN"}, "status": {"abbrev": "Go", "name": "Go"},
        "mission": {"name": "Starlink Group 1", "description": "Internet satellites."},
        "rocket": {"configuration": {"full_name": "Falcon 9 Block 5"}},
        "launch_service_provider": {"name": "SpaceX"},
        "pad": {"location": {"name": "Florida"}}, "image": None, "vid_urls": [],
    }

    async def sahte_servis(yol, parametreler):
        return [ornek_firlatma] if yol == "launches" else []
    monkeypatch.setattr(events, "_ll2_getir", sahte_servis)

    sonuc = asyncio.run(events.ayin_olaylari(2026, 12))
    firlatma = _bul(sonuc["olaylar"], "Starlink")[0]
    assert firlatma["id"] == "firlatma:abc"
    assert firlatma["starlink"] is True
    assert firlatma["aciklama"] == "TR: Internet satellites."   # sahte çeviri
    assert firlatma["aciklama_en"] == "Internet satellites."
    assert firlatma["durum"] == "✅ Hazır"
    tarihler = [o["tarih"] for o in sonuc["olaylar"]]
    assert tarihler == sorted(tarihler), "Olaylar tarihe göre sıralı olmalı"
