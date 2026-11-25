// =====================================================================
// Dünya'nın Fotoğrafı sayfası (NASA EPIC)
// Bir günün fotoğraflarını AKICI bir şekilde oynatarak Dünya'nın dönüşünü gösterir.
// ikon(), metinTemizle(), saat() ... -> ortak.js'den geliyor.
//
// Akıcılık nasıl sağlanıyor?
//   Fotoğraflar arasında ~1,5-2 saat var; Dünya bu sürede ~27° dönüyor. Fotoğrafları sırayla
//   değiştirirsek görüntü her seferinde "zıplar". Bunun yerine bir <canvas> (çizim tuvali) üzerinde
//   saniyede ~60 kez çizim yapıyoruz: bir fotoğraf yavaşça kaybolurken bir sonraki yavaşça
//   beliriyor (çapraz geçiş). Konum 0'dan fotoğraf sayısına kadar KESİRLİ bir sayı:
//   ör. 3,4 = "3. fotoğraf %60, 4. fotoğraf %40".
// =====================================================================

const GECIS_SURESI = 1600;   // bir fotoğraftan sonrakine geçiş kaç milisaniye sürsün (1x hızda)
const HIZLAR = [1, 2, 0.5];
const BUYUTME = 1.24;       // EPIC fotoğraflarında Dünya'nın etrafı siyah: hafif büyütüp daireyi dolduruyoruz

const tuval = document.getElementById("dunya-tuvali");
const c = tuval.getContext("2d");
const durumKutusu = document.getElementById("dunya-durum");
const cubuk = document.getElementById("zaman-cubugu");
const oynatDugmesi = document.getElementById("oynat");
const hizDugmesi = document.getElementById("hiz");
const bilgiKutusu = document.getElementById("kare-bilgisi");
const onizlemeKutusu = document.getElementById("onizlemeler");
const tarihKutusu = document.getElementById("tarih");

let kareler = [];        // API'den gelen bilgiler
let hazirResimler = [];  // ekran boyutuna küçültülmüş fotoğraflar (her karede yeniden küçültmemek için)
let konum = 0;           // kesirli: hangi iki fotoğrafın arasındayız
let oynuyor = false;
let hizSirasi = 0;
let sonZaman = 0;
let gosterilenKare = -1; // bilgi kutusunu her karede değil, sadece fotoğraf değişince yaz
let yuklemeNumarasi = 0; // tarih hızlıca değiştirilirse eski yüklemenin sonucu yenisini bozmasın

tarihKutusu.max = new Date().toISOString().slice(0, 10);
const hareketsiz = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---------------------------------------------------------------------
// Veriyi getir ve resimleri hazırla
// ---------------------------------------------------------------------
async function gunuGetir(tarih) {
  const numara = ++yuklemeNumarasi;
  durdur();
  kareler = [];
  hazirResimler = [];
  gosterilenKare = -1;
  onizlemeKutusu.innerHTML = "";
  bilgiKutusu.innerHTML = "";
  c.clearRect(0, 0, tuval.width, tuval.height);
  durumKutusu.innerHTML = yukleniyorHtml("Dünya'nın fotoğrafları geliyor");
  durumKutusu.hidden = false;

  try {
    const cevap = await fetch(tarih ? `/api/dunya?tarih=${tarih}` : "/api/dunya");
    const veri = await cevap.json();
    if (!cevap.ok) throw new Error(veri.detail || "Bilinmeyen hata");
    if (numara !== yuklemeNumarasi) return;
    if (!veri.kareler.length) {
      durumKutusu.innerHTML = `<div class="not">${ikon("bilgi")}<span>Bu tarihte fotoğraf yok. Uydu bazı günler bakımda olabiliyor; başka bir gün seç.</span></div>`;
      return;
    }
    kareler = veri.kareler;
    tarihKutusu.value = veri.tarih;
    cubuk.max = kareler.length - 1;
    onizlemeleriGoster();
    const resimler = await resimleriYukle(numara);
    if (numara !== yuklemeNumarasi) return;
    resimleriHazirla(resimler);
    durumKutusu.hidden = true;
    konum = 0;
    ciz();
    if (!hareketsiz) oynat();
  } catch (hata) {
    if (numara === yuklemeNumarasi) durumKutusu.innerHTML = hataHtml("Fotoğraflar alınamadı.", hata.message);
  }
}

// Bütün büyük fotoğrafları baştan indir (~250 KB'lık 10-20 resim)
function resimleriYukle(numara) {
  let biten = 0;
  const guncelle = () => {
    if (numara === yuklemeNumarasi) {
      durumKutusu.innerHTML = yukleniyorHtml("Fotoğraflar yükleniyor", `${biten} / ${kareler.length}`);
    }
  };
  guncelle();
  return Promise.all(kareler.map((k) => new Promise((tamam) => {
    const r = new Image();
    r.onload = () => { biten++; guncelle(); tamam(r); };
    r.onerror = () => { biten++; guncelle(); tamam(null); };   // inmeyen olursa atlanır
    r.src = k.resim;
  })));
}

/**
 * Fotoğrafları bir kez, ekrandaki boyuta küçültüp ayrı tuvallere çiziyoruz.
 * Oynatırken her karede 2048x2048'lik resmi küçültmek telefonu yorardı; hazır küçük kopyayı
 * çizmek çok daha hızlı.
 */
