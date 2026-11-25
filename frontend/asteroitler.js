// =====================================================================
// Yaklaşan Asteroitler sayfası
//   1) Özet kutuları
//   2) Uzaklık çizelgesi (SVG): her gün bir satır, yatayda uzaklık (logaritmik), nokta boyu = asteroit boyu
//   3) Gün gün liste (çizelgenin tablo hali)
// ikon(), metinTemizle(), saat() ... -> ortak.js'den geliyor.
// =====================================================================

const sayi = (n, basamak = 0) => n.toLocaleString("tr-TR", { maximumFractionDigits: basamak });

async function asteroitleriGetir() {
  const kutular = ["ozet", "uzaklik-cizelgesi", "asteroit-listesi"].map((id) => document.getElementById(id));
  kutular.forEach((k) => (k.innerHTML = yukleniyorHtml("NASA'dan asteroitler geliyor")));
  try {
    const cevap = await fetch("/api/asteroitler");
    const veri = await cevap.json();
    if (!cevap.ok) throw new Error(veri.detail || "Bilinmeyen hata");
    const gun = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("tr-TR", { day: "numeric", month: "long" });
    document.getElementById("tarih-araligi").textContent = `${gun(veri.baslangic)} – ${gun(veri.bitis)}`;
    if (!veri.asteroitler.length) {
      kutular.forEach((k) => (k.innerHTML = `<p class="soluk">Bu hafta yakından geçecek bir asteroit yok.</p>`));
      return;
    }
    ozetGoster(veri);
    cizelgeCiz(veri.asteroitler);
    listeGoster(veri.asteroitler, veri.ozet);
  } catch (hata) {
    kutular.forEach((k) => (k.innerHTML = hataHtml("Asteroit bilgisi alınamadı.", hata.message)));
  }
}

// ---------------------------------------------------------------------
// 1) Özet
// ---------------------------------------------------------------------
function ozetGoster({ ozet, asteroitler }) {
  const bul = (id) => asteroitler.find((a) => a.id === id);
  const yakin = bul(ozet.en_yakin), buyuk = bul(ozet.en_buyuk), hizli = bul(ozet.en_hizli);
  document.getElementById("ozet").innerHTML = `
    <div><span>Bu hafta</span><strong>${ozet.toplam} asteroit</strong></div>
    <div><span>Ay'dan yakın geçen</span><strong>${ozet.aydan_yakin}</strong></div>
    <div><span>En yakın</span><strong>${sayi(yakin.ay_kati, 1)} × Ay</strong><small>${metinTemizle(yakin.ad)}</small></div>
    <div><span>En büyük</span><strong>~${sayi(buyuk.cap_max_m)} m</strong><small>${metinTemizle(buyuk.ad)}</small></div>
    <div><span>En hızlı</span><strong>${sayi(hizli.hiz_kms, 1)} km/sn</strong><small>${metinTemizle(hizli.ad)}</small></div>
    <div><span>Potansiyel tehlikeli</span><strong>${ozet.tehlikeli}</strong><small>Açıklaması aşağıda</small></div>`;
}

// ---------------------------------------------------------------------
// 2) Uzaklık çizelgesi
// Logaritmik ölçek: 1, 10, 100 eşit aralıklarla dizilir. Böylece hem Ay'dan yakın (0,5)
// hem çok uzak (150) asteroitler aynı çizelgeye sığar ve ayırt edilebilir.
// ---------------------------------------------------------------------
const ipucu = document.getElementById("ipucu");

