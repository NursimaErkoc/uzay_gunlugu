"""
ISS testleri. İnternete çıkmamak için sabit bir yörünge verisi (TLE) ve sahte astronot listesi kullanıyoruz.
"""
import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from app.services import events, iss

# 24 Kasım 2026 tarihli gerçek ISS yörünge verisi
TLE = (
    "1 25544U 98067A   26328.88031537  .00004718  00000+0  91905-4 0  9993",
    "2 25544  51.6319 224.8621 0007433  61.9046 298.2693 15.49577477596662",
)
# Bu andaki konumu ayrı bir ISS takip servisinden (wheretheiss.at) kontrol ettik:
# enlem -12.02, boylam -144.22, yükseklik 424.3 km, hız 27560 km/sa, Dünya'nın gölgesinde
KONTROL_ANI = datetime(2026, 11, 25, 8, 47, 58, tzinfo=timezone.utc)


@pytest.fixture
def sabit_tle(monkeypatch):
    async def tle():
        return TLE
    monkeypatch.setattr(iss, "tle_getir", tle)


def test_konum_bagimsiz_servisle_ayni(sabit_tle):
    k = asyncio.run(iss.iss_konumu(KONTROL_ANI))
    assert k["enlem"] == pytest.approx(-12.02, abs=0.2)
    assert k["boylam"] == pytest.approx(-144.22, abs=0.2)
    assert k["yukseklik_km"] == pytest.approx(424.3, abs=2)
    assert k["hiz_kmsa"] == pytest.approx(27560, abs=50)
    assert k["gunes_isiginda"] is False


def test_yorunge_izi(sabit_tle):
    k = asyncio.run(iss.iss_konumu(KONTROL_ANI))
    assert len(k["iz"]) == 136                            # -45 ... +90 dakika
    assert k["iz"][45] == [round(k["enlem"], 3), round(k["boylam"], 3)]   # ortadaki nokta = şu an
    # ISS'in yörünge eğimi 51.6°: hiçbir zaman bundan daha kuzeye/güneye gitmez
    assert all(abs(enlem) <= 52 for enlem, _ in k["iz"])
    assert all(-180 <= boylam <= 180 for _, boylam in k["iz"])


def test_tle_zamani(sabit_tle):
    # TLE'deki "26328.88031537" = 2026 yılının 328. günü, günün %88'i -> 24 Kasım 21:07
    assert asyncio.run(iss.iss_konumu(KONTROL_ANI))["tle_zamani"] == "2026-11-24T21:07:39Z"


def test_iss_api(istemci, sabit_tle):
    cevap = istemci.get("/api/iss")
    assert cevap.status_code == 200
    assert 380 < cevap.json()["yukseklik_km"] < 460


def test_iss_api_veri_alinamazsa_502(istemci, monkeypatch):
    async def bozuk():
        raise iss.IssHatasi("bağlantı yok")
    monkeypatch.setattr(iss, "tle_getir", bozuk)
    assert istemci.get("/api/iss").status_code == 502


# --- Görünür geçişler (ISS'i Gör) ---
# 25 Kasım 2026 tarihli TLE ve Heavens-Above'un (bilinen bir geçiş tahmin sitesi) aynı günlerde
# Ankara için verdiği sonuçlar: 10 günde 12 görünür geçiş, ilki 25 Kasım 16:08:16 UTC (KKB'dan 10°),
# en yükseği 30 Kasım 15:24:39'da 79°.
TLE_25_KASIM = (
    "1 25544U 98067A   26329.13827942  .00005490  00000-0  10559-3 0  9999",
    "2 25544  51.6318 223.5847 0007441  62.8824 297.2922 15.49581740596707",
)


@pytest.fixture(scope="module")
def ankara_gecisleri():
    """Hesap ~1 saniye sürüyor; birkaç test aynı sonucu kullansın diye bir kez hesaplıyoruz."""
    async def tle():
        return TLE_25_KASIM
    gercek = iss.tle_getir
    iss.tle_getir = tle
    try:
        return asyncio.run(iss.gorunur_gecisler(39.93, 32.86, 10, datetime(2026, 11, 25, tzinfo=timezone.utc)))
    finally:
        iss.tle_getir = gercek


