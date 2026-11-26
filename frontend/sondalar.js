// =====================================================================
// Uzay Sondaları Nerede
// Konumlar /api/sondalar'dan gelir (JPL Horizons, saat başına bir hesap).
// Uzaklık sayacı tarayıcıda her saniye ilerler: uzaklık = ölçülen uzaklık + hız × geçen süre
// ikon(), metinTemizle(), yukleniyorHtml(), hataHtml() -> ortak.js
// =====================================================================

const ISIK_HIZI = 299792.458;   // km/sn

// Gezegenlerin Güneş'e ortalama uzaklığı (AB). Çizelgede dikey çizgi olarak görünür.
const YORUNGELER = [
  { ad: "Merkür", ab: 0.387 }, { ad: "Venüs", ab: 0.723 }, { ad: "Dünya", ab: 1 },
  { ad: "Mars", ab: 1.524 }, { ad: "Jüpiter", ab: 5.20 }, { ad: "Satürn", ab: 9.58 },
  { ad: "Uranüs", ab: 19.2 }, { ad: "Neptün", ab: 30.1 }, { ad: "Plüton", ab: 39.5 },
];

let olcumZamani = 0;     // Horizons hesabının zamanı (ms)
let sayacZamanlayici = null;
let sondaHaritasi = {};   // kod -> araç; sayaç her saniye buradan okur

// ---------------------------------------------------------------------
// Biçimler
// ---------------------------------------------------------------------
function sayi(deger, ondalik = 0) {
  return deger.toLocaleString("tr-TR", { minimumFractionDigits: ondalik, maximumFractionDigits: ondalik });
}

// 26 milyar km gibi büyük sayılar için okunur kısa hali
function kisaKm(km) {
  if (km >= 1e9) return `${sayi(km / 1e9, 1)} milyar km`;
  if (km >= 1e6) return `${sayi(km / 1e6, 1)} milyon km`;
  return `${sayi(km)} km`;
}

// Işığın (ve radyo sinyalinin) yolculuk süresi: "23 sa 58 dk", "5 dk 12 sn"
function sureYaz(saniye) {
  const sa = Math.floor(saniye / 3600), dk = Math.floor((saniye % 3600) / 60), sn = Math.round(saniye % 60);
  if (sa > 0) return `${sa} sa ${dk} dk`;
  if (dk > 0) return `${dk} dk ${sn} sn`;
  return `${sn} sn`;
}

function hizYaz(kms) {
  const yon = kms >= 0 ? "uzaklaşıyor" : "yaklaşıyor";
  return `saniyede ${sayi(Math.abs(kms), 1)} km ${yon}`;
}

// ---------------------------------------------------------------------
// Veri
// ---------------------------------------------------------------------
async function sondalariGetir() {
  const kutular = ["sonda-ozet", "sonda-cizelgesi", "sonda-listesi"].map((id) => document.getElementById(id));
  kutular[2].innerHTML = yukleniyorHtml("Uzay araçlarının yeri hesaplanıyor", "NASA JPL Horizons");
  try {
    const cevap = await fetch("/api/sondalar");
    const veri = await cevap.json();
    if (!cevap.ok) throw new Error(veri.detail || "Bilinmeyen hata");
    olcumZamani = Date.parse(veri.zaman);
    ozetGoster(veri.sondalar);
    cizelgeCiz(veri.sondalar);
    listeGoster(veri.sondalar, veri.eksik);
    sayaciBaslat();
  } catch (hata) {
    kutular[0].innerHTML = "";
    kutular[1].innerHTML = "";
    kutular[2].innerHTML = hataHtml("Uzay araçlarının konumu alınamadı.", hata.message);
  }
}

// Şu anki uzaklık: ölçüm saat başında yapıldı, aradan geçen sürede araç ilerledi
function suankiKm(s) {
  return s.dunya_km + s.dunya_hiz_kms * ((Date.now() - olcumZamani) / 1000);
}

// ---------------------------------------------------------------------
// 1) Özet
// ---------------------------------------------------------------------
function ozetGoster(sondalar) {
  const enUzak = sondalar.reduce((a, b) => (b.dunya_km > a.dunya_km ? b : a));
  const enHizli = sondalar.reduce((a, b) => (Math.abs(b.gunes_hiz_kms) > Math.abs(a.gunes_hiz_kms) ? b : a));
  const yolda = sondalar.filter((s) => s.durum === "aktif").length;
  document.getElementById("sonda-ozet").innerHTML = `
    <div><span>En uzaktaki</span><strong>${metinTemizle(enUzak.ad)}</strong><small>${kisaKm(enUzak.dunya_km)}</small></div>
    <div><span>Ona bir mesaj</span><strong>${sureYaz(enUzak.isik_suresi_sn)}</strong><small>ışık hızıyla gider</small></div>
    <div><span>Şu an en hızlı</span><strong>${metinTemizle(enHizli.ad)}</strong><small>${sayi(Math.abs(enHizli.gunes_hiz_kms), 1)} km/sn</small></div>
    <div><span>Haberleşen</span><strong>${yolda} / ${sondalar.length}</strong><small>${sondalar.length - yolda} araç sessiz</small></div>`;
}

