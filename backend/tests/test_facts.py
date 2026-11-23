"""Günün bilgisi testleri."""
from datetime import date, timedelta

from app.services import facts


def test_bilgi_dosyasi_dolu_ve_duzgun():
    assert len(facts.BILGILER) >= 30
    for bilgi in facts.BILGILER:
        assert bilgi["metin"].strip(), "Boş bilgi olmamalı"
        assert bilgi["kategori"].strip(), "Her bilginin kategorisi olmalı"


def test_ayni_gun_hep_ayni_bilgi():
    gun = date(2026, 12, 1)
    assert facts.gunun_bilgisi(gun) == facts.gunun_bilgisi(gun)


def test_ardisik_gunlerde_farkli_bilgi():
    bugun = date(2026, 12, 1)
    yarin = bugun + timedelta(days=1)
    assert facts.gunun_bilgisi(bugun)["metin"] != facts.gunun_bilgisi(yarin)["metin"]


def test_yilin_her_gunu_icin_bilgi_var():
    # 366 günün hiçbiri hata vermemeli (artık yıl dahil)
    gun = date(2028, 1, 1)
    for _ in range(366):
        assert facts.gunun_bilgisi(gun)["metin"]
        gun += timedelta(days=1)
