"""
Uygulama (PWA) testleri: telefona kurulabilmek için gereken dosyalar doğru sunuluyor mu?
"""
import json
import re

import pytest

from app.config import PROJE_KLASORU

# Menüsü olan bütün sayfalar (yeni sayfa eklenince kendiliğinden listeye girer)
SAYFALAR = sorted(p.name for p in (PROJE_KLASORU / "frontend").glob("*.html") if p.name != "cevrimdisi.html")


def test_manifest_gecerli_ve_ikonlar_var(istemci):
    cevap = istemci.get("/manifest.json")
    assert cevap.status_code == 200
    manifest = json.loads(cevap.content)
    # Tarayıcıların "kurulabilir" demesi için gereken alanlar
    for alan in ["name", "short_name", "start_url", "display", "icons"]:
        assert manifest[alan], alan
    boyutlar = {i["sizes"] for i in manifest["icons"]}
    assert {"192x192", "512x512"} <= boyutlar
    # Manifest'te adı geçen her ikon gerçekten sunuluyor mu?
    for ikon in manifest["icons"]:
        assert istemci.get("/" + ikon["src"]).status_code == 200, ikon["src"]


def test_service_worker_dogru_turde_ve_her_seferinde_kontrol_edilir(istemci):
    cevap = istemci.get("/sw.js")
    assert cevap.status_code == 200
    # Tarayıcı service worker'ı sadece JavaScript türünde gelirse kabul eder
    assert "javascript" in cevap.headers["content-type"]
    # Güncellemeler hemen fark edilsin
    assert cevap.headers["cache-control"] == "no-cache"


def test_cevrimdisi_sayfasi(istemci):
    cevap = istemci.get("/cevrimdisi.html")
    assert cevap.status_code == 200
    assert "Çevrimdışısın" in cevap.text


@pytest.mark.parametrize("sayfa", SAYFALAR)
def test_her_sayfa_manifeste_bagli(sayfa):
    html = (PROJE_KLASORU / "frontend" / sayfa).read_text(encoding="utf-8")
    assert 'rel="manifest"' in html
    assert 'rel="apple-touch-icon"' in html


def test_service_worker_ozel_bilgileri_kaydetmez():
    """Yöneticiye özel hatırlatma listesi telefonda saklanmamalı; canlı ISS konumu da (anlamsız)."""
    sw = (PROJE_KLASORU / "frontend" / "sw.js").read_text(encoding="utf-8")
    assert re.search(r'startsWith\("/api/reminders"\)\) return false', sw)
    assert '=== "/api/iss") return false' in sw
    assert 'istek.method !== "GET"' in sw
