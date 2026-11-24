// =====================================================================
// Uzay Günlüğü - ana sayfa
// Görevi: Kendi API'mizden veriyi çekip sayfaya yerleştirmek.
// ikon(), metinTemizle(), yukleniyorHtml(), hataHtml() -> ortak.js'den geliyor.
// =====================================================================

// Sayfadaki elemanları bul (DOM = sayfanın JavaScript'teki karşılığı)
const apodKutusu = document.getElementById("apod-icerik");
const tarihKutusu = document.getElementById("tarih");

// Tarih seçicide bugünden sonrası seçilemesin
tarihKutusu.max = new Date().toISOString().slice(0, 10);

// ---------------------------------------------------------------------
// 1) Günün fotoğrafı
//    async/await: "cevap gelene kadar bekle, ama sayfayı dondurma"
// ---------------------------------------------------------------------
async function apodGetir(tarih) {
  apodKutusu.innerHTML = yukleniyorHtml("Uzaydan veri geliyor");

  // Tarih seçildiyse adrese ekle: /api/apod?tarih=2024-04-08
  const adres = tarih ? `/api/apod?tarih=${tarih}` : "/api/apod";

  try {
    const cevap = await fetch(adres);          // isteği gönder
    const veri = await cevap.json();           // gelen JSON'u JavaScript nesnesine çevir
    if (!cevap.ok) throw new Error(veri.detail || "Bilinmeyen hata");
    apodGoster(veri);
  } catch (hata) {
    apodKutusu.innerHTML = hataHtml("Fotoğraf alınamadı.", hata.message);
  }
}

// Gelen veriyi HTML'e dönüştürüp sayfaya koyan fonksiyon
function apodGoster(veri) {
  const kaynak = metinTemizle(veri.kaynak);
  let medya;
  if (veri.tur === "image") {
    // Resme tıklayınca yüksek çözünürlüklü hali yeni sekmede açılsın
    medya = `
      <a href="${metinTemizle(veri.hd_url)}" target="_blank" rel="noopener">
        <img src="${metinTemizle(veri.url)}" alt="${metinTemizle(veri.baslik)}" loading="lazy">
      </a>`;
  } else {
    // Video vb. günlerde NASA sayfasına yönlendir
    medya = `<div class="not">${ikon("oynat")}<span>Bugünkü içerik bir video veya animasyon.
      <a href="${kaynak}" target="_blank" rel="noopener">NASA'da izle</a></span></div>`;
  }

  const telif = veri.telif ? `<span>· © ${metinTemizle(veri.telif)}</span>` : "";

  // Türkçe çeviri varsa üstte Türkçe, altta İngilizce orijinal. Yoksa sadece İngilizce.
  const turkceVar = Boolean(veri.aciklama_tr);
  const baslik = turkceVar ? veri.baslik_tr || veri.baslik : veri.baslik;

  const turkceBolum = turkceVar ? `<p class="apod-aciklama">${metinTemizle(veri.aciklama_tr)}</p>` : "";
  const ingilizceBolum = `
    <div class="${turkceVar ? "orijinal" : ""}">
      ${turkceVar ? `<h4 class="orijinal-baslik">Orijinal metin<span>${metinTemizle(veri.baslik)}</span></h4>` : ""}
      <p class="apod-aciklama">${metinTemizle(veri.aciklama ?? "")}</p>
    </div>`;

  apodKutusu.innerHTML = `
    <div class="medya">${medya}</div>
    <h3 class="apod-baslik">${metinTemizle(baslik)}</h3>
    <p class="apod-bilgi">${ikon("takvim")}<span>${tarihYaz(veri.tarih)}</span>${telif}</p>
    ${turkceBolum}
    ${ingilizceBolum}
    <a class="devam-linki" href="${kaynak}" target="_blank" rel="noopener">NASA'da görüntüle ${ikon("ok")}</a>
  `;
}

// "2024-04-08" -> "8 Nisan 2024"
function tarihYaz(isoTarih) {
  return new Date(isoTarih + "T12:00:00").toLocaleDateString("tr-TR", {
    day: "numeric", month: "long", year: "numeric",
  });
}

tarihKutusu.addEventListener("change", () => apodGetir(tarihKutusu.value));

// ---------------------------------------------------------------------
// 2) Günün bilgisi
// ---------------------------------------------------------------------
async function bilgiGetir() {
  const kutu = document.getElementById("bilgi");
  kutu.innerHTML = yukleniyorHtml("Günün bilgisi hazırlanıyor");
  try {
    const cevap = await fetch("/api/fact");
    const bilgi = await cevap.json();
    kutu.innerHTML = `
      <div class="bilgi-ust">
        <h2 class="bolum-basligi">${ikon("bilgi")}Günün Bilgisi</h2>
        <span class="etiket">${metinTemizle(bilgi.kategori)}</span>
      </div>
      <p class="bilgi-metni">${metinTemizle(bilgi.metin)}</p>`;
  } catch {
    kutu.remove();   // bilgi gelmezse kartı tamamen gizle
  }
}

// ---------------------------------------------------------------------
// 3) Güncel haberler
// ---------------------------------------------------------------------
async function haberleriGetir() {
  const liste = document.getElementById("haber-listesi");
  liste.innerHTML = yukleniyorHtml("Haberler yükleniyor");
  try {
    const cevap = await fetch("/api/news?adet=6");
    const haberler = await cevap.json();
    if (!cevap.ok) throw new Error(haberler.detail);

    // Her haber için bir kart oluştur, hepsini birleştir (map + join)
    liste.innerHTML = haberler.map((h) => `
      <a class="haber" href="${metinTemizle(h.url)}" target="_blank" rel="noopener">
        ${h.gorsel ? `<img src="${metinTemizle(h.gorsel)}" alt="" loading="lazy">` : ""}
        <div class="haber-govde">
          <p class="haber-meta">${metinTemizle(h.kaynak)} · ${neZamanOnce(h.tarih)}</p>
          <h3>${metinTemizle(h.baslik_tr || h.baslik)}</h3>
          <p class="haber-ozet">${metinTemizle(h.ozet_tr || h.ozet)}</p>
          ${h.baslik_tr ? `<p class="haber-orijinal">${metinTemizle(h.baslik)}</p>` : ""}
        </div>
      </a>`).join("");
  } catch (hata) {
    liste.innerHTML = hataHtml("Haberler alınamadı.", hata.message);
  }
}

// "2026-11-19T06:41:35Z" -> "3 saat önce"
function neZamanOnce(isoTarih) {
  const dakika = Math.round((Date.now() - new Date(isoTarih)) / 60000);
  if (dakika < 60) return `${Math.max(dakika, 1)} dakika önce`;
  if (dakika < 60 * 24) return `${Math.round(dakika / 60)} saat önce`;
  return `${Math.round(dakika / (60 * 24))} gün önce`;
}

// Sayfa açılınca her şeyi getir (üçü aynı anda başlar, birbirini beklemez)
bilgiGetir();
apodGetir();
haberleriGetir();
