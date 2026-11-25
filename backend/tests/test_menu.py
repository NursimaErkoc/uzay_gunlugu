"""
Menü testleri: menü her sayfaya elle kopyalandığı için, yeni sayfa eklerken birini unutmak kolay.
Bu testler 'her sayfada aynı menü var mı, bağlantılar çalışıyor mu' diye kontrol eder.
"""
import re

import pytest

from app.config import PROJE_KLASORU

FRONTEND = PROJE_KLASORU / "frontend"
SAYFALAR = sorted(p.name for p in FRONTEND.glob("*.html") if p.name != "cevrimdisi.html")


def _menu(sayfa):
    html = (FRONTEND / sayfa).read_text(encoding="utf-8")
    bulunan = re.search(r'<nav class="menu">(.*?)</nav>', html, re.S)
    assert bulunan, f"{sayfa}: menü yok"
    return bulunan.group(1)


def _baglantilar(menu):
    return re.findall(r'<a href="([^"]+)"', menu)


def test_her_sayfada_ayni_baglantilar_ayni_sirada():
    ilk = _baglantilar(_menu(SAYFALAR[0]))
    for sayfa in SAYFALAR:
        assert _baglantilar(_menu(sayfa)) == ilk, sayfa


def test_menude_her_sayfa_var_ve_dosyalari_mevcut():
    baglantilar = _baglantilar(_menu(SAYFALAR[0]))
    assert sorted(baglantilar) == SAYFALAR       # menüde olmayan sayfa ya da fazladan bağlantı yok
    for adres in baglantilar:
        assert (FRONTEND / adres).exists(), adres


@pytest.mark.parametrize("sayfa", SAYFALAR)
def test_sadece_bulunulan_sayfa_aktif(sayfa):
    menu = _menu(sayfa)
    aktifler = re.findall(r'<a href="([^"]+)" class="aktif"', menu)
    assert aktifler == [sayfa]
    # Aktif sayfa "Keşfet" grubundaysa grubun başlığı da vurgulu olmalı
    grup = re.search(r'<div class="menu-acilir">(.*?)</div>', menu, re.S).group(1)
    baslik_aktif = '<summary class="aktif">' in menu
    assert baslik_aktif == (f'href="{sayfa}"' in grup)


def test_surum_etiketi_her_sayfada_ayni():
    """?v=N: tarayıcı eski CSS/JS'i kullanmasın diye. Bir sayfada unutulursa o sayfa eski stille açılır."""
    surumler = {s: set(re.findall(r'\?v=(\d+)', (FRONTEND / s).read_text(encoding="utf-8"))) for s in SAYFALAR}
    hepsi = set().union(*surumler.values())
    assert len(hepsi) == 1, surumler
