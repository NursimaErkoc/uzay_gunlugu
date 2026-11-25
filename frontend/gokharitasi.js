// =====================================================================
// Gök Haritası sayfası
// konumSeciciKur(), saatGun(), ikon(), yukleniyorHtml() ... -> ortak.js'den geliyor.
//
// Nasıl çalışıyor?
//   1) Yıldızların gökyüzündeki "adresi" (ra/dec) sabit: veri/gok.json'dan bir kez okunuyor.
//   2) Güneş, Ay ve gezegenler hareket ettiği için onların adresi sunucudan geliyor (/api/gok-haritasi).
//   3) Seçilen saat ve şehre göre her cismin YÜKSEKLİĞİNİ (ufuktan kaç derece yukarıda) ve
//      YÖNÜNÜ (kuzeyden kaç derece) hesaplayıp yuvarlak haritaya yerleştiriyoruz.
//      (Aynı formülün Python kopyası backend/tests/test_gok_haritasi.py'de astronomy-engine ile
//      karşılaştırılarak test ediliyor.)
// =====================================================================

const D = Math.PI / 180;     // derece -> radyan
const ADIM_DAKIKA = 10;      // saat çubuğunun bir adımı
const KENAR_PAYI = 26;       // daire ile tuvalin kenarı arasında yön harfleri için boşluk (piksel)

const GEZEGEN_RENGI = {
  "Merkür": "#b8b4c8", "Venüs": "#f5e3b0", "Mars": "#ff8a6b", "Jüpiter": "#e8c59a", "Satürn": "#f3c86f",
};
const YONLER = ["Kuzey", "Kuzeydoğu", "Doğu", "Güneydoğu", "Güney", "Güneybatı", "Batı", "Kuzeybatı"];

const tuval = document.getElementById("gok-tuvali");
const c = tuval.getContext("2d");
const durumKutusu = document.getElementById("gok-durum");
const cubuk = document.getElementById("saat-cubugu");
const saatYazisi = document.getElementById("saat-yazisi");
const notKutusu = document.getElementById("gok-notu");
const bilgiKutusu = document.getElementById("secili-bilgi");
const gezegenKutusu = document.getElementById("gorunen-gezegenler");
const secenek = {
  cizgiler: document.getElementById("cizgiler"),
  tkAdlari: document.getElementById("tk-adlari"),
  yildizAdlari: document.getElementById("yildiz-adlari"),
};

let veri = null;          // gok.json
let tkAdi = {};           // "Lyr" -> "Çalgı"
let konum = null;         // { ad, enlem, boylam }
let cisimler = [];        // sunucudan: Güneş, Ay, gezegenler
let baslangic = 0;        // saat çubuğunun 0 noktası (ms)
let secili = null;        // { tur, ad }  dokunulan cisim
let hedefler = [];        // dokunulabilir noktalar (her çizimde yeniden doldurulur)
let olcu = { W: 0, R: 0, cx: 0, cy: 0, oran: 1, k: 1 };

// =====================================================================
// 1) Astronomi hesapları
// =====================================================================
function julyenGunu(ms) {
  return ms / 86400000 + 2440587.5;   // gökbilimcilerin kullandığı kesintisiz gün sayacı
}

/** Yerel yıldız zamanı (derece): bu an tam tepemizden geçen gök "boylamı". Dünya döndükçe artar. */
function yerelYildizZamani(ms, boylam) {
  const deger = 280.46061837 + 360.98564736629 * (julyenGunu(ms) - 2451545) + boylam;
  return ((deger % 360) + 360) % 360;
}

/** ra/dec -> [yükseklik, yön] (derece). Yön: 0 Kuzey, 90 Doğu, 180 Güney, 270 Batı. */
function ufukKoordinati(ra, dec, yildizZamani, enlem) {
  const h = (yildizZamani - ra) * D, d = dec * D, f = enlem * D;
  const yukseklik = Math.asin(Math.sin(f) * Math.sin(d) + Math.cos(f) * Math.cos(d) * Math.cos(h));
  const yon = Math.atan2(-Math.sin(h) * Math.cos(d), Math.sin(d) * Math.cos(f) - Math.cos(d) * Math.cos(h) * Math.sin(f));
  return [yukseklik / D, ((yon / D) + 360) % 360];
}

