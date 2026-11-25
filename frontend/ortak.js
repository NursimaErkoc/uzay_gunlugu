// =====================================================================
// ortak.js: Her iki sayfanın (index.html ve events.html) birlikte kullandığı kod
//   1) SVG ikon seti
//   2) Hareketli yıldız arka planı (canvas)
//   3) Yardımcı fonksiyonlar
// Bu dosya, sayfaya özel JS dosyalarından ÖNCE yüklenir.
// =====================================================================

// ---------------------------------------------------------------------
// 1) İKONLAR
// Emoji yerine kendi çizgi ikonlarımızı kullanıyoruz: tek renkli, ince, her yerde aynı görünür.
// Her ikon 24x24'lük bir alana çizilmiş SVG yollarıdır (path). Renk CSS'teki "currentColor"dan,
// yani yazının renginden gelir.
// ---------------------------------------------------------------------
const IKONLAR = {
  // Olay türleri
  roket: '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
  uydu: '<path d="M13 7 9 3 5 7l4 4"/><path d="m17 11 4 4-4 4-4-4"/><path d="m8 12 4 4 6-6-4-4Z"/><path d="m16 8 3-3"/><path d="M9 21a6 6 0 0 0-6-6"/>',
  dolunay: '<circle cx="12" cy="12" r="8" fill="currentColor" fill-opacity=".25"/><circle cx="12" cy="12" r="8"/>',
  "yeni-ay": '<circle cx="12" cy="12" r="8" stroke-dasharray="2 2.6"/>',
  mevsim: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a14 14 0 0 1 0 18a14 14 0 0 1 0-18"/>',
  "ay-tutulmasi": '<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16a5 8 0 0 0 0-16z" fill="currentColor" fill-opacity=".5"/>',
  "gunes-tutulmasi": '<circle cx="12" cy="12" r="5.5" fill="currentColor" fill-opacity=".55"/><path d="M12 2v2.5M12 19.5V22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M2 12h2.5M19.5 12H22M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/>',
  gezegen: '<circle cx="12" cy="12" r="5"/><ellipse cx="12" cy="12" rx="10.5" ry="3.2" transform="rotate(-20 12 12)"/>',
  uzanim: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 17l.6 1.4L21 19l-1.4.6L19 21l-.6-1.4L17 19l1.4-.6z"/>',
  meteor: '<circle cx="17.5" cy="6.5" r="2.5"/><path d="M15.5 8.5 4 20M13 7l-6 6M17 11l-6 6"/>',
  // Arayüz
  fotograf: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
  bilgi: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6M10 22h4"/>',
  haber: '<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8M15 18h-5M10 6h8v4h-8z"/>',
  takvim: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  zil: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  liste: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  izgara: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  sol: '<path d="m15 18-6-6 6-6"/>',
  sag: '<path d="m9 18 6-6-6-6"/>',
  ok: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  oynat: '<circle cx="12" cy="12" r="9"/><path d="m10 8.5 5 3.5-5 3.5z"/>',
  kapat: '<path d="M18 6 6 18M6 6l12 12"/>',
  sil: '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  anahtar: '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6M15.5 7.5l3 3L22 7l-3-3"/>',
  eposta: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 5L2 7"/>',
  uyari: '<circle cx="12" cy="12" r="9"/><path d="M12 8v4.5M12 16h.01"/>',
  onay: '<path d="M20 6 9 17l-5-5"/>',
  hilal: '<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a6.8 6.8 0 0 0 10.5 10.5z"/>',
  gunes: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  iss: '<path d="M2 8.5h5v7H2zM17 8.5h5v7h-5zM7 12h10M4.5 8.5v7M19.5 8.5v7"/><rect x="10" y="9.5" width="4" height="5" rx="1"/>',
  astronot: '<circle cx="12" cy="8" r="5"/><path d="M9.5 7.5a3 3 0 0 1 5 0"/><path d="M5 21v-2a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v2"/>',
  asteroit: '<path d="M8 3.5l6.5-.5 5 4 2 6-3 6-7 2-6.5-3L3 11z"/><circle cx="10" cy="9.5" r="1.6"/><circle cx="15" cy="14.5" r="1.1"/><circle cx="9" cy="15" r=".8"/>',
  goz: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  konum: '<path d="M12 22s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/>',
};

/** ikon("roket") -> <svg ...>...</svg>   Bilinmeyen ad gelirse zil ikonu. */
function ikon(ad, sinif = "") {
  const icerik = IKONLAR[ad] || IKONLAR.zil;
  // width/height="18": CSS yüklenemese bile ikon dev boyuta çıkmasın (yedek boyut). Asıl boyutu CSS belirler.
  return `<svg class="ikon ${sinif}" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icerik}</svg>`;
}

