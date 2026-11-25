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


def _servisleri_ayarla(monkeypatch, google=None, mymemory=None, deepl=None):
    """Sahte servisler. Her çağrıyı 'cagrilar' listesine yazar ki kaç kez sorulduğunu sayabilelim."""
    cagrilar = []

    async def sahte_deepl(metin):
        if deepl is not None:   # anahtar tanımlı değilmiş gibi: sadece istenirse çağrıyı say
            cagrilar.append("deepl")
        return deepl

    monkeypatch.setattr(ceviri, "_deepl_ile", sahte_deepl)

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
    assert set(veri["ceviri_son_hatalar"]) == {"deepl", "google", "mymemory"}


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


# ---------------------------------------------------------------------
# DeepL
# ---------------------------------------------------------------------
def test_deepl_varsa_ilk_o_denenir(monkeypatch):
    cagrilar = _servisleri_ayarla(monkeypatch, deepl="Merhaba", google="Selam")
    assert _cevir("Hello from DeepL") == "Merhaba"
    assert cagrilar == ["deepl"]


def test_deepl_olmazsa_googlea_gecer(monkeypatch):
    cagrilar = _servisleri_ayarla(monkeypatch, deepl="", google="Selam")
    assert _cevir("Hello when DeepL fails") == "Selam"
    assert cagrilar == ["deepl", "google"]


def _sahte_deepl_sunucusu(monkeypatch, kod, govde):
    import httpx
    gelen = {}

    def isleyici(istek):
        gelen["adres"] = str(istek.url)
        gelen["baslik"] = istek.headers.get("authorization")
        gelen["govde"] = istek.content.decode()
        return httpx.Response(kod, json=govde)

    gercek = httpx.AsyncClient

    class SahteIstemci(gercek):
        def __init__(self, **ayarlar):
            super().__init__(transport=httpx.MockTransport(isleyici), **ayarlar)

    monkeypatch.setattr(httpx, "AsyncClient", SahteIstemci)
    monkeypatch.setattr(ceviri, "DEEPL_API_KEY", "gizli-anahtar:fx")
    return gelen


def test_deepl_istegi_dogru_bicimde(monkeypatch):
    gelen = _sahte_deepl_sunucusu(monkeypatch, 200, {"translations": [{"text": "Ay'a dönüş"}]})
    assert asyncio.run(ceviri._deepl_ile("Return to the Moon")) == "Ay'a dönüş"
    assert gelen["baslik"] == "DeepL-Auth-Key gizli-anahtar:fx"
    assert '"target_lang":"TR"' in gelen["govde"].replace(" ", "")


def test_deepl_hatasinda_anahtar_gorunmez(monkeypatch):
    _sahte_deepl_sunucusu(monkeypatch, 456, {"message": "Quota exceeded"})
    assert asyncio.run(ceviri._deepl_ile("Hello")) is None
    assert ceviri.son_hatalar["deepl"] == "HTTP 456"
    assert "gizli" not in str(ceviri.son_hatalar)


def test_deepl_anahtari_yoksa_hic_istek_atilmaz(monkeypatch):
    gelen = _sahte_deepl_sunucusu(monkeypatch, 200, {"translations": [{"text": "x"}]})
    monkeypatch.setattr(ceviri, "DEEPL_API_KEY", "")
    assert asyncio.run(ceviri._deepl_ile("Hello")) is None
    assert gelen == {}


def test_saglik_sayfasi_anahtari_gostermez(istemci, monkeypatch):
    monkeypatch.setattr(ceviri, "DEEPL_API_KEY", "gizli-anahtar:fx")
    cevap = istemci.get("/api/saglik").json()
    assert cevap["deepl_anahtar_tanimli"] is True
    assert "gizli" not in str(cevap)


# ---------------------------------------------------------------------
# Haber kaynağındaki bozuk karakterler
# ---------------------------------------------------------------------
def test_bozuk_karakterler_onarilir():
    from app.services.news import bozuk_karakterleri_onar
    assert bozuk_karakterleri_onar("Mentor-ProtÃ©gÃ© Agreement") == "Mentor-Protégé Agreement"
    assert bozuk_karakterleri_onar("NASAâ€™s rover") == "NASA’s rover"
    assert bozuk_karakterleri_onar("Normal başlık") == "Normal başlık"   # sağlam metne dokunma
    assert bozuk_karakterleri_onar(None) is None
