// =====================================================================
// Uzay Günlüğü - frontend JavaScript
// Görevi: Kendi API'mizden (/api/apod) veriyi çekip sayfaya yerleştirmek.
// =====================================================================

// Sayfadaki elemanları bul (DOM = sayfanın JavaScript'teki karşılığı)
const apodKutusu = document.getElementById("apod-icerik");
const tarihKutusu = document.getElementById("tarih");

// Tarih seçicide bugünden sonrası seçilemesin
tarihKutusu.max = new Date().toISOString().slice(0, 10);

// ---------------------------------------------------------------------
// 1) API'den veri çeken fonksiyon
//    async/await: "cevap gelene kadar bekle, ama sayfayı dondurma"
// ---------------------------------------------------------------------
async function apodGetir(tarih) {
  apodKutusu.innerHTML = `<p class="yukleniyor">Uzaydan veri geliyor... 🛰️</p>`;

  // Tarih seçildiyse adrese ekle: /api/apod?tarih=2024-04-08
  const adres = tarih ? `/api/apod?tarih=${tarih}` : "/api/apod";

  try {
    const cevap = await fetch(adres);          // isteği gönder
    const veri = await cevap.json();           // gelen JSON'u JavaScript nesnesine çevir

    if (!cevap.ok) {                           // 200 değilse hata göster
      throw new Error(veri.detail || "Bilinmeyen hata");
    }

    apodGoster(veri);
  } catch (hata) {
    apodKutusu.innerHTML = `
      <p class="hata">😕 Fotoğraf alınamadı.<br><small>${metinTemizle(hata.message)}</small></p>`;
  }
}

// ---------------------------------------------------------------------
// 2) Gelen veriyi HTML'e dönüştürüp sayfaya koyan fonksiyon
// ---------------------------------------------------------------------
function apodGoster(veri) {
  // Fotoğraf mı video mu?
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
    medya = `<div class="not">🎬 Bugünkü içerik bir video/animasyon.
      <a href="${kaynak}" target="_blank" rel="noopener">NASA'da izle →</a></div>`;
  }

  const telif = veri.telif ? ` · © ${metinTemizle(veri.telif)}` : "";

  // Türkçe çeviri varsa üstte Türkçe, altta İngilizce orijinal.
  // Çeviri yoksa (servis çalışmadıysa) sadece İngilizce.
  const turkceVar = Boolean(veri.aciklama_tr);
  const baslik = turkceVar ? veri.baslik_tr || veri.baslik : veri.baslik;

  const turkceBolum = turkceVar
    ? `<p class="apod-aciklama">${metinTemizle(veri.aciklama_tr)}</p>`
    : "";

  const ingilizceBolum = `
    <div class="${turkceVar ? "orijinal" : ""}">
      ${turkceVar ? `<h4 class="orijinal-baslik">🇬🇧 English · ${metinTemizle(veri.baslik)}</h4>` : ""}
      <p class="apod-aciklama">${metinTemizle(veri.aciklama ?? "")}</p>
    </div>`;

  apodKutusu.innerHTML = `
    <div class="medya">${medya}</div>
    <h3 class="apod-baslik">${metinTemizle(baslik)}</h3>
    <p class="apod-bilgi">📅 ${tarihYaz(veri.tarih)}${telif}</p>
    ${turkceBolum}
    ${ingilizceBolum}
    <p class="apod-bilgi"><a href="${kaynak}" target="_blank" rel="noopener">NASA'da görüntüle →</a></p>
  `;
}

// ---------------------------------------------------------------------
// Yardımcı fonksiyonlar
// ---------------------------------------------------------------------

// "2024-04-08" -> "8 Nisan 2024"
function tarihYaz(isoTarih) {
  return new Date(isoTarih + "T12:00:00").toLocaleDateString("tr-TR", {
    day: "numeric", month: "long", year: "numeric",
  });
}

// Güvenlik: dışarıdan gelen metindeki < > gibi karakterleri zararsız hale getir.
// (Yoksa biri metnin içine kod gizleyip sayfamızda çalıştırabilir: "XSS saldırısı")
function metinTemizle(metin) {
  const div = document.createElement("div");
  div.textContent = metin ?? "";
  return div.innerHTML.replaceAll('"', "&quot;");
}

// ---------------------------------------------------------------------
// 3) Olaylar: kullanıcı bir şey yapınca ne olsun?
// ---------------------------------------------------------------------
tarihKutusu.addEventListener("change", () => {
  apodGetir(tarihKutusu.value);
});

// ---------------------------------------------------------------------
// 4) Günün bilgisi
// ---------------------------------------------------------------------
async function bilgiGetir() {
  const kutu = document.getElementById("bilgi");
  try {
    const cevap = await fetch("/api/fact");
    const bilgi = await cevap.json();
    kutu.innerHTML = `
      <div class="bilgi-ust">
        <h2>💡 Günün Bilgisi</h2>
        <span class="etiket">${metinTemizle(bilgi.kategori)}</span>
      </div>
      <p class="bilgi-metni">${metinTemizle(bilgi.metin)}</p>`;
  } catch {
    kutu.remove();   // bilgi gelmezse kartı tamamen gizle
  }
}

// ---------------------------------------------------------------------
// 5) Güncel haberler
// ---------------------------------------------------------------------
async function haberleriGetir() {
  const liste = document.getElementById("haber-listesi");
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
          ${h.baslik_tr ? `<p class="haber-orijinal">🇬🇧 ${metinTemizle(h.baslik)}</p>` : ""}
        </div>
      </a>`).join("");
  } catch (hata) {
    liste.innerHTML = `<p class="hata">😕 Haberler alınamadı.<br><small>${metinTemizle(hata.message)}</small></p>`;
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