/**
 * Gökyüzü kubbesini düz daireye yayıyoruz (stereografik izdüşüm: takımyıldızların şekli bozulmaz).
 * Tepe noktası (90°) ortada, ufuk (0°) dairenin kenarında. Kuzey yukarıda, Doğu SOLDA (yukarı bakınca öyle).
 */
function izdusum(yukseklik, yon) {
  const r = olcu.R * Math.tan(((90 - yukseklik) * D) / 2);
  return [olcu.cx - r * Math.sin(yon * D), olcu.cy - r * Math.cos(yon * D)];
}

function yonAdi(yon) { return YONLER[Math.round(yon / 45) % 8]; }
function anlikZaman() { return baslangic + Number(cubuk.value) * ADIM_DAKIKA * 60000; }

// =====================================================================
// 2) Çizim
// =====================================================================
function boyutla() {
  const oran = Math.min(window.devicePixelRatio || 1, 2);
  const W = tuval.parentElement.clientWidth;
  if (!W) return;
  tuval.width = tuval.height = Math.round(W * oran);
  olcu = { W, oran, R: (W / 2 - KENAR_PAYI) * oran, cx: (W / 2) * oran, cy: (W / 2) * oran,
           k: Math.min(Math.max(W / 640, 0.75), 1.15) * oran };
}

function yildizRengi(bv) {
  if (bv < 0) return "170, 200, 255";      // mavi-beyaz (sıcak yıldız)
  if (bv < 0.5) return "240, 244, 255";    // beyaz
  if (bv < 1.0) return "255, 240, 212";    // sarımsı
  return "255, 207, 160";                  // turuncu (soğuk yıldız)
}

function yazi(metin, x, y, { boyut = 11, renk = "rgba(200, 208, 240, 0.8)", hiza = "left", kalin = false } = {}) {
  c.font = `${kalin ? 600 : 400} ${boyut * olcu.oran}px "Exo 2", sans-serif`;
  c.fillStyle = renk;
  c.textAlign = hiza;
  c.textBaseline = "middle";
  c.fillText(metin, x, y);
}