// HTML'de <span data-ikon="takvim"></span> yazdığımız yerlere ikonu yerleştir
function sabitIkonlariYerlestir() {
  document.querySelectorAll("[data-ikon]").forEach((yer) => {
    yer.innerHTML = ikon(yer.dataset.ikon);
  });
}

// ---------------------------------------------------------------------
// 2) HAREKETLİ YILDIZ ARKA PLANI
// <canvas> = JavaScript ile üzerine çizim yapılabilen bir tuval.
// Saniyede ~60 kez (requestAnimationFrame) tuvali temizleyip yıldızları yeniden çiziyoruz:
//   - yıldızlar 3 katmanda farklı hızlarda yavaşça kayar (yakınlar hızlı, uzaklar yavaş: derinlik hissi)
//   - her yıldız kendi ritminde hafifçe parlayıp söner (twinkle)
//   - arada bir kayan yıldız geçer
// Hareket istemeyen kullanıcılar için (işletim sisteminde "animasyonları azalt" açıksa) sabit çizilir.
// ---------------------------------------------------------------------
function yildizlariBaslat() {
  const tuval = document.createElement("canvas");
  tuval.className = "yildiz-tuvali";
  tuval.setAttribute("aria-hidden", "true");
  // Konumu burada (satır içi stil olarak) veriyoruz, CSS'e bırakmıyoruz: style.css herhangi bir
  // sebeple yüklenmese bile tuval sayfada yer kaplayıp içeriği aşağı itmesin, hep arkada dursun.
  Object.assign(tuval.style, {
    position: "fixed", inset: "0", width: "100%", height: "100%", zIndex: "-1", pointerEvents: "none",
  });
  document.body.prepend(tuval);
  const c = tuval.getContext("2d");

  const hareketsiz = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const RENKLER = ["255,255,255", "220,228,255", "190,205,255", "255,236,214"];   // beyaz, mavimsi, sıcak
  let genislik, yukseklik, yildizlar = [], kayanlar = [], sonrakiKayan = 0, sonZaman = 0;

  function boyutla() {
    const oran = Math.min(window.devicePixelRatio || 1, 2);   // keskin ekranlarda net görünsün
    genislik = window.innerWidth;
    yukseklik = window.innerHeight;
    tuval.width = genislik * oran;
    tuval.height = yukseklik * oran;
    c.setTransform(oran, 0, 0, oran, 0, 0);

    const sayi = Math.min(1000, Math.round((genislik * yukseklik) / 1500));
    yildizlar = Array.from({ length: sayi }, () => {
      const katman = Math.random() < 0.68 ? 0 : Math.random() < 0.75 ? 1 : 2;   // çoğu uzak katmanda
      return {
        x: Math.random() * genislik,
        y: Math.random() * yukseklik,
        r: [0.6, 1.0, 1.55][katman] * (0.7 + Math.random() * 0.6),
        hiz: [3, 7, 14][katman],                 // piksel/saniye
        parlaklik: [0.45, 0.65, 0.9][katman] * (0.7 + Math.random() * 0.4),
        ritim: 0.4 + Math.random() * 1.6,        // parıldama hızı
        faz: Math.random() * Math.PI * 2,
        renk: RENKLER[Math.random() < 0.75 ? 0 : 1 + Math.floor(Math.random() * 3)],
      };
    });
  }

  function kayanYildizEkle() {
    const aci = (Math.PI / 180) * (20 + Math.random() * 25);   // sağ üstten sol alta doğru
    kayanlar.push({
      x: genislik * (0.3 + Math.random() * 0.8),
      y: -20 + Math.random() * yukseklik * 0.4,
      vx: -Math.cos(aci) * 900,
      vy: Math.sin(aci) * 900,
      omur: 0,
      sure: 0.7 + Math.random() * 0.5,
    });
  }

  function ciz(zaman) {
    const t = zaman / 1000;
    const dt = Math.min(t - sonZaman, 0.05);   // sekme arka plandayken büyük sıçrama olmasın
    sonZaman = t;
    c.clearRect(0, 0, genislik, yukseklik);

    for (const y of yildizlar) {
      if (!hareketsiz) {
        y.x -= y.hiz * dt;                      // sola doğru süzül
        y.y += y.hiz * 0.15 * dt;               // hafifçe aşağı
        if (y.x < -2) { y.x = genislik + 2; y.y = Math.random() * yukseklik; }
        if (y.y > yukseklik + 2) y.y = -2;
      }
      const parilti = hareketsiz ? 1 : 0.6 + 0.4 * Math.sin(t * y.ritim + y.faz);
      const isik = Math.min(1, y.parlaklik * parilti);
      c.fillStyle = `rgba(${y.renk},${isik.toFixed(3)})`;
      c.beginPath();
      c.arc(y.x, y.y, y.r, 0, Math.PI * 2);
      c.fill();
      // Büyük yıldızların etrafına hafif bir ışık halesi
      if (y.r > 1.3) {
        c.fillStyle = `rgba(${y.renk},${(isik * 0.12).toFixed(3)})`;
        c.beginPath();
        c.arc(y.x, y.y, y.r * 3.2, 0, Math.PI * 2);
        c.fill();
      }
    }

    if (!hareketsiz) {
      if (t > sonrakiKayan) {
        kayanYildizEkle();
        sonrakiKayan = t + 5 + Math.random() * 9;   // 5-14 saniyede bir
      }
      kayanlar = kayanlar.filter((k) => (k.omur += dt) < k.sure);
      for (const k of kayanlar) {
        k.x += k.vx * dt;
        k.y += k.vy * dt;
        const solma = 1 - k.omur / k.sure;
        const kuyrukX = k.x - k.vx * 0.12, kuyrukY = k.y - k.vy * 0.12;
        const iz = c.createLinearGradient(k.x, k.y, kuyrukX, kuyrukY);
        iz.addColorStop(0, `rgba(255,255,255,${0.9 * solma})`);
        iz.addColorStop(1, "rgba(160,180,255,0)");
        c.strokeStyle = iz;
        c.lineWidth = 1.4;
        c.beginPath();
        c.moveTo(k.x, k.y);
        c.lineTo(kuyrukX, kuyrukY);
        c.stroke();
      }
      requestAnimationFrame(ciz);
    }
  }

  boyutla();
  let zamanlayici;
  window.addEventListener("resize", () => {
    clearTimeout(zamanlayici);
    zamanlayici = setTimeout(() => { boyutla(); if (hareketsiz) ciz(0); }, 150);
  });
  sonrakiKayan = 2;   // ilk kayan yıldız 2. saniyede
  requestAnimationFrame(ciz);
}

