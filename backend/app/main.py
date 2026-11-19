"""
Uzay Günlüğü backend'i, yani kendi API'miz.

Çalıştırmak için (proje kök klasöründe):
    .venv\\Scripts\\uvicorn app.main:app --reload --app-dir backend

Sonra tarayıcıda:
    http://localhost:8000/docs      -> otomatik API dokümantasyonu (Swagger)
    http://localhost:8000/api/apod  -> günün fotoğrafı (JSON)
"""
from datetime import date

from fastapi import FastAPI, HTTPException, Query

from app.services import nasa

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
    except nasa.NasaHatasi as hata:
        # 502 = "Bad Gateway": biz sağlamız ama arkadaki servis (NASA) sorun çıkardı
        raise HTTPException(status_code=502, detail=str(hata))