function ciz() {
  if (!veri || !konum || !olcu.R) return;
  const ms = anlikZaman();
  const yz = yerelYildizZamani(ms, konum.boylam);
  const ufuk = (ra, dec) => ufukKoordinati(ra, dec, yz, konum.enlem);
  const { R, cx, cy, k, oran } = olcu;
  hedefler = [];

  // Gökyüzünün rengi Güneş'in yüksekliğine bağlı: -18° altı tam karanlık, +6° üstü gündüz
  const gunes = cisimler.find((x) => x.tur === "gunes");
  const gunesY = gunes ? ufuk(gunes.ra, gunes.dec)[0] : -90;
  const aydinlik = Math.min(Math.max((gunesY + 18) / 24, 0), 1);

  c.clearRect(0, 0, tuval.width, tuval.height);
  c.save();
  c.beginPath();
  c.arc(cx, cy, R, 0, 2 * Math.PI);
  const zemin = c.createRadialGradient(cx, cy, 0, cx, cy, R);
  zemin.addColorStop(0, `rgb(${5 + 30 * aydinlik}, ${9 + 60 * aydinlik}, ${24 + 100 * aydinlik})`);
  zemin.addColorStop(1, `rgb(${12 + 50 * aydinlik}, ${18 + 80 * aydinlik}, ${40 + 110 * aydinlik})`);
  c.fillStyle = zemin;
  c.fill();
  c.clip();   // bundan sonra çizilen her şey dairenin içinde kalır

  // Takımyıldız çizgileri
  const seciliTk = secili?.tur === "takimyildiz" ? secili.ad : null;
  if (secenek.cizgiler.checked) {
    for (const tk of veri.takimyildizlar) {
      const vurgulu = tk.k === seciliTk;
      c.strokeStyle = vurgulu ? "rgba(185, 162, 255, 0.9)" : `rgba(143, 169, 255, ${0.32 - 0.2 * aydinlik})`;
      c.lineWidth = (vurgulu ? 1.8 : 1) * oran;
      c.beginPath();
      for (const parca of tk.cizgiler) {
        let onceki = null;
        for (const [ra, dec] of parca) {
          const [y, yon] = ufuk(ra, dec);
          const nokta = y > -25 ? izdusum(y, yon) : null;   // ufkun çok altındaki parçaları atla
          if (nokta && onceki) { c.moveTo(...onceki); c.lineTo(...nokta); }
          onceki = nokta;
        }
      }
      c.stroke();
    }
  }

  // Yıldızlar (gündüz sönükler kaybolur)
  const sinirKadir = 5.5 - 7 * aydinlik;
  for (const [ra, dec, kadir, bv] of veri.yildizlar) {
    if (kadir > sinirKadir) continue;
    const [y, yon] = ufuk(ra, dec);
    if (y < 0) continue;
    const [x, yy] = izdusum(y, yon);
    const r = Math.max(0.55, (6 - kadir) * 0.48) * k;
    const parlaklik = Math.min(1, 0.35 + (5.5 - kadir) * 0.16);
    c.fillStyle = `rgba(${yildizRengi(bv)}, ${parlaklik})`;
    c.beginPath();
    c.arc(x, yy, r, 0, 2 * Math.PI);
    c.fill();
  }

  // Takımyıldız adları
  if (secenek.tkAdlari.checked) {
    // Ekran küçüldükçe sadece önemli takımyıldızların adı (1 = en bilinenler)
    const enFazlaOnem = olcu.W >= 560 ? 3 : olcu.W >= 420 ? 2 : 1;
    for (const tk of veri.takimyildizlar) {
      if (tk.onem > enFazlaOnem && tk.k !== seciliTk) continue;
      const [y, yon] = ufuk(tk.ra, tk.dec);
      if (y < 4) continue;
      const [x, yy] = izdusum(y, yon);
      yazi(tk.ad.toLocaleUpperCase("tr-TR"), x, yy, {
        boyut: olcu.W >= 420 ? 9.5 : 8.5, hiza: "center",
        renk: tk.k === seciliTk ? "rgba(214, 200, 255, 1)" : "rgba(185, 162, 255, 0.62)",
      });
      hedefler.push({ x, y: yy, r: 26 * oran, oncelik: 3, tur: "takimyildiz", ad: tk.k });
    }
  }

  // Adı olan parlak yıldızlar (veri en parlaktan sönüğe sıralı: çakışmada parlak olanın adı kalır)
  const yazilanlar = [];
  for (const ad of veri.adlar) {
    const [y, yon] = ufuk(ad.ra, ad.dec);
    if (y < 1) continue;
    const [x, yy] = izdusum(y, yon);
    const yazilsin = olcu.W >= 420 || ad.kadir < 1 || ad.ad === "Kutup Yıldızı";   // telefonda en parlaklar
    if (secenek.yildizAdlari.checked && yazilsin) yildizAdiYaz(ad.ad, x, yy, yazilanlar);
    hedefler.push({ x, y: yy, r: 16 * oran, oncelik: 2, tur: "yildiz", ad: ad.ad });
  }

  // Güneş, Ay, gezegenler (en üstte)
  for (const cisim of cisimler) {
    const [y, yon] = ufuk(cisim.ra, cisim.dec);
    if (y < -1) continue;
    const [x, yy] = izdusum(y, yon);
    if (cisim.tur === "gunes") {
      c.shadowColor = "#ffc861"; c.shadowBlur = 24 * k;
      c.fillStyle = "#ffd77a";
      c.beginPath(); c.arc(x, yy, 9 * k, 0, 2 * Math.PI); c.fill();
      c.shadowBlur = 0;
    } else if (cisim.tur === "ay") {
      ayiCiz(x, yy, 8 * k, cisim, gunes ? izdusum(Math.max(ufuk(gunes.ra, gunes.dec)[0], -80), ufuk(gunes.ra, gunes.dec)[1]) : null);
    } else {
      const renk = GEZEGEN_RENGI[cisim.ad] || "#fff";
      c.shadowColor = renk; c.shadowBlur = 10 * k;
      c.fillStyle = renk;
      c.beginPath(); c.arc(x, yy, (3.2 + Math.max(0, -cisim.kadir) * 0.55) * k, 0, 2 * Math.PI); c.fill();
      c.shadowBlur = 0;
    }
    yazi(cisim.ad, x + 11 * k, yy - 9 * k, { boyut: 11.5, kalin: true, renk: "rgba(255, 244, 214, 0.95)" });
    hedefler.push({ x, y: yy, r: 20 * oran, oncelik: 1, tur: cisim.tur, ad: cisim.ad });
  }

  // Seçili cismin etrafına halka
  const isaret = secili && secili.tur !== "takimyildiz" && hedefler.find((h) => h.tur === secili.tur && h.ad === secili.ad);
  if (isaret) {
    c.strokeStyle = "rgba(143, 169, 255, 0.95)";
    c.lineWidth = 1.5 * oran;
    c.beginPath(); c.arc(isaret.x, isaret.y, 13 * k, 0, 2 * Math.PI); c.stroke();
  }
  c.restore();

  // Ufuk çizgisi ve yön harfleri (Doğu solda!)
  c.strokeStyle = "rgba(140, 160, 255, 0.35)";
  c.lineWidth = 1.2 * oran;
  c.beginPath(); c.arc(cx, cy, R, 0, 2 * Math.PI); c.stroke();
  ["K", "KD", "D", "GD", "G", "GB", "B", "KB"].forEach((harf, i) => {
    const ana = i % 2 === 0;
    const aci = i * 45 * D;
    const uzaklik = R + 13 * oran;
    yazi(harf, cx - uzaklik * Math.sin(aci), cy - uzaklik * Math.cos(aci), {
      boyut: ana ? 12 : 9, kalin: ana, hiza: "center", renk: ana ? "rgba(230, 233, 251, 0.9)" : "rgba(136, 144, 184, 0.8)",
    });
  });

  bilgileriYaz(ms, gunesY, ufuk);
}

