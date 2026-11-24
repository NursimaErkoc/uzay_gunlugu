"""
E-posta gönderici testleri. Gerçek e-posta gitmez: httpx.post'u sahtesiyle değiştiriyoruz.
"""
import httpx
import pytest

from app import mailer


@pytest.fixture
def resend_ayarli(monkeypatch):
    monkeypatch.setattr(mailer, "RESEND_API_KEY", "re_test_anahtari")
    monkeypatch.setattr(mailer, "HATIRLATMA_ALICISI", "ben@ornek.com")


def _sahte_post(monkeypatch, durum_kodu, govde=None):
    giden = []

    def sahte(url, headers, json, timeout):
        giden.append({"url": url, "headers": headers, "json": json})
        return httpx.Response(durum_kodu, json=govde or {"id": "123"})
    monkeypatch.setattr(mailer.httpx, "post", sahte)
    return giden


def test_resend_anahtari_varsa_resend_kullanilir(resend_ayarli):
    assert mailer.yontem() == "resend"


def test_hicbir_ayar_yoksa_gonderilmez(monkeypatch):
    monkeypatch.setattr(mailer, "RESEND_API_KEY", "")
    monkeypatch.setattr(mailer, "GMAIL_ADRESI", "")
    monkeypatch.setattr(mailer, "GMAIL_UYGULAMA_SIFRESI", "")
    assert mailer.ayarli_mi() is False
    with pytest.raises(mailer.EpostaHatasi):
        mailer.gonder("konu", "metin", "<p>html</p>")


def test_resend_istegi_dogru_hazirlanir(monkeypatch, resend_ayarli):
    giden = _sahte_post(monkeypatch, 200)
    mailer.gonder("Konu", "düz metin", "<p>html</p>")

    istek = giden[0]
    assert istek["url"] == "https://api.resend.com/emails"
    assert istek["headers"]["Authorization"] == "Bearer re_test_anahtari"
    assert istek["json"]["to"] == ["ben@ornek.com"]
    assert istek["json"]["subject"] == "Konu"
    assert istek["json"]["html"] == "<p>html</p>"


def test_resend_reddederse_anlasilir_hata(monkeypatch, resend_ayarli):
    _sahte_post(monkeypatch, 403, {"message": "You can only send testing emails to your own email address"})
    with pytest.raises(mailer.EpostaHatasi, match="own email address"):
        mailer.gonder("konu", "metin", "<p>html</p>")