function cizelgeCiz(asteroitler) {
  // Günlere göre satırlar (cihazın saat dilimine göre gün)
  const gunAnahtari = (iso) => new Date(iso).toDateString();
  const gunler = [...new Set(asteroitler.map((a) => gunAnahtari(a.zaman)))];

  const G = 820, SOL = 92, SAG = 24, UST = 30, SATIR = 38;
  const Y = UST + gunler.length * SATIR + 28;
  const enAz = Math.min(0.5, ...asteroitler.map((a) => a.ay_kati * 0.8));
  const enCok = Math.max(100, ...asteroitler.map((a) => a.ay_kati * 1.25));
  const log = Math.log10;
  const x = (ay) => SOL + ((log(ay) - log(enAz)) / (log(enCok) - log(enAz))) * (G - SOL - SAG);
  const enBuyukCap = Math.max(...asteroitler.map((a) => a.cap_max_m));
  // Alan boyutla orantılı olsun diye karekök: en küçük nokta 8 px çapında
  const r = (a) => 4 + 9 * Math.sqrt((a.cap_min_m + a.cap_max_m) / 2 / enBuyukCap);

  // Dikey çizgiler: 0,1 · 1 (Ay) · 10 · 100 ...
  let izgara = "";
  for (let us = Math.ceil(log(enAz)); us <= Math.floor(log(enCok)); us++) {
    const deger = 10 ** us, px = x(deger);
    const ay = deger === 1;
    izgara += `<line x1="${px}" x2="${px}" y1="${UST - 8}" y2="${Y - 22}" class="${ay ? "ay-cizgisi" : "izgara"}"/>
      <text x="${px}" y="${Y - 6}" class="eksen ${ay ? "ay-yazisi" : ""}">${ay ? "Ay" : sayi(deger, 1)}</text>`;
  }

  const satirlar = gunler.map((g, i) => {
    const y = UST + i * SATIR + SATIR / 2;
    const etiket = new Date(asteroitler.find((a) => gunAnahtari(a.zaman) === g).zaman)
      .toLocaleDateString("tr-TR", { weekday: "short", day: "numeric", month: "short" });
    return `<line x1="${SOL}" x2="${G - SAG}" y1="${y}" y2="${y}" class="satir-cizgisi"/>
      <text x="${SOL - 12}" y="${y + 4}" class="gun-etiketi">${etiket}</text>`;
  }).join("");

  // Büyükleri önce çiz ki küçükler üstte kalsın ve görünsün
  const sirali = [...asteroitler].sort((a, b) => b.cap_max_m - a.cap_max_m);
  const noktalar = sirali.map((a) => {
    const cx = x(a.ay_kati), cy = UST + gunler.indexOf(gunAnahtari(a.zaman)) * SATIR + SATIR / 2;
    return `<g class="asteroit-noktasi ${a.tehlikeli ? "tehlikeli" : ""}" data-id="${a.id}" tabindex="0">
      <circle cx="${cx}" cy="${cy}" r="${Math.max(r(a) + 4, 10)}" class="isabet"/>
      <circle cx="${cx}" cy="${cy}" r="${r(a)}" class="nokta"/>
    </g>`;
  }).join("");

  // Tek doğrudan etiket: en yakın geçen asteroit
  const enYakin = asteroitler.reduce((a, b) => (b.ay_kati < a.ay_kati ? b : a));
  const ey = UST + gunler.indexOf(gunAnahtari(enYakin.zaman)) * SATIR + SATIR / 2;
  const etiket = `<text x="${x(enYakin.ay_kati)}" y="${ey - r(enYakin) - 6}" class="dogrudan-etiket">En yakın: ${metinTemizle(enYakin.ad)}</text>`;

  // Solda Dünya: çizelgenin "0" noktası değil, sadece yön göstergesi
  const dunya = `<circle cx="${SOL - 70}" cy="${UST - 16}" r="5" class="dunya"/>
    <text x="${SOL - 60}" y="${UST - 12}" class="eksen sola">Dünya → uzaklık</text>`;

  const kutu = document.getElementById("uzaklik-cizelgesi");
  kutu.innerHTML = `<svg viewBox="0 0 ${G} ${Y}" role="img"
      aria-label="Asteroitlerin Dünya'ya en yakın geçiş uzaklıkları, günlere göre">
    ${dunya}${izgara}${satirlar}${noktalar}${etiket}</svg>`;

  // Üstüne gelince / dokununca / klavyeyle seçince bilgi kutusu
  const bilgi = Object.fromEntries(asteroitler.map((a) => [a.id, a]));
  kutu.querySelectorAll(".asteroit-noktasi").forEach((n) => {
    const goster = (olay) => ipucuGoster(bilgi[n.dataset.id], n.querySelector(".nokta"), olay);
    n.addEventListener("mouseenter", goster);
    n.addEventListener("focus", goster);
    n.addEventListener("click", goster);
    n.addEventListener("mouseleave", () => (ipucu.hidden = true));
    n.addEventListener("blur", () => (ipucu.hidden = true));
  });
}