/**
 * Yıldız adını önce sağına yazmayı dener; başka bir adla çakışıyor ya da dairenin dışına taşıyorsa
 * soluna; iki taraf da doluysa hiç yazmaz (üst üste binmiş okunmaz yazılardan iyidir).
 */
function yildizAdiYaz(metin, x, y, yazilanlar) {
  const { k, oran, cx, cy, R } = olcu;
  c.font = `400 ${10 * oran}px "Exo 2", sans-serif`;
  const genislik = c.measureText(metin).width, yukseklik = 12 * oran, bosluk = 7 * k;
  for (const sag of [true, false]) {
    const kutu = { x: sag ? x + bosluk : x - bosluk - genislik, y: y - yukseklik / 2, g: genislik, y2: yukseklik };
    const disari = [kutu.x, kutu.x + kutu.g].some((kx) => Math.hypot(kx - cx, y - cy) > R - 2 * oran);
    const carpisma = yazilanlar.some((b) => kutu.x < b.x + b.g && b.x < kutu.x + kutu.g && kutu.y < b.y + b.y2 && b.y < kutu.y + kutu.y2);
    if (disari || carpisma) continue;
    yazilanlar.push(kutu);
    yazi(metin, kutu.x, y, { boyut: 10, renk: "rgba(225, 230, 250, 0.78)" });
    return;
  }
}

/**
 * Ay'ı evresine göre çiziyoruz: aydınlık taraf Güneş'e bakar.
 * Önce Güneş tarafındaki yarım daire aydınlatılır, sonra ortadaki elips ile hilal ya da şişkin ay yapılır.
 */
function ayiCiz(x, y, r, ay, gunesNoktasi) {
  const karanlik = "rgba(40, 46, 70, 0.95)", isik = "#f4f1e4";
  const aci = gunesNoktasi ? Math.atan2(gunesNoktasi[1] - y, gunesNoktasi[0] - x) : 0;
  const k2 = 2 * ay.aydinlik - 1;   // -1 yeni ay ... 0 yarım ... +1 dolunay
  c.save();
  c.translate(x, y);
  c.rotate(aci);
  c.shadowColor = "rgba(244, 241, 228, 0.6)"; c.shadowBlur = 14 * olcu.k * ay.aydinlik;
  c.fillStyle = karanlik;
  c.beginPath(); c.arc(0, 0, r, 0, 2 * Math.PI); c.fill();
  c.shadowBlur = 0;
  c.fillStyle = isik;
  c.beginPath(); c.arc(0, 0, r, -Math.PI / 2, Math.PI / 2); c.fill();   // Güneş tarafındaki yarı
  c.fillStyle = k2 > 0 ? isik : karanlik;
  c.beginPath(); c.ellipse(0, 0, Math.abs(k2) * r, r, 0, 0, 2 * Math.PI); c.fill();
  c.restore();
}

