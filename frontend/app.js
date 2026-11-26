// =====================================================================
// Uzay Günlüğü - ana sayfa
// Görevi: Kendi API'mizden veriyi çekip sayfaya yerleştirmek.
// ikon(), metinTemizle(), yukleniyorHtml(), hataHtml(), apodHtml() -> ortak.js'den geliyor.
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
    apodKutusu.innerHTML = apodHtml(veri);   // apodHtml() ortak.js'de
  } catch (hata) {
    apodKutusu.innerHTML = hataHtml("Fotoğraf alınamadı.", hata.message);
  }
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
// 3) Bugün uzay tarihinde
//    Tarayıcı kendi tarihini gönderir: sunucunun saati farklı olabilir (Render UTC kullanıyor,
//    Türkiye'de gece 01:00'de sunucu için hâlâ dün).
// ---------------------------------------------------------------------
async function uzayTarihiGetir() {
  const kutu = document.getElementById("uzay-tarihi");
  const simdi = new Date();
  const bugun = `${simdi.getFullYear()}-${String(simdi.getMonth() + 1).padStart(2, "0")}-${String(simdi.getDate()).padStart(2, "0")}`;
  try {
    const cevap = await fetch(`/api/uzay-tarihi?tarih=${bugun}`);
    const veri = await cevap.json();
    if (!cevap.ok) throw new Error(veri.detail);

    // Bugün olay yoksa en yakın gün: "3 gün sonra, 5 Eylül'de" / "2 gün önce, 24 Ağustos'ta"
    const gunAdi = new Date(veri.tarih + "T12:00:00").toLocaleDateString("tr-TR", { day: "numeric", month: "long" });
    const baslik = veri.fark === 0 ? "Bugün Uzay Tarihinde" : "Yakında Uzay Tarihinde";
    const altBaslik = veri.fark === 0
      ? gunAdi
      : `${gunAdi} · ${Math.abs(veri.fark)} gün ${veri.fark < 0 ? "önce" : "sonra"}`;

    kutu.innerHTML = `
      <div class="kart-ust">
        <h2 class="bolum-basligi">${ikon("roket")}${baslik}</h2>
        <span class="etiket">${altBaslik}</span>
      </div>
      <ol class="tarih-listesi">
        ${veri.olaylar.map((o) => `
          <li>
            <div class="tarih-yil">${o.yil}<small>${o.yil_once} yıl önce</small></div>
            <div>
              <span class="tarih-kategori">${metinTemizle(o.kategori)}</span>
              <p>${metinTemizle(o.metin)}</p>
            </div>
          </li>`).join("")}
      </ol>`;
    kutu.hidden = false;
  } catch {
    kutu.hidden = true;   // gelmezse kart hiç görünmesin
  }
}

// ---------------------------------------------------------------------
// 4) Güncel haberler
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

// Sayfa açılınca her şeyi getir (hepsi aynı anda başlar, birbirini beklemez)
bilgiGetir();
apodGetir();
uzayTarihiGetir();
haberleriGetir();
