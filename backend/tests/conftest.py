"""
conftest.py: pytest'in her testten önce otomatik okuduğu ortak hazırlık dosyası.

"Fixture" = testlere hazır malzeme sağlayan fonksiyon. autouse=True olanlar
her testte kendiliğinden çalışır.

Altın kural: TESTLER GERÇEK DÜNYAYA DOKUNMAMALI.
- Gerçek veritabanı yerine her test için geçici, boş bir veritabanı
- Gerçek e-posta yerine e-postaları bir listeye toplayan sahte gönderici
- Gerçek çeviri servisi yerine sahte çevirici (internet gerekmez, hızlı)
"monkeypatch" = test süresince bir fonksiyonu/değişkeni geçici olarak değiştirir,
test bitince eski haline döndürür.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import cache, db, mailer
from app.main import app
from app.services import ceviri, reminders

# Testlerde "şimdi" hep bu an olsun: sonuçlar her gün aynı çıksın
SABIT_SIMDI = datetime(2026, 12, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def temiz_ortam(tmp_path, monkeypatch):
    # 1) Geçici veritabanı ve önbellek klasörü (tmp_path: pytest'in verdiği geçici klasör)
    monkeypatch.setattr(db, "DATABASE_URL", "")   # .env'de bulut veritabanı olsa bile testler SQLite kullansın
    monkeypatch.setattr(db, "VERITABANI", tmp_path / "test.db")
    monkeypatch.setattr(cache, "DISK_KLASORU", tmp_path / "onbellek")
    cache._hafiza.clear()
    db.tablolari_olustur()

    # 2) Sahte çeviri: metnin başına "TR:" ekler
    async def sahte_cevir(metin):
        return f"TR: {metin}" if metin else None
    monkeypatch.setattr(ceviri, "turkceye_cevir", sahte_cevir)

    # 3) Sabit "şimdi"
    monkeypatch.setattr(reminders, "_simdi", lambda: SABIT_SIMDI)

    yield
    cache._hafiza.clear()


@pytest.fixture
def giden_epostalar(monkeypatch):
    """E-posta 'gönderilince' buraya eklenir. Test, listeye bakarak ne gittiğini kontrol eder."""
    kutu = []
    monkeypatch.setattr(mailer, "ayarli_mi", lambda: True)
    monkeypatch.setattr(mailer, "gonder", lambda konu, metin, html: kutu.append(
        {"konu": konu, "metin": metin, "html": html}))
    return kutu


@pytest.fixture
def istemci():
    """
    Sahte tarayıcı: sunucuyu gerçekten başlatmadan API'ye istek atmamızı sağlar.
    ('with' kullanmıyoruz ki arka plandaki zamanlayıcı testlerde çalışmasın.)
    """
    return TestClient(app)


def ornek_olay(**degisenler) -> dict:
    """Testlerde kullanmak için hazır bir olay. İstenen alanlar değiştirilebilir."""
    olay = {
        "id": "firlatma:test-1",
        "tur": "firlatma",
        "ikon": "🚀",
        "baslik": "Test Görevi",
        "tarih": "2026-12-10T15:30:00Z",
        "kesinlik": "dakika",
        "aciklama": "Bir test fırlatması",
        "alt_bilgi": "Falcon 9 · SpaceX · Florida",
        "gorsel": None,
        "link": None,
    }
    olay.update(degisenler)
    return olay