function resimleriHazirla(resimler) {
  const oran = Math.min(window.devicePixelRatio || 1, 2);
  const boyut = Math.round(Math.min(1024, tuval.parentElement.clientWidth * oran));
  tuval.width = tuval.height = boyut;
  const buyuk = boyut * BUYUTME, kenar = (buyuk - boyut) / 2;
  hazirResimler = resimler.map((r) => {
    if (!r) return null;
    const kopya = document.createElement("canvas");
    kopya.width = kopya.height = boyut;
    kopya.getContext("2d").drawImage(r, -kenar, -kenar, buyuk, buyuk);
    return kopya;
  });
}

// ---------------------------------------------------------------------
// Çizim ve oynatma
// ---------------------------------------------------------------------
function ciz() {
  const n = kareler.length;
  if (!n || !hazirResimler.length) return;
  const i = Math.floor(konum) % n;
  const sonraki = (i + 1) % n;
  const t = konum - Math.floor(konum);   // 0..1: sonraki fotoğrafa ne kadar geçildi

  c.globalAlpha = 1;
  if (hazirResimler[i]) c.drawImage(hazirResimler[i], 0, 0);
  if (t > 0 && hazirResimler[sonraki]) {
    c.globalAlpha = t;
    c.drawImage(hazirResimler[sonraki], 0, 0);
    c.globalAlpha = 1;
  }

  cubuk.value = konum;
  const enYakin = Math.round(konum) % n;
  if (enYakin !== gosterilenKare) bilgileriGoster(enYakin);
}

function dongu(zaman) {
  if (!oynuyor) return;
  const gecen = sonZaman ? Math.min(zaman - sonZaman, 100) : 0;   // sekme geri gelince büyük sıçrama olmasın
  sonZaman = zaman;
  konum = (konum + (gecen * HIZLAR[hizSirasi]) / GECIS_SURESI) % kareler.length;
  ciz();
  requestAnimationFrame(dongu);
}

function oynat() {
  if (oynuyor || kareler.length < 2) return;
  oynuyor = true;
  sonZaman = 0;
  requestAnimationFrame(dongu);
  oynatDugmesiniGuncelle();
}

function durdur() {
  oynuyor = false;
  oynatDugmesiniGuncelle();
}

function oynatDugmesiniGuncelle() {
  oynatDugmesi.innerHTML = ikon(oynuyor ? "durdur" : "oynat");
  oynatDugmesi.setAttribute("aria-label", oynuyor ? "Durdur" : "Oynat");
}

function kareyeGit(i) {
  durdur();
  konum = i;
  ciz();
}

oynatDugmesi.addEventListener("click", () => (oynuyor ? durdur() : oynat()));
hizDugmesi.addEventListener("click", () => {
  hizSirasi = (hizSirasi + 1) % HIZLAR.length;
  hizDugmesi.textContent = `${String(HIZLAR[hizSirasi]).replace(".", ",")}x`;
});
cubuk.addEventListener("input", () => { durdur(); konum = Number(cubuk.value); ciz(); });
tarihKutusu.addEventListener("change", () => tarihKutusu.value && gunuGetir(tarihKutusu.value));
document.addEventListener("visibilitychange", () => { if (document.hidden) durdur(); });

// ---------------------------------------------------------------------
// Bilgi kutuları ve küçük önizlemeler
// ---------------------------------------------------------------------
function bilgileriGoster(i) {
  gosterilenKare = i;
  const k = kareler[i];
  tuval.setAttribute("aria-label", `Dünya, ${saat(k.zaman)}: ${k.bolge} görünüyor`);
  bilgiKutusu.innerHTML = `
    <div><span>Saat</span><strong>${saat(k.zaman)}</strong><small>${new Date(k.zaman).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" })}</small></div>
    <div><span>Görünen bölge</span><strong>${metinTemizle(k.bolge)}</strong></div>
    <div><span>Türkiye</span><strong>${k.turkiye_gorunur ? `<span class="durum durum-gorunur">Görünüyor</span>` : `<span class="durum">Görünmüyor</span>`}</strong></div>
    <div><span>Uydunun uzaklığı</span><strong>${k.uzaklik_km.toLocaleString("tr-TR")} km</strong></div>`;
  onizlemeKutusu.querySelectorAll("button").forEach((d, j) => d.classList.toggle("secili", j === i));
}

function onizlemeleriGoster() {
  onizlemeKutusu.innerHTML = kareler.map((k, i) => `
    <button class="onizleme ${k.turkiye_gorunur ? "turkiye" : ""}" data-i="${i}"
            title="${saat(k.zaman)} · ${metinTemizle(k.bolge)}">
      <img src="${metinTemizle(k.onizleme)}" alt="" loading="lazy">
      <span>${saat(k.zaman)}</span>
      ${k.turkiye_gorunur ? `<em>TR</em>` : ""}
    </button>`).join("");
  onizlemeKutusu.querySelectorAll("button").forEach((d) =>
    d.addEventListener("click", () => kareyeGit(Number(d.dataset.i))));
}

oynatDugmesiniGuncelle();
gunuGetir();
