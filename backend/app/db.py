"""
Veritabanı katmanı: iki veritabanını da destekler.

- Bilgisayarında (DATABASE_URL boşsa): SQLite. Tek dosya (uzay_gunlugu.db), kurulum gerektirmez.
- İnternette (DATABASE_URL doluysa):  PostgreSQL (Neon). Sunucu yeniden başlasa da veri kaybolmaz.

Projenin geri kalanı hangisinin kullanıldığını BİLMEZ; hep aynı şekilde çağırır:
    with baglan() as db:
        db.execute("SELECT * FROM hatirlatmalar WHERE id = ?", (5,)).fetchone()

SQL hatırlatması:
    CREATE TABLE -> tablo oluştur     INSERT -> ekle     SELECT -> oku
    UPDATE       -> güncelle          DELETE -> sil
"""
import sqlite3
import ssl
from contextlib import contextmanager
from urllib.parse import unquote, urlparse

import pg8000.dbapi

from app.config import DATABASE_URL, VERITABANI

# "Aynı kayıt zaten var" (UNIQUE ihlali) hatası iki veritabanında farklı sınıflar;
# ikisini birden yakalayabilmek için bir demet (tuple) yapıyoruz:  except ButunlukHatasi:
ButunlukHatasi = (sqlite3.IntegrityError, pg8000.dbapi.IntegrityError)


def postgres_mi() -> bool:
    return bool(DATABASE_URL)


class _Imlec:
    """Her iki veritabanının sonucunu da aynı biçime (sözlük listesi) çeviren küçük sarmalayıcı."""

    def __init__(self, ham_imlec):
        self._imlec = ham_imlec
        self.rowcount = ham_imlec.rowcount   # etkilenen satır sayısı (UPDATE/DELETE)

    def _sozluge(self, satir):
        if satir is None:
            return None
        sutunlar = [s[0] for s in self._imlec.description]
        return dict(zip(sutunlar, satir))

    def fetchone(self):
        return self._sozluge(self._imlec.fetchone())

    def fetchall(self):
        return [self._sozluge(s) for s in self._imlec.fetchall()]


class _Baglanti:
    def __init__(self, ham_baglanti):
        self._baglanti = ham_baglanti

    def execute(self, sql: str, parametreler: tuple = ()) -> _Imlec:
        if postgres_mi():
            # SQLite "?" kullanır, pg8000 "%s". Kodda hep "?" yazıyoruz, burada çeviriyoruz.
            sql = sql.replace("?", "%s")
        imlec = self._baglanti.cursor()
        imlec.execute(sql, parametreler)
        return _Imlec(imlec)


def _postgres_baglantisi():
    # postgresql://kullanici:sifre@sunucu/veritabani?sslmode=require  ->  parçalarına ayır
    adres = urlparse(DATABASE_URL)
    return pg8000.dbapi.connect(
        user=unquote(adres.username or ""),
        password=unquote(adres.password or ""),
        host=adres.hostname,
        port=adres.port or 5432,
        database=adres.path.lstrip("/"),
        ssl_context=ssl.create_default_context(),   # bulut veritabanına şifreli bağlan
        timeout=20,
    )


@contextmanager
def baglan():
    """Bağlantı açar; iş bitince kaydeder (commit) ve kapatır. Hata olursa değişiklikleri geri alır."""
    ham = _postgres_baglantisi() if postgres_mi() else sqlite3.connect(VERITABANI)
    try:
        yield _Baglanti(ham)
        ham.commit()      # değişiklikleri kalıcı yap
    except Exception:
        ham.rollback()    # yarım kalan değişiklikleri geri al
        raise
    finally:
        ham.close()


def tablolari_olustur() -> None:
    """Sunucu açılırken çağrılır. Tablo zaten varsa hiçbir şey yapmaz (IF NOT EXISTS)."""
    # Otomatik artan numara iki veritabanında farklı yazılıyor
    id_sutunu = "SERIAL PRIMARY KEY" if postgres_mi() else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with baglan() as db:
        db.execute(f"""
            CREATE TABLE IF NOT EXISTS hatirlatmalar (
                id               {id_sutunu},
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
                durum            TEXT NOT NULL DEFAULT 'bekliyor',   -- bekliyor | gonderiliyor | gonderildi | kacirildi
                olusturma        TEXT NOT NULL,
                UNIQUE (olay_id, ne_zaman)          -- aynı olay için aynı hatırlatma iki kez kurulamaz
            )
        """)
