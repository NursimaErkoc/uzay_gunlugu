"""
API testleri: sahte bir tarayıcıyla (TestClient) uç noktalara istek atıp
durum kodlarını ve cevapları kontrol ediyoruz.
"""
import pytest
from conftest import ornek_olay

from app.services import events


@pytest.fixture
def sahte_takvim(monkeypatch):
    """/api/events ve hatırlatma kurma, internete çıkmadan bu sahte takvimi kullansın."""
    async def takvim(yil, ay):
        return {"ay": f"{yil}-{ay:02d}", "olaylar": [ornek_olay()], "eksik": []}
    monkeypatch.setattr(events, "ayin_olaylari", takvim)


def test_saglik(istemci):
    cevap = istemci.get("/api/saglik")
    assert cevap.status_code == 200


def test_gunun_bilgisi(istemci):
    cevap = istemci.get("/api/fact")
    assert cevap.status_code == 200
    assert cevap.json()["metin"]


@pytest.mark.parametrize("ay", ["2026-13", "2026-1", "abc", "26-12"])
def test_hatali_ay_reddedilir(istemci, ay):
    assert istemci.get(f"/api/events?ay={ay}").status_code == 422


def test_hatali_haber_adedi_reddedilir(istemci):
    assert istemci.get("/api/news?adet=50").status_code == 422


def test_frontend_sayfalari_sunuluyor(istemci):
    for sayfa in ["/", "/events.html", "/style.css", "/app.js", "/events.js", "/gokyuzu.html", "/gokyuzu.js", "/iss.html", "/iss.js", "/asteroitler.html", "/asteroitler.js", "/dunya.html", "/dunya.js"]:
        assert istemci.get(sayfa).status_code == 200, sayfa


def test_hatirlatma_akisi(istemci, sahte_takvim):
    istek = {"olay_id": "firlatma:test-1", "ay": "2026-12", "ne_zaman": "1gun"}

    # Kur -> 201
    cevap = istemci.post("/api/reminders", json=istek)
    assert cevap.status_code == 201
    hatirlatma_id = cevap.json()["id"]

    # Aynısı -> 409
    assert istemci.post("/api/reminders", json=istek).status_code == 409

    # Listede görünüyor
    liste = istemci.get("/api/reminders").json()["hatirlatmalar"]
    assert [h["id"] for h in liste] == [hatirlatma_id]

    # Sil -> 204, tekrar sil -> 404
    assert istemci.delete(f"/api/reminders/{hatirlatma_id}").status_code == 204
    assert istemci.delete(f"/api/reminders/{hatirlatma_id}").status_code == 404


def test_olmayan_olaya_hatirlatma_kurulamaz(istemci, sahte_takvim):
    istek = {"olay_id": "uydurma:olay", "ay": "2026-12", "ne_zaman": "1gun"}
    assert istemci.post("/api/reminders", json=istek).status_code == 404


def test_gecersiz_hatirlatma_secenegi(istemci, sahte_takvim):
    istek = {"olay_id": "firlatma:test-1", "ay": "2026-12", "ne_zaman": "5dakika"}
    assert istemci.post("/api/reminders", json=istek).status_code == 422


def test_test_epostasi(istemci, giden_epostalar):
    cevap = istemci.post("/api/reminders/test")
    assert cevap.status_code == 200
    assert len(giden_epostalar) == 1
