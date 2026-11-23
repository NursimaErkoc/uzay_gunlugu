"""
Veritabanı: SQLite (Python'un içinde hazır gelen sqlite3 modülü).

SQLite = tek bir dosyada (uzay_gunlugu.db) duran küçük bir veritabanı.
Sunucu gerektirmez, kurulum gerektirmez. Küçük projeler için ideal.

Veritabanıyla SQL (Structured Query Language) diliyle konuşuruz:
    CREATE TABLE  -> tablo oluştur
    INSERT        -> satır ekle
    SELECT        -> satırları oku
    UPDATE        -> satırı güncelle
    DELETE        -> satır sil
"""
import sqlite3
from contextlib import contextmanager

from app.config import VERITABANI


@contextmanager
def baglan():
    """
    Veritabanı bağlantısı açar, iş bitince kaydedip (commit) kapatır.
    Kullanım:
        with baglan() as db:
            db.execute("SELECT ...")
    """
    db = sqlite3.connect(VERITABANI)
    db.row_factory = sqlite3.Row   # satırlara sütun adıyla erişelim: satir["baslik"]
    try:
        yield db
        db.commit()                # değişiklikleri kalıcı yap
    finally:
        db.close()


def tablolari_olustur() -> None:
    """Sunucu açılırken çağrılır. Tablo zaten varsa hiçbir şey yapmaz (IF NOT EXISTS)."""
    with baglan() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS hatirlatmalar (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,  -- otomatik artan numara
                olay_id          TEXT NOT NULL,     -- takvimdeki olayın kimliği
                baslik           TEXT NOT NULL,
                ikon             TEXT,
                olay_tarihi      TEXT NOT NULL,     -- ISO biçimi, UTC: 2026-12-14T00:00:00Z
                kesinlik         TEXT NOT NULL,     -- dakika | saat | gun
                aciklama         TEXT,
                alt_bilgi        TEXT,
                link             TEXT,
                ne_zaman         TEXT NOT NULL,     -- 1saat | 1gun | 1hafta
                gonderim_zamani  TEXT NOT NULL,     -- e-posta ne zaman gitsin (UTC)
                durum            TEXT NOT NULL DEFAULT 'bekliyor',   -- bekliyor | gonderildi | kacirildi
                olusturma        TEXT NOT NULL,
                UNIQUE (olay_id, ne_zaman)          -- aynı olay için aynı hatırlatma iki kez kurulamaz
            )
        """)