// ---------------------------------------------------------------------
// 3) YARDIMCILAR
// ---------------------------------------------------------------------

// Güvenlik: dışarıdan gelen metindeki < > " gibi karakterleri zararsız hale getir (XSS koruması)
function metinTemizle(metin) {
  const div = document.createElement("div");
  div.textContent = metin ?? "";
  return div.innerHTML.replaceAll('"', "&quot;");
}

// Yükleniyor ve hata kutuları (her yerde aynı görünsün)
function yukleniyorHtml(metin, altMetin = "") {
  return `<div class="yukleniyor"><span class="yukleniyor-halka"></span>
    <span>${metin}</span>${altMetin ? `<small>${altMetin}</small>` : ""}</div>`;
}
function hataHtml(metin, ayrinti = "") {
  return `<div class="hata">${ikon("uyari")}<span>${metin}</span>
    ${ayrinti ? `<small>${metinTemizle(ayrinti)}</small>` : ""}</div>`;
}

// ---------------------------------------------------------------------
// 4) KONUM SEÇİCİ (Bu Gece ve ISS sayfaları birlikte kullanır)
// Şehir listesi + "Konumumu kullan" düğmesi. Seçim tarayıcıda (localStorage) saklanır;
// böylece bir sayfada seçilen şehir öbür sayfada da seçili gelir.
// ---------------------------------------------------------------------
const SEHIRLER = [
  { ad: "Adana", enlem: 37.0, boylam: 35.32 },
  { ad: "Ankara", enlem: 39.93, boylam: 32.86 },
  { ad: "Antalya", enlem: 36.89, boylam: 30.71 },
  { ad: "Bursa", enlem: 40.19, boylam: 29.06 },
  { ad: "Diyarbakır", enlem: 37.91, boylam: 40.23 },
  { ad: "Erzurum", enlem: 39.9, boylam: 41.27 },
  { ad: "Eskişehir", enlem: 39.78, boylam: 30.52 },
  { ad: "Gaziantep", enlem: 37.07, boylam: 37.38 },
  { ad: "İstanbul", enlem: 41.01, boylam: 28.98 },
  { ad: "İzmir", enlem: 38.42, boylam: 27.14 },
  { ad: "Kayseri", enlem: 38.73, boylam: 35.48 },
  { ad: "Konya", enlem: 37.87, boylam: 32.48 },
  { ad: "Samsun", enlem: 41.29, boylam: 36.33 },
  { ad: "Trabzon", enlem: 41.0, boylam: 39.72 },
  { ad: "Van", enlem: 38.49, boylam: 43.38 },
];
const KONUM_KAYIT_ANAHTARI = "uzay-gunlugu-konum";

