// =====================================================================
// ISS Şu An Nerede sayfası
//   1) Leaflet haritası: ISS ikonu, yörünge izi, gece tarafının gölgesi
//   2) Birkaç saniyede bir /api/iss'ten yeni konumu alıp haritayı güncelleme
//   3) Şu an uzaydaki insanlar (/api/uzaydakiler)
// ikon(), metinTemizle(), yukleniyorHtml(), hataHtml() -> ortak.js'den geliyor.
// =====================================================================

const GUNCELLEME_SANIYE = 3;

// ---------------------------------------------------------------------
// 1) Harita
// L = Leaflet kütüphanesi (iss.html'de yüklendi)
// ---------------------------------------------------------------------
const harita = L.map("harita", {
  center: [20, 0],
  zoom: 2,
  minZoom: 1,
  worldCopyJump: true,   // haritayı yana kaydırınca dünya tekrar eder; ISS hep görünür kalsın
});

// Harita görüntüleri (karolar): Esri'nin anahtarsız kullanılabilen haritaları.
// Harita, küçük kare resimlerin (karo) yan yana dizilmesiyle oluşur. {z}/{y}/{x} = yakınlık ve karonun konumu.
const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services";
const koyuHarita = L.tileLayer(`${ESRI}/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`, {
  attribution: "Harita &copy; Esri", maxZoom: 8,
}).addTo(harita);
const uyduHaritasi = L.tileLayer(`${ESRI}/World_Imagery/MapServer/tile/{z}/{y}/{x}`, {
  attribution: "Uydu görüntüsü &copy; Esri, Maxar, Earthstar Geographics", maxZoom: 8,
});
// Sağ üstte harita türü seçici
L.control.layers({ "Koyu": koyuHarita, "Uydu": uyduHaritasi }, null, { position: "topright" }).addTo(harita);

// ISS işareti: kendi SVG ikonumuzla
const issIsareti = L.marker([0, 0], {
  icon: L.divIcon({ className: "iss-isareti", html: ikon("iss"), iconSize: [40, 40], iconAnchor: [20, 20] }),
  keyboard: false,
});
const gecmisIz = L.layerGroup().addTo(harita);
const gelecekIz = L.layerGroup().addTo(harita);
const geceKatmani = L.layerGroup().addTo(harita);
let ilkKonum = true;

const takipKutusu = document.getElementById("takip-et");
// Kullanıcı haritayı elle kaydırırsa takibi bırak (yoksa harita onu sürekli geri çeker)
harita.on("dragstart", () => { takipKutusu.checked = false; });
takipKutusu.addEventListener("change", () => { if (takipKutusu.checked) harita.panTo(issIsareti.getLatLng()); });

/**
 * Yörünge izini çizgilere böler. ISS haritanın sağ kenarından (boylam 180) çıkıp soldan (-180)
 * girdiğinde iki nokta arasına düz bir çizgi çekersek harita boyunca yatay bir çizgi oluşur.
 * Bunu önlemek için boylam bir anda 180°'den fazla değişirse çizgiyi orada koparıyoruz.
 */
function parcala(noktalar) {
  const parcalar = [[]];
  noktalar.forEach((n, i) => {
    if (i > 0 && Math.abs(n[1] - noktalar[i - 1][1]) > 180) parcalar.push([]);
    parcalar[parcalar.length - 1].push(n);
  });
  return parcalar;
}

function iziCiz(katman, noktalar, ayarlar) {
  katman.clearLayers();
  for (const parca of parcala(noktalar)) {
    if (parca.length > 1) L.polyline(parca, ayarlar).addTo(katman);
  }
}

/**
 * Dünya'nın gece tarafını gölgeli bir alan olarak çizer.
 * Güneş'in tam tepede olduğu nokta (enlemi = Güneş'in sapması, boylamı = saate göre) bulunur.
 * Gündüz ile gecenin sınırı (terminatör), bu noktadan 90° uzaktaki noktaların oluşturduğu çizgidir.
 * Yaklaşık formüller kullanıyoruz (±1° hassasiyet, harita için fazlasıyla yeterli).
 */
