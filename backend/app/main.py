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
import secrets
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import cache, db, mailer
from app.config import PROJE_KLASORU, YONETICI_ANAHTARI
from app.services import ceviri, events, facts, gokyuzu, iss, nasa, news, reminders


# ---------------------------------------------------------------------
# Zamanlayıcı: arka planda dakikada bir "zamanı gelen hatırlatma var mı?" diye bakar
# ---------------------------------------------------------------------
async def zamanlayici():
    while True:
        try:
            sayi = await reminders.bekleyenleri_gonder()
            if sayi:
                print(f"[zamanlayıcı] {sayi} hatırlatma e-postası gönderildi")
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


@app.middleware("http")
async def tarayici_onbellegi(istek, sonraki):
    """
    Sayfa dosyaları (HTML/CSS/JS) için tarayıcıya "her seferinde değişmiş mi diye sor" diyoruz.
    Yoksa site güncellendiğinde tarayıcı eski style.css'i yeni sayfayla kullanabilir ve görünüm bozulur.
    Dosya değişmediyse sunucu kısa bir "304 Değişmedi" cevabı verir; yani yavaşlatmaz.
    """
    cevap = await sonraki(istek)
    if not istek.url.path.startswith("/api/"):
        cevap.headers["Cache-Control"] = "no-cache"
    return cevap


@app.get("/api/saglik", tags=["Genel"])
def saglik_kontrolu():
    """Sunucu ayakta mı? Dış servislerin son hataları da burada görünür (sorun ararken işe yarar)."""
    return {
        "durum": "çalışıyor",
        "ceviri_son_hatalar": ceviri.son_hatalar,
        "mymemory_eposta_tanimli": bool(ceviri.MYMEMORY_EPOSTA),   # adresin kendisini göstermiyoruz
        "iss_tle": iss.durum,   # ISS yörünge verisi hangi kaynaktan geldi, hangi kaynaklar hata verdi
    }


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


@app.get("/api/gece", tags=["Gökyüzü"])
def bu_gece_gokyuzu(
    enlem: float = Query(default=39.93, ge=-90, le=90, description="Enlem (Ankara: 39.93)"),
    boylam: float = Query(default=32.86, ge=-180, le=180, description="Boylam (Ankara: 32.86)"),
):
    """Bu gecenin gökyüzü: Ay evresi, gün batımı/doğumu, görünen gezegenler."""
    # Gizlilik ve önbellek için konumu 1 ondalığa yuvarlıyoruz (~10 km). Bu hassasiyet
    # hesaplar için yeterli (saatler en fazla birkaç saniye değişir) ve kimsenin tam
    # konumu sunucuda kalmaz. Aynı bölgeden gelen istekler de aynı önbelleği kullanır.
    enlem, boylam = round(enlem, 1), round(boylam, 1)
    anahtar = f"gece:{enlem}:{boylam}"
    sonuc = cache.getir(anahtar)
    if sonuc is None:
        sonuc = gokyuzu.bu_gece(enlem, boylam)
        cache.kaydet(anahtar, sonuc, 10 * 60)   # 10 dakika
    return sonuc


@app.get("/api/iss", tags=["ISS"])
async def iss_nerede():
    """ISS'in şu anki konumu, yüksekliği, hızı ve yörünge izi (yörünge verisinden hesaplanır)."""
    try:
        return await iss.iss_konumu()
    except iss.IssHatasi as hata:
        raise HTTPException(status_code=502, detail=str(hata))


@app.get("/api/iss/gecisler", tags=["ISS"])
async def iss_gecisleri(
    enlem: float = Query(default=39.93, ge=-90, le=90, description="Enlem (Ankara: 39.93)"),
    boylam: float = Query(default=32.86, ge=-180, le=180, description="Boylam (Ankara: 32.86)"),
):
    """Önümüzdeki 10 günde ISS'in bu konumdan çıplak gözle görülebileceği geçişler."""
    enlem, boylam = round(enlem, 1), round(boylam, 1)   # gizlilik + önbellek (bkz. /api/gece)
    anahtar = f"iss-gecis:{enlem}:{boylam}"
    sonuc = cache.getir(anahtar)
    if sonuc is None:
        try:
            sonuc = await iss.gorunur_gecisler(enlem, boylam)
        except iss.IssHatasi as hata:
            raise HTTPException(status_code=502, detail=str(hata))
        cache.kaydet(anahtar, sonuc, 60 * 60)   # 1 saat (geçmişte kalan geçişler tarayıcıda ayıklanıyor)
    return sonuc


