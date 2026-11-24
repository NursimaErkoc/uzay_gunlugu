"""
Hatırlatma servisi: kur, listele, sil ve zamanı gelenleri e-postayla gönder.
"""
import asyncio
import html
from datetime import datetime, time, timedelta, timezone

from app import mailer
from app.config import SITE_ADRESI
from app.db import ButunlukHatasi, baglan

# Hangi seçenek, olaydan ne kadar önce, ekranda nasıl yazılsın
SECENEKLER = {
    "1saat": (timedelta(hours=1), "1 saat önce"),
    "1gun": (timedelta(days=1), "1 gün önce"),
    "1hafta": (timedelta(days=7), "1 hafta önce"),
}

TURKIYE = timezone(timedelta(hours=3))
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


class HatirlatmaHatasi(Exception):
    """Hatırlatma kurulamadığında (geçersiz seçenek, zamanı geçmiş vb.) fırlatılır."""


class AyniHatirlatmaVar(HatirlatmaHatasi):
    """Aynı olay için aynı hatırlatma zaten kurulu."""


# ---------------------------------------------------------------------
# Zaman yardımcıları
# ---------------------------------------------------------------------
def _simdi() -> datetime:
    return datetime.now(timezone.utc)


def _metne(zaman: datetime) -> str:
    """datetime -> '2026-12-14T00:00:00Z' (veritabanında hep bu biçimde saklıyoruz)"""
    return zaman.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _zamana(metin: str) -> datetime:
    """'2026-12-14T00:00:00Z' -> datetime"""
    return datetime.fromisoformat(metin.replace("Z", "+00:00"))


def turkce_tarih(metin: str, kesinlik: str) -> str:
    """'2026-12-14T00:00:00Z' -> '14 Aralık 2026, 03:00' (Türkiye saati)"""
    t = _zamana(metin).astimezone(TURKIYE)
    tarih = f"{t.day} {AYLAR[t.month - 1]} {t.year}"
    if kesinlik == "gun":
        return tarih
    return f"{tarih}, {'~' if kesinlik == 'saat' else ''}{t:%H:%M}"


# ---------------------------------------------------------------------
# Kur / listele / sil
# ---------------------------------------------------------------------
def olustur(olay: dict, ne_zaman: str) -> dict:
    """Takvimdeki bir olay için hatırlatma kurar."""
    if ne_zaman not in SECENEKLER:
        raise HatirlatmaHatasi("Geçersiz hatırlatma seçeneği")
    if olay["kesinlik"] == "ay":
        raise HatirlatmaHatasi("Bu olayın kesin tarihi henüz belli değil, hatırlatma kurulamaz")
    if ne_zaman == "1saat" and olay["kesinlik"] == "gun":
        raise HatirlatmaHatasi("Saati belli olmayan olaylar için '1 saat önce' seçilemez")

    olay_tarihi = _zamana(olay["tarih"])
    fark = SECENEKLER[ne_zaman][0]
    if olay["kesinlik"] == "gun":
        # Saati belli olmayan ("gün boyu") olaylar: gece yarısı yerine sabah 09:00'da (Türkiye) gönder
        olay_gunu = olay_tarihi.astimezone(TURKIYE).date()
        gonderim = datetime.combine(olay_gunu - fark, time(9, 0), tzinfo=TURKIYE)
    else:
        gonderim = olay_tarihi - fark
    if gonderim <= _simdi():
        raise HatirlatmaHatasi(f"'{SECENEKLER[ne_zaman][1]}' zamanı çoktan geçmiş, daha kısa bir seçenek dene")

    try:
        with baglan() as db:
            # "?" işaretleri: değerleri SQL'e güvenli şekilde yerleştirir (SQL injection saldırısına karşı).
            # Asla f"... VALUES ('{baslik}')" gibi metni doğrudan SQL'e yapıştırma!
            # RETURNING id: eklenen satırın otomatik verilen numarasını geri döndür
            yeni_id = db.execute(
                """INSERT INTO hatirlatmalar
                   (olay_id, baslik, ikon, olay_tarihi, kesinlik, aciklama, alt_bilgi, link,
                    ne_zaman, gonderim_zamani, olusturma)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   RETURNING id""",
                (olay["id"], olay["baslik"], olay.get("ikon"), _metne(olay_tarihi), olay["kesinlik"],
                 olay.get("aciklama"), olay.get("alt_bilgi"), olay.get("link"),
                 ne_zaman, _metne(gonderim), _metne(_simdi())),
            ).fetchone()["id"]
    except ButunlukHatasi as hata:   # UNIQUE kuralı ihlal edildi
        raise AyniHatirlatmaVar("Bu olay için bu hatırlatma zaten kurulu") from hata

    return getir(yeni_id)