// localStorage bazı durumlarda (gizli sekme vb.) çalışmayabilir; o yüzden try/catch içinde
function kayitliKonum() {
  try {
    const konum = JSON.parse(localStorage.getItem(KONUM_KAYIT_ANAHTARI));
    // Bozuk ya da eski biçimli bir kayıt varsa kullanma
    return konum && typeof konum.enlem === "number" && typeof konum.boylam === "number" ? konum : null;
  } catch {
    return null;
  }
}

function konumuKaydet(konum) {
  try {
    localStorage.setItem(KONUM_KAYIT_ANAHTARI, JSON.stringify(konum));
  } catch { /* kaydedemezsek sorun değil */ }
}

/**
 * Sayfadaki şehir kutusunu ve "Konumumu kullan" düğmesini çalıştırır.
 * Konum her değiştiğinde (ve sayfa ilk açıldığında) degisince(konum) çağrılır.
 */
function konumSeciciKur({ secimKutusu, konumButonu, mesajKutusu, degisince }) {
  const varsayilanMesaj = mesajKutusu.textContent;

  function listeyiDoldur(secili) {
    const secenekler = SEHIRLER.map((s) =>
      `<option value="${s.ad}" ${s.ad === secili ? "selected" : ""}>${s.ad}</option>`);
    if (secili === "Konumum") secenekler.unshift(`<option value="Konumum" selected>Konumum</option>`);
    secimKutusu.innerHTML = secenekler.join("");
  }

  secimKutusu.addEventListener("change", () => {
    const sehir = SEHIRLER.find((s) => s.ad === secimKutusu.value);
    if (!sehir) return;
    listeyiDoldur(sehir.ad);   // "Konumum" seçeneği listeden kalksın
    konumuKaydet(sehir);
    mesajKutusu.textContent = varsayilanMesaj;
    degisince(sehir);
  });

  konumButonu.addEventListener("click", () => {
    if (!navigator.geolocation) {
      mesajKutusu.textContent = "Tarayıcın konum özelliğini desteklemiyor.";
      return;
    }
    mesajKutusu.textContent = "Konum alınıyor…";
    navigator.geolocation.getCurrentPosition(
      (yer) => {
        const konum = {
          ad: "Konumum",
          // 2 ondalık (~1 km) yeterli; sunucu zaten 1 ondalığa yuvarlıyor
          enlem: Number(yer.coords.latitude.toFixed(2)),
          boylam: Number(yer.coords.longitude.toFixed(2)),
        };
        listeyiDoldur("Konumum");
        konumuKaydet(konum);
        mesajKutusu.textContent = `Konumun kullanılıyor (yaklaşık). ${varsayilanMesaj}`;
        degisince(konum);
      },
      () => { mesajKutusu.textContent = "Konum alınamadı. İzin vermediysen listeden şehir seçebilirsin."; },
      { timeout: 10000, maximumAge: 10 * 60 * 1000 },
    );
  });

  // Başlangıç: kayıtlı konum varsa o, yoksa Ankara
  const baslangic = kayitliKonum() || SEHIRLER.find((s) => s.ad === "Ankara");
  listeyiDoldur(baslangic.ad);
  degisince(baslangic);
}

// ---------------------------------------------------------------------
// 5) ZAMAN YAZDIRMA
// Sunucu zamanları UTC gönderiyor ("...Z"). new Date() bunu cihazın saat dilimine çevirir.
// ---------------------------------------------------------------------
function saat(iso) {
  return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

// Bugün değilse saatin yanına "yarın" ya da tarih ekle
function saatGun(iso) {
  if (!iso) return "—";
  const tarih = new Date(iso);
  const bugun = new Date();
  const yarin = new Date(); yarin.setDate(bugun.getDate() + 1);
  const dun = new Date(); dun.setDate(bugun.getDate() - 1);
  const ayniGun = (a, b) => a.toDateString() === b.toDateString();
  let gun = "";
  if (ayniGun(tarih, yarin)) gun = " (yarın)";
  else if (ayniGun(tarih, dun)) gun = " (dün)";
  else if (!ayniGun(tarih, bugun)) gun = ` (${tarih.toLocaleDateString("tr-TR", { day: "numeric", month: "long" })})`;
  return saat(iso) + gun;
}

sabitIkonlariYerlestir();
yildizlariBaslat();
