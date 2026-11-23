"""
Hatırlatma testleri. "Şimdi" conftest.py'de 1 Aralık 2026 12:00 UTC olarak sabitlendi.
"""
import asyncio

import pytest
from conftest import ornek_olay

from app.db import baglan
from app.services import reminders


def test_hatirlatma_kurulur_ve_zamani_dogru_hesaplanir():
    h = reminders.olustur(ornek_olay(), "1gun")
    assert h["durum"] == "bekliyor"
    assert h["gonderim_zamani"] == "2026-12-09T15:30:00Z"   # olaydan tam 1 gün önce
    assert h["ne_zaman_metni"] == "1 gün önce"


def test_ayni_hatirlatma_iki_kez_kurulamaz():
    reminders.olustur(ornek_olay(), "1gun")
    with pytest.raises(reminders.AyniHatirlatmaVar):
        reminders.olustur(ornek_olay(), "1gun")


def test_ayni_olaya_farkli_secenekler_kurulabilir():
    reminders.olustur(ornek_olay(), "1gun")
    reminders.olustur(ornek_olay(), "1saat")
    assert len(reminders.listele()) == 2


def test_zamani_gecmis_hatirlatma_kurulamaz():
    # Olay 3 Aralık, "şimdi" 1 Aralık -> 1 hafta önce = 26 Kasım (geçmiş)
    with pytest.raises(reminders.HatirlatmaHatasi, match="geçmiş"):
        reminders.olustur(ornek_olay(tarih="2026-12-03T10:00:00Z"), "1hafta")


def test_tarihi_belirsiz_olaya_hatirlatma_kurulamaz():
    with pytest.raises(reminders.HatirlatmaHatasi):
        reminders.olustur(ornek_olay(kesinlik="ay"), "1gun")


def test_gun_boyu_olayda_1_saat_secilemez():
    with pytest.raises(reminders.HatirlatmaHatasi):
        reminders.olustur(ornek_olay(kesinlik="gun", tarih="2026-12-14T00:00:00Z"), "1saat")


def test_gun_boyu_olay_hatirlatmasi_sabah_9da_gider():
    h = reminders.olustur(ornek_olay(kesinlik="gun", tarih="2026-12-14T00:00:00Z"), "1gun")
    assert h["gonderim_zamani"] == "2026-12-13T06:00:00Z"   # 06:00 UTC = 09:00 Türkiye


def test_silme():
    h = reminders.olustur(ornek_olay(), "1gun")
    assert reminders.sil(h["id"]) is True
    assert reminders.sil(h["id"]) is False   # ikinci kez silinecek bir şey yok
    assert reminders.listele() == []


def _zamani_geldi_yap(hatirlatma_id, gonderim, olay_tarihi=None):
    """Testte 'zamanı gelmiş' bir hatırlatma oluşturmak için veritabanını doğrudan değiştir."""
    with baglan() as db:
        db.execute("UPDATE hatirlatmalar SET gonderim_zamani = ? WHERE id = ?", (gonderim, hatirlatma_id))
        if olay_tarihi:
            db.execute("UPDATE hatirlatmalar SET olay_tarihi = ? WHERE id = ?", (olay_tarihi, hatirlatma_id))


def test_zamani_gelen_hatirlatma_bir_kez_gonderilir(giden_epostalar):
    h = reminders.olustur(ornek_olay(), "1gun")
    _zamani_geldi_yap(h["id"], "2026-12-01T11:59:00Z", olay_tarihi="2026-12-01T13:00:00Z")

    assert asyncio.run(reminders.bekleyenleri_gonder()) == 1
    assert asyncio.run(reminders.bekleyenleri_gonder()) == 0   # ikinci kez gönderilmemeli
    assert len(giden_epostalar) == 1
    assert reminders.getir(h["id"])["durum"] == "gonderildi"
    assert "Test Görevi" in giden_epostalar[0]["konu"]


def test_zamani_gelmeyen_hatirlatma_gonderilmez(giden_epostalar):
    reminders.olustur(ornek_olay(), "1gun")   # gönderim 9 Aralık, şimdi 1 Aralık
    assert asyncio.run(reminders.bekleyenleri_gonder()) == 0
    assert giden_epostalar == []


def test_olay_coktan_gectiyse_eposta_atilmaz(giden_epostalar):
    h = reminders.olustur(ornek_olay(), "1gun")
    _zamani_geldi_yap(h["id"], "2026-11-30T09:00:00Z", olay_tarihi="2026-11-30T10:00:00Z")

    asyncio.run(reminders.bekleyenleri_gonder())
    assert giden_epostalar == []
    assert reminders.getir(h["id"])["durum"] == "kacirildi"


def test_eposta_ayarli_degilse_beklemede_kalir():
    # giden_epostalar fixture'ı yok -> mailer.ayarli_mi() .env'e bakar; testte garanti olsun diye kapatalım
    from app import mailer
    h = reminders.olustur(ornek_olay(), "1gun")
    _zamani_geldi_yap(h["id"], "2026-12-01T11:59:00Z", olay_tarihi="2026-12-01T13:00:00Z")
    eski = mailer.ayarli_mi
    mailer.ayarli_mi = lambda: False
    try:
        assert asyncio.run(reminders.bekleyenleri_gonder()) == 0
    finally:
        mailer.ayarli_mi = eski
    assert reminders.getir(h["id"])["durum"] == "bekliyor"   # ayarlanınca gönderilecek


def test_eposta_icerigi_guvenli():
    h = reminders.olustur(ornek_olay(baslik="<script>alert(1)</script>", aciklama="A & B"), "1gun")
    konu, duz_metin, html = reminders.hatirlatma_epostasi(h)
    assert "<script>" not in html, "Dışarıdan gelen HTML e-postada çalışmamalı"
    assert "&lt;script&gt;" in html
    assert "A &amp; B" in html
    assert "tarihleri son dakikada değişebilir" in duz_metin   # fırlatma notu