// =====================================================================
// 3) Yazılı bilgiler: saat, not, seçili cisim, görünen gezegenler
// =====================================================================
function konumCumlesi(y, yon) {
  if (y < 0) return "Şu an <strong>ufkun altında</strong>, görünmüyor.";
  let ek = "";
  if (y > 75) ek = " (neredeyse tam tepende)";
  else if (y < 10) ek = " (ufka çok yakın; önünde bina ya da ağaç olmamalı)";
  return `<strong>${yonAdi(yon)}</strong> yönünde, ufuktan <strong>${Math.round(y)}°</strong> yukarıda${ek}.`;
}

function parlaklikAdi(kadir) {
  if (kadir < -3) return "çok parlak";
  if (kadir < -1) return "parlak";
  if (kadir < 1) return "kolayca görülür";
  if (kadir < 3) return "şehirde de görülebilir";
  return "sönük, karanlık bir yer ister";
}

function bilgileriYaz(ms, gunesY, ufuk) {
  saatYazisi.textContent = saatGun(new Date(ms).toISOString());

  if (gunesY > -6) notKutusu.textContent = "Bu saatte hava aydınlık; yıldızlar görünmez. Çubuğu kaydırıp akşama geç.";
  else if (gunesY > -15) notKutusu.textContent = "Alacakaranlık: sadece en parlak yıldızlar ve gezegenler görünür.";
  else notKutusu.textContent = "Saatler cihazının saat dilimine göredir.";

  // Ufkun üstündeki gezegenler ve Ay
  const gorunenler = cisimler.filter((x) => x.tur !== "gunes")
    .map((x) => ({ ...x, uk: ufuk(x.ra, x.dec) }))
    .filter((x) => x.uk[0] > 0);
  gezegenKutusu.innerHTML = gorunenler.length
    ? gorunenler.map((x) => `<div><span>${x.ad}</span><strong>${yonAdi(x.uk[1])} · ${Math.round(x.uk[0])}°</strong></div>`).join("")
    : `<div class="gorunen-yok"><span>Gezegenler</span><strong>Bu saatte ufkun üstünde gezegen yok</strong></div>`;

  if (!secili) return;
  let html = "";
  if (secili.tur === "takimyildiz") {
    const tk = veri.takimyildizlar.find((t) => t.k === secili.ad);
    const [y, yon] = ufuk(tk.ra, tk.dec);
    html = `<strong class="secili-ad">${tk.ad}</strong> <span class="soluk">takımyıldızı</span><p>${konumCumlesi(y, yon)}</p>`;
  } else if (secili.tur === "yildiz") {
    const yildiz = veri.adlar.find((a) => a.ad === secili.ad);
    const [y, yon] = ufuk(yildiz.ra, yildiz.dec);
    const tk = tkAdi[yildiz.tk] ? ` · ${tkAdi[yildiz.tk]} takımyıldızında` : "";
    html = `<strong class="secili-ad">${yildiz.ad}</strong> <span class="soluk">yıldız${tk}</span>
      <p>${konumCumlesi(y, yon)} Parlaklık: ${String(yildiz.kadir).replace(".", ",")} kadir, ${parlaklikAdi(yildiz.kadir)}.</p>`;
  } else {
    const cisim = cisimler.find((x) => x.ad === secili.ad);
    if (!cisim) return;
    const [y, yon] = ufuk(cisim.ra, cisim.dec);
    const tur = { gunes: "yıldızımız", ay: "uydumuz" }[cisim.tur] || "gezegen";
    const ek = cisim.tur === "ay" ? ` ${cisim.evre}, %${Math.round(cisim.aydinlik * 100)} aydınlık.`
      : cisim.tur === "gunes" ? " Güneş'e asla doğrudan bakma!" : ` Parlaklık: ${parlaklikAdi(cisim.kadir)}.`;
    html = `<strong class="secili-ad">${cisim.ad}</strong> <span class="soluk">${tur}</span><p>${konumCumlesi(y, yon)}${ek}</p>`;
  }
  bilgiKutusu.innerHTML = html;
}

// =====================================================================
// 4) Veriyi getir
// =====================================================================
const cisimOnbellegi = new Map();
let bekleyenIstek = 0;

