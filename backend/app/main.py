"""
Uzay Günlüğü backend'i, yani kendi API'miz.

Çalıştırmak için (proje kök klasöründe):
    .venv\\Scripts\\uvicorn app.main:app --reload --app-dir backend

Sonra tarayıcıda:
    http://localhost:8000           -> web sitemiz (frontend)
    http://localhost:8000/docs      -> otomatik API dokümantasyonu (Swagger)
    http://localhost:8000/api/apod  -> günün fotoğrafı (JSON)
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import db, mailer
from app.config import PROJE_KLASORU
from app.services import events, facts, nasa, news, reminders


# ---------------------------------------------------------------------
# Zamanlayıcı: arka planda dakikada bir "zamanı gelen hatırlatma var mı?" diye bakar
# ---------------------------------------------------------------------
async def zamanlayici():
    while True:
        try:
            sayi = await reminders.bekleyenleri_gonder()
            if sayi:
                print(f"[zamanlayıcı] {sayi} hatırlatma e-postası gönderildi 📧")
        except Exception as hata:   # zamanlayıcı asla tamamen durmasın
            print(f"[zamanlayıcı] hata: {hata}")
        await asyncio.sleep(60)


@asynccontextmanager
async def yasam_dongusu(app: FastAPI):
    """Sunucu açılırken 'yield'den öncesi, kapanırken sonrası çalışır."""
    db.tablolari_olustur()
    gorev = asyncio.create_task(zamanlayici())   # arka planda başlat
    yield
    gorev.cancel()


app = FastAPI(
    title="Uzay Günlüğü API",
    description="Günün uzay fotoğrafı, bilgisi, haberleri, olayları ve hatırlatmalar",
    version="0.2.0",
    lifespan=yasam_dongusu,
)


@app.get("/api/saglik", tags=["Genel"])
def saglik_kontrolu():
    """Sunucu ayakta mı? Basit bir kontrol."""
    return {"durum": "çalışıyor 🚀"}


@app.get("/api/apod", tags=["NASA"])
async def apod(
    tarih: date | None = Query(
        default=None,
        description="İstersen geçmiş bir gün seç (YYYY-AA-GG). Boş bırakırsan bugün.",
        examples=["2024-04-08"],
    ),
):
    """NASA'nın Günün Astronomi Fotoğrafı (APOD)."""
    try:
        return await nasa.gunun_fotografi(tarih.isoformat() if tarih else None)
    except nasa.ApodBulunamadi as hata:
        # 404 = "Not Found": istenen şey yok
        raise HTTPException(status_code=404, detail=str(hata))
    except nasa.NasaHatasi as hata:
        # 502 = "Bad Gateway": biz sağlamız ama arkadaki servis (NASA) sorun çıkardı
        raise HTTPException(status_code=502, detail=str(hata))


@app.get("/api/fact", tags=["İçerik"])
def gunun_bilgisi():
    """Günün uzay bilgisi (her gün farklı)."""
    return facts.gunun_bilgisi()


@app.get("/api/news", tags=["İçerik"])
async def haberler(
    adet: int = Query(default=6, ge=1, le=12, description="Kaç haber gelsin (1-12)"),
):
    """En güncel uzay haberleri (Türkçe çevirili)."""
    try:
        return await news.son_haberler(adet)
    except news.HaberHatasi as hata:
        raise HTTPException(status_code=502, detail=str(hata))


@app.get("/api/events", tags=["Takvim"])
async def ayin_olaylari(
    ay: str | None = Query(
        default=None,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",   # "YYYY-AA" biçimi (regex)
        description="Hangi ay? Örn. 2026-12. Boş bırakırsan bu ay.",
        examples=["2026-12"],
    ),
):
    """Ayın uzay olayları: gökyüzü olayları, meteor yağmurları, roket fırlatmaları, uzay etkinlikleri."""
    if ay:
        yil, ay_no = map(int, ay.split("-"))
    else:
        bugun = date.today()
        yil, ay_no = bugun.year, bugun.month
    if not 1900 <= yil <= 2100:
        raise HTTPException(status_code=422, detail="Yıl 1900-2100 arasında olmalı")
    return await events.ayin_olaylari(yil, ay_no)


# ---------------------------------------------------------------------
# Hatırlatmalar
# ---------------------------------------------------------------------
class HatirlatmaIstegi(BaseModel):
    """POST /api/reminders isteğinin gövdesi (JSON). Pydantic gelen veriyi otomatik doğrular."""
    olay_id: str = Field(min_length=1, max_length=300, examples=["firlatma:abc-123"])
    ay: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", examples=["2026-12"],
                    description="Olayın takvimde bulunduğu ay")
    ne_zaman: Literal["1saat", "1gun", "1hafta"]


@app.get("/api/reminders", tags=["Hatırlatmalar"])
def hatirlatmalari_listele():
    """Kurulu hatırlatmalar ve e-posta ayarlarının durumu."""
    return {
        "eposta_ayarli": mailer.ayarli_mi(),
        "alici": mailer.alici_gizli(),
        "hatirlatmalar": reminders.listele(),
    }


@app.post("/api/reminders", tags=["Hatırlatmalar"], status_code=201)
async def hatirlatma_kur(istek: HatirlatmaIstegi):
    """
    Takvimdeki bir olay için hatırlatma kurar.
    Güvenlik: olayın bilgilerini tarayıcıdan almıyoruz, sunucuda takvimden kendimiz buluyoruz.
    Böylece kimse sahte bir başlık/metin göndererek e-postanın içeriğini değiştiremez.
    """
    yil, ay_no = map(int, istek.ay.split("-"))
    takvim = await events.ayin_olaylari(yil, ay_no)
    olay = next((o for o in takvim["olaylar"] if o["id"] == istek.olay_id), None)
    if olay is None:
        raise HTTPException(status_code=404, detail="Bu olay takvimde bulunamadı")
    try:
        return reminders.olustur(olay, istek.ne_zaman)
    except reminders.AyniHatirlatmaVar as hata:
        raise HTTPException(status_code=409, detail=str(hata))   # 409 = Conflict (çakışma)
    except reminders.HatirlatmaHatasi as hata:
        raise HTTPException(status_code=422, detail=str(hata))


@app.delete("/api/reminders/{hatirlatma_id}", tags=["Hatırlatmalar"], status_code=204)
def hatirlatma_sil(hatirlatma_id: int):
    """Hatırlatmayı siler. 204 = 'No Content': başarılı, geri döndürecek bir şey yok."""
    if not reminders.sil(hatirlatma_id):
        raise HTTPException(status_code=404, detail="Hatırlatma bulunamadı")


@app.post("/api/reminders/test", tags=["Hatırlatmalar"])
async def test_epostasi_gonder():
    """E-posta ayarlarını denemek için hemen bir test e-postası gönderir."""
    try:
        await asyncio.to_thread(mailer.gonder, *reminders.test_epostasi())
    except mailer.EpostaHatasi as hata:
        raise HTTPException(status_code=503, detail=str(hata))   # 503 = Service Unavailable
    return {"mesaj": f"Test e-postası gönderildi: {mailer.alici_gizli()}"}


# ---------------------------------------------------------------------
# Frontend: frontend/ klasöründeki HTML/CSS/JS dosyalarını sun.
# DİKKAT: Bu satır en sonda olmalı; yoksa "/" her şeyi yakalar ve
# yukarıdaki /api/... adresleri çalışmaz.
# ---------------------------------------------------------------------
app.mount("/", StaticFiles(directory=PROJE_KLASORU / "frontend", html=True), name="frontend")
