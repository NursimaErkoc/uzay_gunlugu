"""
NASA APOD testleri.
NASA'ya gerçekten bağlanmıyoruz: NASA'nın göndereceği cevabın küçük bir örneğini
elle yazıp, onu doğru ayıklayıp ayıklamadığımızı kontrol ediyoruz.
"""
from app.services import nasa

ORNEK_YAZI = {
    "date": "2024-04-08T00:00:00",
    "title": {"rendered": "APOD: 2024 April 8 &#8211; The Changing Ion Tail of Comet Pons Brooks"},
    "link": "https://science.nasa.gov/image-article/apod-2024-april-8/",
    "featured_image_url": "https://assets.science.nasa.gov/comet.jpg?w=6000&h=4800&fit=clip",
    "content": {"rendered": """
        <h1 class="display-48">The Changing Ion Tail</h1>
        <p class="p-md margin-0 media-detail-hero__description">
            <strong>Explanation:</strong> How does a <a href="https://x">comet tail</a> change ?
            It depends on the comet.<br /> Total Eclipse Imagery: <a href="y">Notable Submissions</a>
        </p>
        <table><tr><td>Image Credit &amp; Copyright: <a href="z">Shengyu Li</a> &amp; Shaining</td></tr>
        <tr><td>Authors &amp; editors: Robert Nemiroff</td></tr></table>
    """},
}


def test_baslik_apod_on_eki_temizlenir():
    sonuc = nasa._sadelestir(ORNEK_YAZI)
    assert sonuc["baslik"] == "The Changing Ion Tail of Comet Pons Brooks"
    assert sonuc["tarih"] == "2024-04-08"


def test_gorsel_adresleri():
    sonuc = nasa._sadelestir(ORNEK_YAZI)
    assert sonuc["tur"] == "image"
    assert sonuc["hd_url"] == "https://assets.science.nasa.gov/comet.jpg"
    assert sonuc["url"] == "https://assets.science.nasa.gov/comet.jpg?w=1600&fit=clip"


def test_aciklama_html_ve_fazlaliklardan_temizlenir():
    aciklama = nasa._sadelestir(ORNEK_YAZI)["aciklama"]
    assert aciklama == "How does a comet tail change? It depends on the comet."
    assert "<" not in aciklama          # HTML etiketi kalmamalı
    assert "Explanation" not in aciklama
    assert "Notable" not in aciklama    # <br> sonrası ekstra linkler atılmalı


def test_telif_bulunur():
    assert nasa._sadelestir(ORNEK_YAZI)["telif"] == "Shengyu Li & Shaining"


def test_gorsel_yoksa_video_sayilir():
    yazi = {**ORNEK_YAZI, "featured_image_url": None}
    sonuc = nasa._sadelestir(yazi)
    assert sonuc["tur"] == "video"
    assert sonuc["url"] is None


def test_apod_baslamadan_onceki_tarih_404(istemci, monkeypatch):
    """1995'ten önceki bir doğum günü sorulursa NASA'ya hiç gidilmeden 404 dönmeli."""
    def internete_cikma(*args, **kwargs):
        raise AssertionError("NASA'ya istek atılmamalıydı")
    monkeypatch.setattr(nasa.httpx, "AsyncClient", internete_cikma)

    cevap = istemci.get("/api/apod?tarih=1990-05-12")
    assert cevap.status_code == 404
    assert "1995" in cevap.json()["detail"]