// ---------------------------------------------------------------------
// 2) Çizelge: Güneş'e uzaklık, logaritmik ölçek
// 0,1 · 1 · 10 · 100 AB eşit aralıklarla dizilir. Böylece Güneş'in dibindeki Parker ile
// 170 AB ötedeki Voyager 1 aynı çizelgeye sığar.
// ---------------------------------------------------------------------
function cizelgeCiz(sondalar) {
  const sirali = [...sondalar].sort((a, b) => b.gunes_ab - a.gunes_ab);
  const G = 820, SOL = 150, SAG = 24, UST = 44, SATIR = 30;
  const Y = UST + sirali.length * SATIR + 30;
  const enAz = 0.1, enCok = 250, log = Math.log10;
  const x = (ab) => SOL + ((log(Math.max(ab, enAz)) - log(enAz)) / (log(enCok) - log(enAz))) * (G - SOL - SAG);

  // Gezegen yörüngeleri: isimler üstte, iç gezegenler sıkışmasın diye iki sıra
  const yorungeler = YORUNGELER.map((g, i) => `
    <line x1="${x(g.ab)}" x2="${x(g.ab)}" y1="${UST - 6}" y2="${Y - 26}" class="${g.ad === "Dünya" ? "ay-cizgisi" : "izgara"}"/>
    <text x="${x(g.ab)}" y="${UST - (i % 2 ? 10 : 24)}" class="eksen ${g.ad === "Dünya" ? "ay-yazisi" : ""}">${g.ad}</text>`).join("");

  // Alttaki ölçek: AB
  const olcek = [0.1, 1, 10, 100].map((ab) => `
    <text x="${x(ab)}" y="${Y - 8}" class="eksen">${sayi(ab, ab < 1 ? 1 : 0)} AB</text>`).join("");

  const satirlar = sirali.map((s, i) => {
    const y = UST + i * SATIR + SATIR / 2;
    return `<line x1="${SOL}" x2="${G - SAG}" y1="${y}" y2="${y}" class="satir-cizgisi"/>
      <text x="${SOL - 12}" y="${y + 4}" class="gun-etiketi">${metinTemizle(s.ad)}</text>
      <line x1="${SOL}" x2="${x(s.gunes_ab)}" y1="${y}" y2="${y}" class="sonda-izi ${s.durum}"/>
      <circle cx="${x(s.gunes_ab)}" cy="${y}" r="5.5" class="sonda-noktasi ${s.durum}">
        <title>${metinTemizle(s.ad)}: Güneş'ten ${sayi(s.gunes_ab, 2)} AB</title></circle>`;
  }).join("");

  document.getElementById("sonda-cizelgesi").innerHTML = `<svg viewBox="0 0 ${G} ${Y}" role="img"
      aria-label="Uzay araçlarının Güneş'e uzaklığı ve gezegenlerin yörüngeleri, logaritmik ölçek">
    ${yorungeler}${satirlar}${olcek}</svg>`;
}

// ---------------------------------------------------------------------
// 3) Kartlar
// ---------------------------------------------------------------------
function listeGoster(sondalar, eksik) {
  const sirali = [...sondalar].sort((a, b) => b.dunya_km - a.dunya_km);
  const eksikNotu = eksik.length
    ? `<div class="not">${ikon("uyari")}<span>Şu an hesaplanamayanlar: ${eksik.map(metinTemizle).join(", ")}. Birkaç dakika sonra tekrar dene.</span></div>`
    : "";

  document.getElementById("sonda-listesi").innerHTML = eksikNotu + `<div class="sonda-izgara">${sirali.map((s) => `
    <article class="sonda ${s.durum}">
      <div class="sonda-ust">
        <h3>${metinTemizle(s.ad)}</h3>
        <span class="etiket">${s.durum === "aktif" ? "Haberleşiyor" : `Son sinyal ${s.son_sinyal}`}</span>
      </div>
      <p class="sonda-firlatma">${s.firlatma}'de fırlatıldı · ${new Date().getFullYear() - s.firlatma} yıldır yolda</p>
      <p class="sonda-km" data-kod="${metinTemizle(s.kod)}">${sayi(suankiKm(s))} km</p>
      <p class="soluk sonda-km-alt">Dünya'dan uzaklık · ${hizYaz(s.dunya_hiz_kms)}</p>
      <dl class="sonda-degerler">
        <div><dt>Mesaj süresi</dt><dd>${sureYaz(s.isik_suresi_sn)}</dd></div>
        <div><dt>Güneş'e uzaklık</dt><dd>${sayi(s.gunes_ab, s.gunes_ab < 10 ? 2 : 1)} AB</dd></div>
      </dl>
      <p class="cisim-bilgi">${metinTemizle(s.aciklama)}</p>
    </article>`).join("")}</div>`;

  sondaHaritasi = Object.fromEntries(sondalar.map((s) => [s.kod, s]));
}

// Her saniye km sayaçlarını yenile
function sayaciBaslat() {
  clearInterval(sayacZamanlayici);
  sayacZamanlayici = setInterval(() => {
    document.querySelectorAll(".sonda-km").forEach((el) => {
      const s = sondaHaritasi[el.dataset.kod];
      if (s) el.textContent = `${sayi(suankiKm(s))} km`;
    });
  }, 1000);
}

sondalariGetir();
// Hesap saat başı yenilenir; sayfa uzun süre açık kalırsa saatte bir tazele
setInterval(sondalariGetir, 60 * 60 * 1000);