async function cisimleriGetir() {
  if (!konum) return;
  const ms = anlikZaman();
  const anahtar = `${konum.enlem},${konum.boylam},${Math.floor(ms / 600000)}`;
  if (cisimOnbellegi.has(anahtar)) { cisimler = cisimOnbellegi.get(anahtar); ciz(); return; }
  const numara = ++bekleyenIstek;
  try {
    const cevap = await fetch(`/api/gok-haritasi?enlem=${konum.enlem}&boylam=${konum.boylam}&zaman=${new Date(ms).toISOString()}`);
    if (!cevap.ok) throw new Error();
    const sonuc = (await cevap.json()).cisimler;
    cisimOnbellegi.set(anahtar, sonuc);
    if (numara !== bekleyenIstek) return;   // bu arada başka saat seçildiyse eskisini çizme
    cisimler = sonuc;
  } catch {
    notKutusu.textContent = "Gezegenlerin konumu alınamadı; sadece yıldızlar gösteriliyor.";
  }
  ciz();
}

let bekleme = null;
function birazSonraGetir() {   // çubuk kaydırılırken her adımda istek atmamak için kısa bekleme
  clearTimeout(bekleme);
  bekleme = setTimeout(cisimleriGetir, 150);
}

/** Şu an hava aydınlıksa haritayı bu akşam gökyüzünün karardığı saate götür. */
function karanligaGit() {
  const gunes = cisimler.find((x) => x.tur === "gunes");
  if (!gunes) return false;
  for (let adim = 0; adim <= Number(cubuk.max); adim++) {
    const ms = baslangic + adim * ADIM_DAKIKA * 60000;
    const [y] = ufukKoordinati(gunes.ra, gunes.dec, yerelYildizZamani(ms, konum.boylam), konum.enlem);
    if (y < -15) {
      if (adim === Number(cubuk.value)) return false;
      cubuk.value = adim;
      return true;
    }
  }
  return false;
}

async function ilkYukleme() {
  durumKutusu.innerHTML = yukleniyorHtml("Yıldızlar yükleniyor");
  const cevap = await fetch("veri/gok.json");
  if (!cevap.ok) throw new Error("Yıldız verisi okunamadı");
  veri = await cevap.json();
  tkAdi = Object.fromEntries(veri.takimyildizlar.map((t) => [t.k, t.ad]));
  durumKutusu.hidden = true;
}

// =====================================================================
// 5) Etkileşim
// =====================================================================
function simdiyeAyarla() {
  const simdi = Date.now();
  baslangic = simdi - (simdi % (ADIM_DAKIKA * 60000));   // 10 dakikaya yuvarla
  cubuk.value = 0;
}

tuval.addEventListener("click", (olay) => {
  const kutu = tuval.getBoundingClientRect();
  const x = (olay.clientX - kutu.left) * olcu.oran, y = (olay.clientY - kutu.top) * olcu.oran;
  let enIyi = null;
  for (const h of hedefler) {
    const uzaklik = Math.hypot(h.x - x, h.y - y);
    if (uzaklik > h.r) continue;
    const puan = h.oncelik * 1000 + uzaklik;   // gezegen > yıldız > takımyıldız adı
    if (!enIyi || puan < enIyi.puan) enIyi = { ...h, puan };
  }
  secili = enIyi ? { tur: enIyi.tur, ad: enIyi.ad } : null;
  if (!secili) bilgiKutusu.innerHTML = `<span class="soluk">Bir yıldıza, gezegene ya da takımyıldız adına dokun: nerede olduğunu söyleyeyim.</span>`;
  ciz();
});

cubuk.addEventListener("input", () => { ciz(); birazSonraGetir(); });
document.getElementById("simdi").addEventListener("click", () => { simdiyeAyarla(); ciz(); cisimleriGetir(); });
Object.values(secenek).forEach((kutu) => kutu.addEventListener("change", ciz));
new ResizeObserver(() => { boyutla(); ciz(); }).observe(tuval.parentElement);

simdiyeAyarla();
boyutla();

const veriHazir = ilkYukleme().catch((hata) => {
  durumKutusu.innerHTML = hataHtml("Gök haritası yüklenemedi.", hata.message);
});

let ilkKez = true;
konumSeciciKur({
  secimKutusu: document.getElementById("sehir"),
  konumButonu: document.getElementById("konumumu-kullan"),
  mesajKutusu: document.getElementById("konum-mesaji"),
  degisince: async (yeni) => {
    konum = yeni;
    await veriHazir;
    if (!veri) return;
    await cisimleriGetir();
    // Sayfa gündüz açıldıysa doğrudan bu akşamın gökyüzünü göster
    if (ilkKez) {
      ilkKez = false;
      if (karanligaGit()) { ciz(); cisimleriGetir(); }
    }
  },
});