function geceyiCiz(tarih) {
  const gun = (tarih - Date.UTC(tarih.getUTCFullYear(), 0, 0)) / 86400000;   // yılın kaçıncı günü (ondalıklı)
  const sapma = -23.44 * Math.cos((2 * Math.PI / 365) * (gun + 10));         // Güneş'in sapması (derece)
  const saatUTC = tarih.getUTCHours() + tarih.getUTCMinutes() / 60 + tarih.getUTCSeconds() / 3600;
  const gunesBoylami = -15 * (saatUTC - 12);                                 // Güneş'in tepede olduğu boylam
  const rad = Math.PI / 180;

  const sinir = [];
  for (let boylam = -180; boylam <= 180; boylam += 2) {
    const enlem = Math.atan(-Math.cos((boylam - gunesBoylami) * rad) / Math.tan(sapma * rad)) / rad;
    sinir.push([enlem, boylam]);
  }
  // Sınır çizgisinden gece olan kutba kadar kapat (kuzey yazındaysa güney kutbu karanlıktadır)
  const geceKutbu = sapma > 0 ? -90 : 90;
  const alan = [...sinir, [geceKutbu, 180], [geceKutbu, -180]];
  geceKatmani.clearLayers();
  // Dünya tekrar ettiği için gölgeyi 3 kopya halinde çiziyoruz (sola ve sağa kaydırınca da görünsün)
  for (const kaydir of [-360, 0, 360]) {
    L.polygon(alan.map(([e, b]) => [e, b + kaydir]), {
      stroke: false, fillColor: "#000010", fillOpacity: 0.45, interactive: false,
    }).addTo(geceKatmani);
  }
}

// ---------------------------------------------------------------------
// 2) Konumu getir ve güncelle
// ---------------------------------------------------------------------
const bilgiKutusu = document.getElementById("iss-bilgi");
let zamanlayici = null;

function koordinat(deger, arti, eksi) {
  return `${Math.abs(deger).toFixed(2)}° ${deger >= 0 ? arti : eksi}`;
}

async function konumuGetir() {
  try {
    const cevap = await fetch("/api/iss");
    const veri = await cevap.json();
    if (!cevap.ok) throw new Error(veri.detail || "Bilinmeyen hata");
    konumuGoster(veri);
  } catch (hata) {
    bilgiKutusu.innerHTML = hataHtml("ISS'in konumu alınamadı.", hata.message);
  }
}

function konumuGoster(veri) {
  const konum = [veri.enlem, veri.boylam];
  issIsareti.setLatLng(konum);
  if (ilkKonum) {
    issIsareti.addTo(harita);
    harita.setView(konum, 3);
    ilkKonum = false;
  } else if (takipKutusu.checked) {
    harita.panTo(konum, { animate: true, duration: 1 });
  }

  // İz: iz[45] şu an. Öncesi geçmiş, sonrası gelecek.
  const simdi = -veri.iz_baslangic_dk;
  iziCiz(gecmisIz, veri.iz.slice(0, simdi + 1), { color: "#8fa9ff", weight: 2, opacity: 0.45, dashArray: "4 6" });
  iziCiz(gelecekIz, veri.iz.slice(simdi), { color: "#ffa274", weight: 2, opacity: 0.85 });
  geceyiCiz(new Date(veri.zaman));

  const isik = veri.gunes_isiginda
    ? `<span class="durum durum-gorunur">Güneş ışığında</span>`
    : `<span class="durum">Gölgede</span>`;
  bilgiKutusu.innerHTML = `
    <div><span>Enlem</span><strong>${koordinat(veri.enlem, "K", "G")}</strong></div>
    <div><span>Boylam</span><strong>${koordinat(veri.boylam, "D", "B")}</strong></div>
    <div><span>Yükseklik</span><strong>${veri.yukseklik_km.toLocaleString("tr-TR")} km</strong></div>
    <div><span>Hız</span><strong>${veri.hiz_kmsa.toLocaleString("tr-TR")} km/sa</strong></div>
    <div><span>Işık</span><strong>${isik}</strong></div>
    <div><span>Altındaki bölge</span><strong>${veri.altta_gunduz ? "Gündüz" : "Gece"}</strong></div>`;

  const saatOnce = Math.round((new Date(veri.zaman) - new Date(veri.tle_zamani)) / 3600000);
  document.getElementById("iss-not").textContent =
    `ISS saniyede yaklaşık ${(veri.hiz_kmsa / 3600).toFixed(1)} km yol alıyor ve Dünya'nın etrafını ` +
    `yaklaşık 92 dakikada bir dolanıyor: astronotlar günde 16 kez gün doğumu görüyor. ` +
    `Konum, ${saatOnce} saat önce ölçülen yörünge verisinden hesaplandı.`;
}

