"""
Güvenlik ve yayın testleri: yönetici anahtarı, görev uç noktası, çift gönderim kilidi.
"""
import asyncio

import pytest
from conftest import ornek_olay

from app import main
from app.db import baglan
from app.services import events, reminders

ANAHTAR = "cok-gizli-test-anahtari"


@pytest.fixture
def anahtarli_site(monkeypatch):
    """Site internetteymiş gibi: yönetici anahtarı tanımlı."""
    monkeypatch.setattr(main, "YONETICI_ANAHTARI", ANAHTAR)

    async def takvim(yil, ay):
        return {"ay": f"{yil}-{ay:02d}", "olaylar": [ornek_olay()], "eksik": []}
    monkeypatch.setattr(events, "ayin_olaylari", takvim)


ISTEK = {"olay_id": "firlatma:test-1", "ay": "2026-12", "ne_zaman": "1gun"}


def test_anahtarsiz_hatirlatma_kurulamaz(istemci, anahtarli_site):
    assert istemci.post("/api/reminders", json=ISTEK).status_code == 401


def test_yanlis_anahtarla_kurulamaz(istemci, anahtarli_site):
    cevap = istemci.post("/api/reminders", json=ISTEK, headers={"X-Yonetici-Anahtari": "tahmin"})
    assert cevap.status_code == 401


def test_dogru_anahtarla_kurulur(istemci, anahtarli_site):
    cevap = istemci.post("/api/reminders", json=ISTEK, headers={"X-Yonetici-Anahtari": ANAHTAR})
    assert cevap.status_code == 201


def test_anahtarsiz_silinemez_ve_test_epostasi_gonderilemez(istemci, anahtarli_site, giden_epostalar):
    h = reminders.olustur(ornek_olay(), "1gun")
    assert istemci.delete(f"/api/reminders/{h['id']}").status_code == 401
    assert istemci.post("/api/reminders/test").status_code == 401
    assert giden_epostalar == []


def test_ziyaretci_hatirlatma_listesini_goremez(istemci, anahtarli_site):
    reminders.olustur(ornek_olay(), "1gun")
    ziyaretci = istemci.get("/api/reminders").json()
    assert ziyaretci["yetkili"] is False
    assert ziyaretci["hatirlatmalar"] == []
    assert ziyaretci["alici"] is None

    yonetici = istemci.get("/api/reminders", headers={"X-Yonetici-Anahtari": ANAHTAR}).json()
    assert yonetici["yetkili"] is True
    assert len(yonetici["hatirlatmalar"]) == 1


def test_gorev_ucu_anahtar_ister_ve_gonderir(istemci, anahtarli_site, giden_epostalar):
    h = reminders.olustur(ornek_olay(), "1gun")
    with baglan() as db:
        db.execute("UPDATE hatirlatmalar SET gonderim_zamani = ?, olay_tarihi = ? WHERE id = ?",
                   ("2026-12-01T11:00:00Z", "2026-12-01T13:00:00Z", h["id"]))

    assert istemci.post("/api/gorevler/hatirlatmalar").status_code == 401
    cevap = istemci.post("/api/gorevler/hatirlatmalar", headers={"X-Yonetici-Anahtari": ANAHTAR})
    assert cevap.json() == {"gonderilen": 1}
    assert len(giden_epostalar) == 1


def test_ayni_anda_iki_gonderici_ayni_epostayi_iki_kez_gondermez(giden_epostalar):
    h = reminders.olustur(ornek_olay(), "1gun")
    with baglan() as db:
        db.execute("UPDATE hatirlatmalar SET gonderim_zamani = ?, olay_tarihi = ? WHERE id = ?",
                   ("2026-12-01T11:00:00Z", "2026-12-01T13:00:00Z", h["id"]))

    async def iki_gonderici_birden():
        return await asyncio.gather(reminders.bekleyenleri_gonder(), reminders.bekleyenleri_gonder())

    sonuclar = asyncio.run(iki_gonderici_birden())
    assert sum(sonuclar) == 1
    assert len(giden_epostalar) == 1


def test_gonderim_hatasinda_kilit_birakilir(monkeypatch):
    from app import mailer
    h = reminders.olustur(ornek_olay(), "1gun")
    with baglan() as db:
        db.execute("UPDATE hatirlatmalar SET gonderim_zamani = ?, olay_tarihi = ? WHERE id = ?",
                   ("2026-12-01T11:00:00Z", "2026-12-01T13:00:00Z", h["id"]))

    def bozuk_gonder(*_):
        raise mailer.EpostaHatasi("bağlantı yok")
    monkeypatch.setattr(mailer, "ayarli_mi", lambda: True)
    monkeypatch.setattr(mailer, "gonder", bozuk_gonder)

    assert asyncio.run(reminders.bekleyenleri_gonder()) == 0
    assert reminders.getir(h["id"])["durum"] == "bekliyor", "Sonra tekrar denenebilmeli"