@app.get("/api/uzaydakiler", tags=["ISS"])
async def uzaydaki_insanlar():
    """Şu an uzayda bulunan insanlar, istasyonlara göre gruplanmış."""
    try:
        return await iss.uzaydakiler()
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Astronot listesi şu an alınamadı")


# ---------------------------------------------------------------------
# Güvenlik: yönetici anahtarı
# İstek başlığında (header)  X-Yonetici-Anahtari: <anahtar>  gönderilmeli.
# .env'de YONETICI_ANAHTARI boşsa (bilgisayarında) kontrol yapılmaz.
# ---------------------------------------------------------------------
def yonetici_mi(anahtar: str | None) -> bool:
    if not YONETICI_ANAHTARI:
        return True
    # compare_digest: karşılaştırma süresinden anahtar tahmin edilemesin diye sabit sürede karşılaştırır
    return anahtar is not None and secrets.compare_digest(anahtar.encode(), YONETICI_ANAHTARI.encode())


def yonetici_gerekli(x_yonetici_anahtari: str | None = Header(default=None)):
    """Bu fonksiyonu Depends(...) ile kullanan uç noktalar sadece yöneticiye açıktır."""
    if not yonetici_mi(x_yonetici_anahtari):
        # 401 = Unauthorized: "kim olduğunu kanıtlamadın"
        raise HTTPException(status_code=401, detail="Bu işlem için yönetici anahtarı gerekli")


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
def hatirlatmalari_listele(x_yonetici_anahtari: str | None = Header(default=None)):
    """Kurulu hatırlatmalar ve e-posta ayarlarının durumu. Liste sadece yöneticiye gösterilir."""
    yetkili = yonetici_mi(x_yonetici_anahtari)
    return {
        "yetkili": yetkili,
        "anahtar_gerekli": bool(YONETICI_ANAHTARI),
        "eposta_ayarli": mailer.ayarli_mi(),
        "alici": mailer.alici_gizli() if yetkili else None,
        "hatirlatmalar": reminders.listele() if yetkili else [],
    }


@app.post("/api/reminders", tags=["Hatırlatmalar"], status_code=201,
          dependencies=[Depends(yonetici_gerekli)])
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


@app.delete("/api/reminders/{hatirlatma_id}", tags=["Hatırlatmalar"], status_code=204,
            dependencies=[Depends(yonetici_gerekli)])
def hatirlatma_sil(hatirlatma_id: int):
    """Hatırlatmayı siler. 204 = 'No Content': başarılı, geri döndürecek bir şey yok."""
    if not reminders.sil(hatirlatma_id):
        raise HTTPException(status_code=404, detail="Hatırlatma bulunamadı")


@app.post("/api/reminders/test", tags=["Hatırlatmalar"], dependencies=[Depends(yonetici_gerekli)])
async def test_epostasi_gonder():
    """E-posta ayarlarını denemek için hemen bir test e-postası gönderir."""
    try:
        await asyncio.to_thread(mailer.gonder, *reminders.test_epostasi())
    except mailer.EpostaHatasi as hata:
        raise HTTPException(status_code=503, detail=str(hata))   # 503 = Service Unavailable
    return {"mesaj": f"Test e-postası gönderildi: {mailer.alici_gizli()}"}


@app.post("/api/gorevler/hatirlatmalar", tags=["Görevler"], dependencies=[Depends(yonetici_gerekli)])
async def zamani_gelenleri_gonder():
    """
    Zamanı gelen hatırlatmaları hemen gönderir.
    İnternette sunucu uyuyabildiği için GitHub Actions bunu 15 dakikada bir çağırır
    (hem sunucuyu uyandırır hem de bekleyen e-postaları yollar).
    """
    return {"gonderilen": await reminders.bekleyenleri_gonder()}


# ---------------------------------------------------------------------
# Frontend: frontend/ klasöründeki HTML/CSS/JS dosyalarını sun.
# DİKKAT: Bu satır en sonda olmalı; yoksa "/" her şeyi yakalar ve
# yukarıdaki /api/... adresleri çalışmaz.
# ---------------------------------------------------------------------
app.mount("/", StaticFiles(directory=PROJE_KLASORU / "frontend", html=True), name="frontend")