// Sekme arka plandayken güncellemeyi durdur (boşuna istek gönderme), geri gelince devam et
function baslat() {
  if (zamanlayici) return;
  konumuGetir();
  zamanlayici = setInterval(konumuGetir, GUNCELLEME_SANIYE * 1000);
}
function durdur() {
  clearInterval(zamanlayici);
  zamanlayici = null;
}
document.addEventListener("visibilitychange", () => (document.hidden ? durdur() : baslat()));

// ---------------------------------------------------------------------
// 3) Şu an uzayda kimler var
// ---------------------------------------------------------------------
async function uzaydakileriGetir() {
  const kutu = document.getElementById("uzaydakiler");
  kutu.innerHTML = yukleniyorHtml("Astronotlar yükleniyor");
  try {
    const cevap = await fetch("/api/uzaydakiler");
    const veri = await cevap.json();
    if (!cevap.ok) throw new Error(veri.detail || "Bilinmeyen hata");
    document.getElementById("uzaydaki-sayisi").textContent = `${veri.toplam} kişi`;
    kutu.innerHTML = veri.gruplar.map((grup) => `
      <h3 class="gun-basligi">${metinTemizle(grup.ad)} <span class="etiket">${grup.kisiler.length}</span></h3>
      <div class="astronot-izgara">${grup.kisiler.map(astronotKarti).join("")}</div>`).join("");
  } catch (hata) {
    kutu.innerHTML = hataHtml("Astronot listesi alınamadı.", hata.message);
  }
}

function astronotKarti(k) {
  const foto = k.fotograf
    ? `<img src="${metinTemizle(k.fotograf)}" alt="" loading="lazy">`
    : `<span class="astronot-yer-tutucu">${ikon("astronot")}</span>`;
  const alt = [k.ajans, k.ulke].filter(Boolean).map(metinTemizle).join(" · ");
  const gun = k.uzayda_gun === 0 ? "Uzaya yeni çıktı"
    : k.uzayda_gun != null ? `Toplam ${k.uzayda_gun} gün uzayda` : "";
  const ucus = k.ucus_sayisi ? ` · ${k.ucus_sayisi}. uçuşu` : "";
  const ad = k.wiki
    ? `<a href="${metinTemizle(k.wiki)}" target="_blank" rel="noopener">${metinTemizle(k.ad)}</a>`
    : metinTemizle(k.ad);
  return `
    <div class="astronot">
      ${foto}
      <div>
        <strong>${ad}</strong>
        ${k.gorev ? `<span class="astronot-gorev">${metinTemizle(k.gorev)}</span>` : ""}
        <p class="soluk">${alt}</p>
        <p class="soluk">${gun}${ucus}</p>
      </div>
    </div>`;
}

baslat();
uzaydakileriGetir();
