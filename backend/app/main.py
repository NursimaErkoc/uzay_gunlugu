"""
Uzay Günlüğü backend'i, yani kendi API'miz.

Çalıştırmak için (proje kök klasöründe):
    .venv\\Scripts\\uvicorn app.main:app --reload --app-dir backend

Sonra tarayıcıda:
    http://localhost:8000           -> web sitemiz (frontend)
    http://localhost:8000/docs      -> otomatik API dokümantasyonu (Swagger)
    http://localhost:8000/api/apod  -> günün fotoğrafı (JSON)
"""
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from app.config import PROJE_KLASORU
from app.services import facts, nasa, news

app = FastAPI(
    title="Uzay Günlüğü API",
    description="Günün uzay fotoğrafı, bilgisi, haberleri ve olayları",
    version="0.1.0",
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


# ---------------------------------------------------------------------
# Frontend: frontend/ klasöründeki HTML/CSS/JS dosyalarını sun.
# DİKKAT: Bu satır en sonda olmalı; yoksa "/" her şeyi yakalar ve
# yukarıdaki /api/... adresleri çalışmaz.
# ---------------------------------------------------------------------
app.mount("/", StaticFiles(directory=PROJE_KLASORU / "frontend", html=True), name="frontend")
