"""
Bugün Uzay Tarihinde testleri.
Veri dosyasını elle yazdığımız için en çok "dosyada yazım hatası var mı" diye kontrol ediyoruz.
"""
from datetime import date, timedelta

from app.services import uzay_tarihi

KATEGORILER = {
    "İnsanlı Uçuş", "Ay", "Gezegen Keşfi", "Uydular", "Uzay İstasyonları", "Roketler",
    "Teleskoplar", "Gökbilim", "Öncüler", "Türkiye", "Anma",
}


def test_veri_dosyasi_duzgun():
    assert len(uzay_tarihi.OLAYLAR) >= 100
    for olay in uzay_tarihi.OLAYLAR:
        assert set(olay) == {"tarih", "yil", "kategori", "metin"}, olay
        ay, gun = map(int, olay["tarih"].split("-"))
        date(olay["yil"], ay, gun)                       # geçersiz tarih (ör. 31 Nisan) hata verir
        assert olay["yil"] <= date.today().year, olay
        assert olay["kategori"] in KATEGORILER, olay["kategori"]
        assert olay["metin"].strip().endswith((".", "\"", "”")), olay["metin"]


def test_ayni_olay_iki_kez_yazilmamis():
    anahtarlar = [(o["tarih"], o["yil"], o["metin"]) for o in uzay_tarihi.OLAYLAR]
    assert len(anahtarlar) == len(set(anahtarlar))


def test_olayli_gun():
    sonuc = uzay_tarihi.gunun_olaylari(date(2026, 7, 20))
    assert sonuc["fark"] == 0
    assert sonuc["tarih"] == "2026-07-20"
    ay_inisi = sonuc["olaylar"][0]                       # eskiden yeniye sıralı
    assert ay_inisi["yil"] == 1969
    assert ay_inisi["yil_once"] == 57


def test_olaysiz_gunde_en_yakin_gun_gelir():
    gun = date(2026, 7, 26)                              # bu gün olay yok
    sonuc = uzay_tarihi.gunun_olaylari(gun)
    assert sonuc["fark"] != 0
    # Gerçekten en yakın mı? Daha yakın bir günde olay olmamalı
    for k in range(abs(sonuc["fark"])):
        for yon in (-k, k):
            assert (gun + timedelta(days=yon)).strftime("%m-%d") not in uzay_tarihi.GUNLERE_GORE


def test_yil_gecisinde_de_calisir():
    # 30 Aralık'ta olay yok; en yakını 27 Aralık (3 gün önce) ya da 1 Ocak (2 gün sonra, seneye)
    sonuc = uzay_tarihi.gunun_olaylari(date(2026, 12, 30))
    assert sonuc["tarih"] == "2027-01-01"
    assert sonuc["fark"] == 2
    assert sonuc["olaylar"][0]["yil_once"] == 2027 - 1801


def test_yilin_her_gunu_icin_sonuc_var():
    gun = date(2028, 1, 1)                               # artık yıl: 29 Şubat dahil
    for _ in range(366):
        sonuc = uzay_tarihi.gunun_olaylari(gun)
        assert sonuc["olaylar"]
        assert abs(sonuc["fark"]) <= 10, gun            # bir olay için 10 günden fazla uzağa gitmeyelim
        gun += timedelta(days=1)


def test_api(istemci):
    cevap = istemci.get("/api/uzay-tarihi?tarih=2026-10-04")
    assert cevap.status_code == 200
    olay = cevap.json()["olaylar"][0]
    assert olay["yil"] == 1957 and "Sputnik" in olay["metin"]
    assert istemci.get("/api/uzay-tarihi").status_code == 200
    assert istemci.get("/api/uzay-tarihi?tarih=2026-13-01").status_code == 422