def _sozluge(satir: dict) -> dict:
    h = dict(satir)
    h["ne_zaman_metni"] = SECENEKLER[h["ne_zaman"]][1]
    return h


def getir(hatirlatma_id: int) -> dict | None:
    with baglan() as db:
        satir = db.execute("SELECT * FROM hatirlatmalar WHERE id = ?", (hatirlatma_id,)).fetchone()
    return _sozluge(satir) if satir else None


def listele() -> list[dict]:
    """Bekleyenler önce (en yakın tarih üstte), sonra son gönderilenler."""
    with baglan() as db:
        satirlar = db.execute("""
            SELECT * FROM hatirlatmalar
            ORDER BY CASE WHEN durum = 'bekliyor' THEN 0 ELSE 1 END, gonderim_zamani
        """).fetchall()
    return [_sozluge(s) for s in satirlar]


def sil(hatirlatma_id: int) -> bool:
    with baglan() as db:
        imlec = db.execute("DELETE FROM hatirlatmalar WHERE id = ?", (hatirlatma_id,))
    return imlec.rowcount > 0   # silinen satır sayısı


# ---------------------------------------------------------------------
# Zamanı gelenleri gönder (zamanlayıcı dakikada bir çağırır)
# ---------------------------------------------------------------------
async def bekleyenleri_gonder() -> int:
    """Gönderim zamanı gelmiş hatırlatmaları e-postayla yollar. Gönderilen sayısını döndürür."""
    simdi = _metne(_simdi())
    with baglan() as db:
        # Metin olarak karşılaştırma çalışır, çünkü hepsi aynı biçimde (YYYY-AA-GGTSS:DD:SSZ)
        bekleyenler = db.execute(
            "SELECT * FROM hatirlatmalar WHERE durum = 'bekliyor' AND gonderim_zamani <= ?", (simdi,)
        ).fetchall()

    if bekleyenler and not mailer.ayarli_mi():
        return 0   # e-posta ayarlı değil; ayarlanınca gönderilir

    gonderilen = 0
    for satir in bekleyenler:
        h = _sozluge(satir)

        # KİLİT: Aynı anda iki yerden (sunucunun zamanlayıcısı + GitHub Actions) çalışılırsa
        # aynı e-posta iki kez gitmesin. Durumu 'bekliyor'dan 'gonderiliyor'a çevirmeyi deniyoruz;
        # bunu sadece biri başarabilir (WHERE durum = 'bekliyor'). Başaramazsak başkası almış demektir.
        if not _durum_degistir(h["id"], "gonderiliyor", sadece_su_durumdaysa="bekliyor"):
            continue

        # Sunucu uzun süre kapalı kaldıysa ve olay çoktan geçtiyse e-posta atmanın anlamı yok
        if _zamana(h["olay_tarihi"]) < _simdi() - timedelta(hours=1):
            _durum_degistir(h["id"], "kacirildi")
            continue
        try:
            await asyncio.to_thread(mailer.gonder, *hatirlatma_epostasi(h))
        except mailer.EpostaHatasi as hata:
            print(f"[hatırlatma] #{h['id']} gönderilemedi, sonra tekrar denenecek: {hata}")
            _durum_degistir(h["id"], "bekliyor")   # kilidi bırak, sonra tekrar denensin
            break   # muhtemelen ayar/bağlantı sorunu; diğerlerini de şimdi denemeyelim
        _durum_degistir(h["id"], "gonderildi")
        gonderilen += 1
    return gonderilen