function ipucuGoster(a, nokta) {
  ipucu.innerHTML = `
    <strong>${metinTemizle(a.ad)}</strong>${a.tehlikeli ? ` <span class="etiket tehlike-etiketi">Potansiyel tehlikeli</span>` : ""}
    <span>${saatGun(a.zaman)}</span>
    <span>${sayi(a.ay_kati, 1)} × Ay uzaklığı (${sayi(a.uzaklik_km)} km)</span>
    <span>${sayi(a.cap_min_m)}–${sayi(a.cap_max_m)} m · ${metinTemizle(a.boyut_metni)}</span>
    <span>${sayi(a.hiz_kms, 1)} km/sn</span>`;
  ipucu.hidden = false;
  const k = nokta.getBoundingClientRect(), i = ipucu.getBoundingClientRect();
  const sol = Math.min(Math.max(8, k.left + k.width / 2 - i.width / 2), window.innerWidth - i.width - 8);
  const ust = k.top - i.height - 10 < 8 ? k.bottom + 10 : k.top - i.height - 10;
  ipucu.style.left = `${sol + window.scrollX}px`;
  ipucu.style.top = `${ust + window.scrollY}px`;
}

// ---------------------------------------------------------------------
// 3) Liste: gün gün kartlar
// ---------------------------------------------------------------------
function listeGoster(asteroitler, ozet) {
  const simdi = Date.now();
  const gruplar = new Map();
  for (const a of asteroitler) {
    const gun = new Date(a.zaman).toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" });
    if (!gruplar.has(gun)) gruplar.set(gun, []);
    gruplar.get(gun).push(a);
  }
  const rozet = (a) => {
    if (a.id === ozet.en_yakin) return `<span class="etiket">En yakın</span>`;
    if (a.id === ozet.en_buyuk) return `<span class="etiket">En büyük</span>`;
    if (a.id === ozet.en_hizli) return `<span class="etiket">En hızlı</span>`;
    return "";
  };

  document.getElementById("asteroit-listesi").innerHTML = [...gruplar].map(([gun, liste]) => `
    <h3 class="gun-basligi">${gun} <span class="etiket">${liste.length}</span></h3>
    <div class="asteroit-izgara">${liste.map((a) => `
      <article class="asteroit ${a.tehlikeli ? "tehlikeli" : ""} ${new Date(a.zaman) < simdi ? "gecti" : ""}">
        <header>
          <strong>${a.jpl ? `<a href="${metinTemizle(a.jpl)}" target="_blank" rel="noopener">${metinTemizle(a.ad)}</a>` : metinTemizle(a.ad)}</strong>
          ${rozet(a)}
          ${a.tehlikeli ? `<span class="etiket tehlike-etiketi">${ikon("uyari")}Potansiyel tehlikeli</span>` : ""}
        </header>
        <p class="soluk">${new Date(a.zaman) < simdi ? "Geçti · " : ""}En yakın an: ${saat(a.zaman)}</p>
        <dl>
          <dt>Uzaklık</dt><dd>${sayi(a.uzaklik_km)} km<small>${metinTemizle(a.uzaklik_metni)}</small></dd>
          <dt>Boyut</dt><dd>${sayi(a.cap_min_m)}–${sayi(a.cap_max_m)} m<small>${metinTemizle(a.boyut_metni)}</small></dd>
          <dt>Hız</dt><dd>${sayi(a.hiz_kms, 1)} km/sn<small>${metinTemizle(a.hiz_metni)}</small></dd>
        </dl>
      </article>`).join("")}
    </div>`).join("");
}

asteroitleriGetir();
