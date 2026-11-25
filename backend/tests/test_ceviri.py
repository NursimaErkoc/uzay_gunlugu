"""
Çeviri servisi testleri. Gerçek çeviri servislerine bağlanmıyoruz; Google ve MyMemory'yi
sahte fonksiyonlarla değiştiriyoruz.

DİKKAT: conftest.py her testte turkceye_cevir'i sahtesiyle değiştiriyor. Burada GERÇEK
fonksiyonu test etmek istediğimiz için, dosya yüklenirken (değiştirilmeden önce) bir kopyasını alıyoruz.
"""
import asyncio

from app import cache
from app.services import ceviri
from app.services.ceviri import turkceye_cevir as gercek_cevir


def _cevir(metin):
    return asyncio.run(gercek_cevir(metin))


def _servisleri_ayarla(monkeypatch, google=None, mymemory=None):
    """Sahte servisler. Her çağrıyı 'cagrilar' listesine yazar ki kaç kez sorulduğunu sayabilelim."""
    cagrilar = []

    async def sahte_google(metin):
        cagrilar.append("google")
        return google

    async def sahte_mymemory(metin):
        cagrilar.append("mymemory")
        return mymemory

    monkeypatch.setattr(ceviri, "_google_ile", sahte_google)
    monkeypatch.setattr(ceviri, "_mymemory_ile", sahte_mymemory)
    return cagrilar


def test_google_calisirsa_ceviri_doner(monkeypatch):
    cagrilar = _servisleri_ayarla(monkeypatch, google="Merhaba dünya")
    assert _cevir("Hello world") == "Merhaba dünya"
    assert cagrilar == ["google"]


def test_ceviri_veritabaninda_kalir_sunucu_yeniden_baslasa_bile(monkeypatch):
    _servisleri_ayarla(monkeypatch, google="Merhaba dünya")
    _cevir("Hello world")

    # Sunucu yeniden başladı: hafıza boş, üstelik Google artık çalışmıyor
    cache._hafiza.clear()
    cagrilar = _servisleri_ayarla(monkeypatch, google=None, mymemory=None)
    assert _cevir("Hello world") == "Merhaba dünya"
    assert cagrilar == [], "Veritabanında olan metin için servislere hiç sorulmamalı"


def test_google_coktugunde_mymemory_kullanilir(monkeypatch):
    cagrilar = _servisleri_ayarla(monkeypatch, google=None, mymemory="Merhaba")
    assert _cevir("Hello") == "Merhaba"
    assert cagrilar == ["google", "mymemory"]


def test_hicbiri_calismazsa_none_ve_kaydedilmez(monkeypatch):
    _servisleri_ayarla(monkeypatch, google=None, mymemory=None)
    assert _cevir("Hello") is None

    # Servis düzelince tekrar denenebilmeli (başarısızlık kaydedilmemiş olmalı)
    cagrilar = _servisleri_ayarla(monkeypatch, google="Merhaba")
    assert _cevir("Hello") == "Merhaba"
    assert cagrilar == ["google"]


def test_bos_metin():
    assert _cevir("") is None
    assert _cevir(None) is None


def test_uzun_metin_cumle_sinirindan_bolunur():
    metin = " ".join(f"This is sentence number {i}." for i in range(60))
    parcalar = ceviri._parcala(metin, 450)
    assert len(parcalar) > 1
    assert all(len(p) <= 450 for p in parcalar)
    assert " ".join(parcalar) == metin, "Bölünürken hiçbir şey kaybolmamalı"
    assert all(p.endswith(".") for p in parcalar), "Cümle ortasından bölünmemeli"


def test_saglik_sayfasi_ceviri_durumunu_gosterir(istemci):
    veri = istemci.get("/api/saglik").json()
    assert veri["durum"] == "çalışıyor"
    assert set(veri["ceviri_son_hatalar"]) == {"google", "mymemory"}


def test_sayfa_dosyalari_onbellekte_bayat_kalmaz(istemci):
    assert istemci.get("/style.css").headers["cache-control"] == "no-cache"
    assert "cache-control" not in istemci.get("/api/fact").headers


class _SahteIstemci:
    """httpx.AsyncClient yerine geçer; gönderilen parametreleri kaydeder, hazır cevap döner."""
    giden = []

    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False

    async def get(self, url, params):
        _SahteIstemci.giden.append(params)
        import httpx
        return httpx.Response(200, json={"responseStatus": 200, "responseData": {"translatedText": "Merhaba &amp; selam"}})


def _mymemory_dene(monkeypatch, eposta):
    _SahteIstemci.giden = []
    monkeypatch.setattr(ceviri.httpx, "AsyncClient", _SahteIstemci)
    monkeypatch.setattr(ceviri, "MYMEMORY_EPOSTA", eposta)
    sonuc = asyncio.run(ceviri._mymemory_ile("Hello and hi"))
    return sonuc, _SahteIstemci.giden


def test_mymemory_eposta_tanimliysa_istege_eklenir(monkeypatch):
    sonuc, giden = _mymemory_dene(monkeypatch, "kota@ornek.com")
    assert giden[0]["de"] == "kota@ornek.com"
    assert giden[0]["langpair"] == "en|tr"
    assert sonuc == "Merhaba & selam", "HTML kodları (&amp;) çözülmeli"


def test_mymemory_eposta_yoksa_gonderilmez(monkeypatch):
    _, giden = _mymemory_dene(monkeypatch, "")
    assert "de" not in giden[0]