def _durum_degistir(hatirlatma_id: int, durum: str, sadece_su_durumdaysa: str | None = None) -> bool:
    """Durumu değiştirir. Değişiklik yapıldıysa True döner."""
    with baglan() as db:
        if sadece_su_durumdaysa:
            imlec = db.execute("UPDATE hatirlatmalar SET durum = ? WHERE id = ? AND durum = ?",
                               (durum, hatirlatma_id, sadece_su_durumdaysa))
        else:
            imlec = db.execute("UPDATE hatirlatmalar SET durum = ? WHERE id = ?", (durum, hatirlatma_id))
    return imlec.rowcount > 0


# ---------------------------------------------------------------------
# E-posta içerikleri
# ---------------------------------------------------------------------
def hatirlatma_epostasi(h: dict) -> tuple[str, str, str]:
    """(konu, düz metin, html) döndürür."""
    zaman = turkce_tarih(h["olay_tarihi"], h["kesinlik"])
    sure = {"1saat": "1 saat sonra", "1gun": "yarın", "1hafta": "1 hafta sonra"}[h["ne_zaman"]]
    konu = f"Hatırlatma: {h['baslik']} {sure}"
    firlatma_notu = ("Not: Fırlatma tarihleri son dakikada değişebilir. Güncel saati takvimden kontrol et."
                     if h["olay_id"].startswith("firlatma:") else "")

    satirlar = [h["baslik"], f"{zaman} (Türkiye saati)"]
    if h["alt_bilgi"]:
        satirlar.append(h["alt_bilgi"])
    if h["aciklama"]:
        satirlar += ["", h["aciklama"]]
    if h["link"]:
        satirlar += ["", f"Canlı yayın: {h['link']}"]
    if firlatma_notu:
        satirlar += ["", firlatma_notu]
    satirlar += ["", f"Uzay takvimi: {SITE_ADRESI}/events.html"]
    duz_metin = "\n".join(satirlar)

    e = html.escape   # dışarıdan gelen metinleri HTML'e koymadan önce zararsızlaştır
    govde = f"""
      <h1 style="margin:0 0 6px;font-size:22px;font-weight:600;line-height:1.3;">{e(h['baslik'])}</h1>
      <p style="margin:0 0 14px;color:#8fa9ff;font-weight:600;letter-spacing:.02em;">{e(zaman)} · Türkiye saati</p>
      {f'<p style="margin:0 0 14px;color:#8890b8;font-size:14px;">{e(h["alt_bilgi"])}</p>' if h["alt_bilgi"] else ""}
      {f'<p style="margin:0 0 18px;line-height:1.65;color:#cfd4f0;">{e(h["aciklama"])}</p>' if h["aciklama"] else ""}
      {f'<p><a href="{e(h["link"])}" style="color:#8fa9ff;">Canlı yayını izle &rarr;</a></p>' if h["link"] else ""}
      {f'<p style="color:#f3c86f;font-size:13px;">{e(firlatma_notu)}</p>' if firlatma_notu else ""}
    """
    return konu, duz_metin, _sablon(govde)


def test_epostasi() -> tuple[str, str, str]:
    govde = """
      <h1 style="margin:0 0 8px;font-size:22px;font-weight:600;">E-posta ayarların çalışıyor</h1>
      <p style="line-height:1.65;color:#cfd4f0;">Bu bir test e-postası. Uzay takviminde kurduğun hatırlatmalar bu adrese gelecek.</p>
    """
    return ("Uzay Günlüğü: test e-postası",
            "E-posta ayarların çalışıyor. Hatırlatmalar bu adrese gelecek.",
            _sablon(govde))


def _sablon(govde: str) -> str:
    """Tüm e-postalar için ortak çerçeve. E-postalarda CSS dosyası çalışmaz, stiller satır içi (inline) yazılır."""
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:24px;background:#010208;font-family:'Segoe UI',Arial,sans-serif;">
  <div style="max-width:560px;margin:0 auto;background:#080b1a;color:#e6e9fb;border-radius:18px;padding:28px;border:1px solid #1c2348;">
    <p style="margin:0 0 20px;color:#8890b8;font-size:11px;letter-spacing:.28em;">UZAY GÜNLÜĞÜ &middot; HATIRLATMA</p>
    {govde}
    <hr style="border:0;border-top:1px solid #1c2348;margin:22px 0;">
    <a href="{html.escape(SITE_ADRESI)}/events.html" style="color:#8fa9ff;font-size:14px;">Uzay takvimini aç &rarr;</a>
  </div>
</body></html>"""