def _saniye(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def test_gecis_sayisi_heavens_above_ile_ayni(ankara_gecisleri):
    assert len(ankara_gecisleri["gecisler"]) == 12


def test_ilk_gecis_heavens_above_ile_ayni(ankara_gecisleri):
    ilk = ankara_gecisleri["gecisler"][0]
    assert abs(_saniye(ilk["baslangic"]["zaman"]) - _saniye("2026-11-25T16:08:16Z")) < 30
    assert ilk["baslangic"]["yon"] in ("Kuzey", "Kuzeybatı")
    assert ilk["golgeye_girer"] is True   # Heavens-Above'da da en yüksek noktada bitiyor (gölgeye giriyor)


def test_en_yuksek_gecis(ankara_gecisleri):
    en_yuksek = max(ankara_gecisleri["gecisler"], key=lambda g: g["en_yuksek"]["yukseklik"])
    assert en_yuksek["en_yuksek"]["zaman"].startswith("2026-11-30T15:2")
    assert en_yuksek["en_yuksek"]["yukseklik"] == pytest.approx(79, abs=4)
    assert en_yuksek["parlaklik"] == "Çok parlak"


def test_gecislerin_ic_tutarliligi(ankara_gecisleri):
    for g in ankara_gecisleri["gecisler"]:
        assert g["baslangic"]["zaman"] <= g["en_yuksek"]["zaman"] <= g["bitis"]["zaman"]
        assert g["en_yuksek"]["yukseklik"] >= max(g["baslangic"]["yukseklik"], g["bitis"]["yukseklik"])
        assert all(iss.EN_AZ_YUKSEKLIK <= yukseklik <= 90 for _, yukseklik in g["yol"])
        assert g["sure_sn"] > 0


def test_gecisler_api(istemci, sabit_tle):
    cevap = istemci.get("/api/iss/gecisler?enlem=41.01&boylam=28.98")
    assert cevap.status_code == 200
    assert cevap.json()["konum"] == {"enlem": 41.0, "boylam": 29.0}


def test_gecisler_api_hatali_konum(istemci):
    assert istemci.get("/api/iss/gecisler?enlem=100").status_code == 422


# --- Yörünge verisi kaynakları ---
@pytest.fixture
def sahte_internet(monkeypatch):
    """
    httpx'in gerçek internete çıkmasını engeller. Test, hangi sunucunun ne cevap vereceğini
    'cevaplar' sözlüğüne yazar: {sunucu_adı: (durum_kodu, metin)} ya da {sunucu_adı: "zaman_asimi"}.
    """
    cevaplar = {}
    monkeypatch.setattr(iss, "durum", {"tle_kaynagi": None, "tle_hatalari": {}})   # her test temiz başlasın

    def isleyici(istek):
        cevap = cevaplar.get(istek.url.host, "zaman_asimi")
        if cevap == "zaman_asimi":
            raise httpx.ConnectTimeout("cevap yok", request=istek)
        return httpx.Response(cevap[0], text=cevap[1])

    gercek = httpx.AsyncClient

    class SahteIstemci(gercek):
        def __init__(self, **ayarlar):
            super().__init__(transport=httpx.MockTransport(isleyici), **ayarlar)

    monkeypatch.setattr(httpx, "AsyncClient", SahteIstemci)
    return cevaplar


def test_celestrak_cevap_vermezse_yedek_kaynak(sahte_internet):
    # CelesTrak zaman aşımı verir, ARISS cevap verir
    sahte_internet["live.ariss.org"] = (200, "ISS (ZARYA)\n" + "\n".join(TLE))
    assert asyncio.run(iss.tle_getir()) == TLE
    assert iss.durum["tle_kaynagi"] == "ARISS"
    assert iss.durum["tle_hatalari"]["CelesTrak"] == "ConnectTimeout"


def test_json_kaynak(sahte_internet):
    import json
    sahte_internet["api.wheretheiss.at"] = (200, json.dumps({"line1": TLE[0], "line2": TLE[1]}))
    assert asyncio.run(iss.tle_getir()) == TLE
    assert iss.durum["tle_kaynagi"] == "wheretheiss.at"


def test_hicbir_kaynak_yoksa_eski_kayit(sahte_internet):
    from app import cache
    cache.kaydet("iss:tle:yedek", list(TLE), 60)   # daha önce alınmış eski TLE
    assert asyncio.run(iss.tle_getir()) == TLE
    assert "eski kayıt" in iss.durum["tle_kaynagi"]


def test_hicbir_kaynak_ve_eski_kayit_yoksa_hata(sahte_internet):
    with pytest.raises(iss.IssHatasi):
        asyncio.run(iss.tle_getir())


def test_baska_uydunun_verisi_reddedilir():
    baska_uydu = "1 20580U 90037B   26328.5  .00001  00000+0  50000-4 0  9990\n2 20580  28.4700 100.0 0002 90.0 270.0 15.10"
    with pytest.raises(ValueError):
        iss.tle_ayikla(baska_uydu, "metin")


# --- Uzaydakiler ---
def _astronot(id, ad, **ekstra):
    a = {"id": id, "name": ad, "type": {"name": "Government"}, "date_of_death": None,
         "agency": {"abbrev": "NASA"}, "nationality": [{"alpha_2_code": "US", "name": "USA"}],
         "time_in_space": "P120DT3H", "flights_count": 2, "image": None, "wiki": None}
    a.update(ekstra)
    return a


@pytest.fixture
def sahte_ll2(monkeypatch):
    async def ll2(yol, parametreler):
        if yol == "astronauts":
            return [
                _astronot(1, "Ayşe Yıldız"),
                _astronot(2, "Wang Li", agency={"abbrev": "CNSA"}, nationality=[{"alpha_2_code": "CN"}]),
                _astronot(3, "Yeni Giden"),
                _astronot(4, "Starman", type={"name": "Non-Human"}),
                _astronot(5, "Laika", date_of_death="1957-11-03"),
            ]
        return [
            {"spacestation": {"name": "Tiangong space station"},
             "crew": [{"astronaut": {"id": 2}, "role": {"role": "Commander"}}]},
            {"spacestation": {"name": "International Space Station"},
             "crew": [{"astronaut": {"id": 1}, "role": {"role": "Flight Engineer"}}]},
        ]
    monkeypatch.setattr(events, "_ll2_getir", ll2)


def test_uzaydakiler_gruplanir_ve_insan_olmayanlar_ayiklanir(sahte_ll2):
    sonuc = asyncio.run(iss.uzaydakiler())
    assert sonuc["toplam"] == 3
    gruplar = {g["ad"]: g["kisiler"] for g in sonuc["gruplar"]}
    # ISS ilk sırada
    assert sonuc["gruplar"][0]["ad"] == "Uluslararası Uzay İstasyonu (ISS)"
    ayse = gruplar["Uluslararası Uzay İstasyonu (ISS)"][0]
    assert (ayse["ad"], ayse["ulke"], ayse["gorev"], ayse["uzayda_gun"]) == ("Ayşe Yıldız", "ABD", "Uçuş Mühendisi", 120)
    assert gruplar["Tiangong Uzay İstasyonu (Çin)"][0]["gorev"] == "Komutan"
    assert [k["ad"] for k in gruplar["Yolda ya da başka bir araçta"]] == ["Yeni Giden"]


def test_uzaydakiler_api_hata(istemci, monkeypatch):
    async def bozuk(yol, parametreler):
        raise httpx.ConnectError("bağlantı yok")
    monkeypatch.setattr(events, "_ll2_getir", bozuk)
    assert istemci.get("/api/uzaydakiler").status_code == 502


@pytest.mark.parametrize("sure, gun", [("P224DT13H57M38S", 224), ("PT5H", 0), (None, None)])
def test_gun_sayisi(sure, gun):
    assert iss._gun_sayisi(sure) == gun
