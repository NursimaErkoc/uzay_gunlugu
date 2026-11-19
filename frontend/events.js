// =====================================================================
// Uzay Takvimi sayfası
// /api/events?ay=YYYY-AA adresinden ayın olaylarını çeker, güne göre gruplayıp gösterir.
// =====================================================================

const SAAT_DILIMI = "Europe/Istanbul";

// Sayfanın "durumu" (state): hangi ay, hangi filtre seçili, gelen olaylar
const durum = {
  yil: new Date().getFullYear(),
  ay: new Date().getMonth() + 1,   // JavaScript'te aylar 0'dan başlar, biz 1-12 kullanıyoruz
  filtre: "hepsi",
  starlink: false,
  // "liste" | "takvim". Öncelik: adresteki ?gorunum=takvim, sonra son seçim, yoksa liste
  gorunum: new URLSearchParams(location.search).get("gorunum") || tercihOku() || "liste",
  olaylar: [],
};

// Kullanıcının son görünüm seçimini tarayıcıda hatırla (localStorage).
// try/catch: gizli sekmede vb. localStorage kapalı olabilir, o zaman sessizce geç.
function tercihOku() {
  try { return localStorage.getItem("takvim-gorunumu"); } catch { return null; }
}
function tercihYaz(deger) {
  try { localStorage.setItem("takvim-gorunumu", deger); } catch { /* önemli değil */ }
}

const liste = document.getElementById("olay-listesi");
const ayBasligi = document.getElementById("ay-basligi");

// ---------------------------------------------------------------------
// Veriyi çek
// ---------------------------------------------------------------------
async function olaylariGetir() {
  const ayMetni = `${durum.yil}-${String(durum.ay).padStart(2, "0")}`;   // 2026-12
  ayBasligi.textContent = new Date(durum.yil, durum.ay - 1, 1)
    .toLocaleDateString("tr-TR", { month: "long", year: "numeric" });     // "Aralık 2026"
  liste.innerHTML = `<p class="yukleniyor">Takvim hazırlanıyor... 🗓️<br>
    <small>İlk açılışta çeviriler yüzünden biraz sürebilir.</small></p>`;

  try {
    const cevap = await fetch(`/api/events?ay=${ayMetni}`);
    const veri = await cevap.json();
    if (!cevap.ok) throw new Error(veri.detail || "Bilinmeyen hata");

    // Kullanıcı bu arada başka aya geçtiyse eski cevabı gösterme
    if (veri.ay !== ayMetni) return;

    durum.olaylar = veri.olaylar;
    durum.eksik = veri.eksik;
    listeyiCiz();
  } catch (hata) {
    liste.innerHTML = `<p class="hata">😕 Olaylar alınamadı.<br><small>${metinTemizle(hata.message)}</small></p>`;
  }
}

// ---------------------------------------------------------------------
// Çizim: filtrele, grupla, seçili görünüme göre çiz
// ---------------------------------------------------------------------
function listeyiCiz() {
  // 1) Filtrele
  const gorunenler = durum.olaylar.filter((o) => {
    if (durum.filtre !== "hepsi" && o.tur !== durum.filtre) return false;
    if (o.starlink && !durum.starlink) return false;
    return true;
  });

  // 2) Tarihi kesin olanları güne göre grupla, "ay içinde" olanları ayrı tut
  const gunler = {};        // { "2026-12-14": [olay, olay], ... }
  const belirsizler = [];
  for (const olay of gorunenler) {
    if (olay.kesinlik === "ay") {
      belirsizler.push(olay);
    } else {
      const gun = gunAnahtari(olay.tarih);
      (gunler[gun] ??= []).push(olay);
    }
  }

  // 3) HTML'i oluştur
  let html = "";
  if (durum.eksik?.length) {
    html += `<div class="not">ℹ️ Şu an ${durum.eksik.join(" ve ")} alınamadı, birkaç dakika sonra tekrar dene.</div>`;
  }

  html += durum.gorunum === "takvim"
    ? takvimHtml(gunler, belirsizler)
    : listeHtml(gunler, belirsizler, gorunenler.length);

  liste.innerHTML = html;
}

// --- Liste görünümü ---
function listeHtml(gunler, belirsizler, toplam) {
  let html = "";
  const bugun = gunAnahtari(new Date().toISOString());
  for (const [gun, olaylar] of Object.entries(gunler)) {
    const gecmis = gun < bugun ? " gecmis" : "";
    const bugunMu = gun === bugun ? ` <span class="etiket">Bugün</span>` : "";
    html += `
      <section class="gun-grubu${gecmis}">
        <h3 class="gun-basligi">${gunBasligi(gun)}${bugunMu}</h3>
        ${olaylar.map(olayKarti).join("")}
      </section>`;
  }

  if (belirsizler.length) {
    html += `
      <section class="gun-grubu">
        <h3 class="gun-basligi">📌 Bu ay içinde (kesin tarih henüz belli değil)</h3>
        ${belirsizler.map(olayKarti).join("")}
      </section>`;
  }

  if (!toplam) {
    html += `<p class="yukleniyor">Bu filtreye uyan olay yok. 🌌</p>`;
  }
  return html;
}

// --- Takvim (aylık tablo) görünümü ---
const GUN_ADLARI = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
const HUCREDE_EN_FAZLA = 3;   // bir gün kutusunda en fazla kaç olay başlığı görünsün

function takvimHtml(gunler, belirsizler) {
  const ilkGun = new Date(durum.yil, durum.ay - 1, 1);
  // getDay(): Pazar=0, Pazartesi=1 ... Takvimimiz Pazartesi'den başlıyor, o yüzden kaydırıyoruz
  const bosHucre = (ilkGun.getDay() + 6) % 7;
  const gunSayisi = new Date(durum.yil, durum.ay, 0).getDate();   // ayın son günü = gün sayısı
  const bugun = gunAnahtari(new Date().toISOString());

  let hucreler = GUN_ADLARI.map((g) => `<div class="takvim-baslik">${g}</div>`).join("");

  for (let i = 0; i < bosHucre; i++) hucreler += `<div class="hucre bos"></div>`;

  for (let gunNo = 1; gunNo <= gunSayisi; gunNo++) {
    const anahtar = `${durum.yil}-${String(durum.ay).padStart(2, "0")}-${String(gunNo).padStart(2, "0")}`;
    const olaylar = gunler[anahtar] || [];
    const siniflar = ["hucre",
      anahtar === bugun && "bugun",
      anahtar < bugun && "gecmis",
      olaylar.length && "dolu"].filter(Boolean).join(" ");

    const cipler = olaylar.slice(0, HUCREDE_EN_FAZLA).map((o) => `
      <button class="cip cip-${o.tur}" data-id="${metinTemizle(o.id)}" title="${metinTemizle(o.baslik)}">
        <span class="cip-ikon">${o.ikon}</span><span class="cip-metin">${metinTemizle(o.baslik)}</span>
      </button>`).join("");
    const kalan = olaylar.length - HUCREDE_EN_FAZLA;
    const daha = kalan > 0 ? `<button class="daha" data-gun="${anahtar}">+${kalan} daha</button>` : "";

    hucreler += `
      <div class="${siniflar}" data-gun="${anahtar}">
        <span class="gun-no">${gunNo}</span>
        <span class="olay-sayisi">${olaylar.length || ""}</span>
        ${cipler}${daha}
      </div>`;
  }

  let html = `<section class="kart takvim-karti"><div class="takvim">${hucreler}</div></section>`;

  if (belirsizler.length) {
    html += `
      <section class="gun-grubu">
        <h3 class="gun-basligi">📌 Bu ay içinde (kesin tarih henüz belli değil)</h3>
        ${belirsizler.map(olayKarti).join("")}
      </section>`;
  }
  return html;
}

// ---------------------------------------------------------------------
// Ayrıntı penceresi
// ---------------------------------------------------------------------
const detay = document.getElementById("detay");
const detayIcerik = document.getElementById("detay-icerik");

function olayDetayiAc(id) {
  const olay = durum.olaylar.find((o) => o.id === id);
  if (!olay) return;
  detayIcerik.innerHTML = `<h3 class="gun-basligi">${gunBasligi(gunAnahtari(olay.tarih))}</h3>${olayKarti(olay)}`;
  detay.showModal();
}

function gunDetayiAc(gun) {
  const olaylar = durum.olaylar.filter((o) =>
    o.kesinlik !== "ay" && gunAnahtari(o.tarih) === gun &&
    (durum.filtre === "hepsi" || o.tur === durum.filtre) &&
    (!o.starlink || durum.starlink));
  if (!olaylar.length) return;
  detayIcerik.innerHTML = `<h3 class="gun-basligi">${gunBasligi(gun)}</h3>${olaylar.map(olayKarti).join("")}`;
  detay.showModal();
}

document.getElementById("detay-kapat").addEventListener("click", () => detay.close());
// Pencerenin dışındaki karanlık alana tıklayınca da kapansın
detay.addEventListener("click", (e) => { if (e.target === detay) detay.close(); });

// Takvimdeki tıklamalar ("event delegation": tek dinleyici, tüm butonlar için)
liste.addEventListener("click", (e) => {
  const cip = e.target.closest(".cip");
  if (cip) return olayDetayiAc(cip.dataset.id);

  const daha = e.target.closest(".daha");
  if (daha) return gunDetayiAc(daha.dataset.gun);

  // Telefonda başlıklar gizli; güne dokununca o günün tüm olayları açılsın
  const hucre = e.target.closest(".hucre.dolu");
  if (hucre && window.matchMedia("(max-width: 640px)").matches) gunDetayiAc(hucre.dataset.gun);
});

// Tek bir olay kartı
function olayKarti(o) {
  const saat = {
    dakika: saatYaz(o.tarih),
    saat: "~" + saatYaz(o.tarih),
    gun: "Gün boyu",
    ay: "",
  }[o.kesinlik];

  const gorsel = o.gorsel
    ? `<img class="olay-gorsel" src="${metinTemizle(o.gorsel)}" alt="" loading="lazy">`
    : `<div class="olay-ikon">${o.ikon}</div>`;

  return `
    <article class="olay olay-${o.tur}">
      ${gorsel}
      <div class="olay-govde">
        <p class="olay-meta">
          ${saat ? `<span class="olay-saat">${saat}</span>` : ""}
          ${o.durum ? `<span class="etiket">${metinTemizle(o.durum)}</span>` : ""}
          ${o.turkiyeden_gorunur ? `<span class="etiket etiket-yesil">🇹🇷 Türkiye'den görünür</span>` : ""}
        </p>
        <h4>${o.ikon} ${metinTemizle(o.baslik)}</h4>
        ${o.alt_bilgi ? `<p class="olay-alt">${metinTemizle(o.alt_bilgi)}</p>` : ""}
        ${o.aciklama ? `<p class="olay-aciklama">${metinTemizle(o.aciklama)}</p>` : ""}
        ${o.link ? `<a href="${metinTemizle(o.link)}" target="_blank" rel="noopener">📺 Canlı yayın / video →</a>` : ""}
      </div>
    </article>`;
}

// ---------------------------------------------------------------------
// Tarih yardımcıları (hepsi Türkiye saatine göre)
// ---------------------------------------------------------------------

// "2026-12-24T01:28:45Z" -> "2026-12-24" (Türkiye saatine göre hangi gün?)
function gunAnahtari(isoTarih) {
  return new Date(isoTarih).toLocaleDateString("en-CA", { timeZone: SAAT_DILIMI });   // en-CA = YYYY-MM-DD biçimi
}

// "2026-12-24" -> "24 Aralık Perşembe"
function gunBasligi(gun) {
  return new Date(gun + "T12:00:00").toLocaleDateString("tr-TR", {
    day: "numeric", month: "long", weekday: "long",
  });
}

// "2026-12-24T01:28:45Z" -> "04:28"
function saatYaz(isoTarih) {
  return new Date(isoTarih).toLocaleTimeString("tr-TR", {
    hour: "2-digit", minute: "2-digit", timeZone: SAAT_DILIMI,
  });
}

function metinTemizle(metin) {
  const div = document.createElement("div");
  div.textContent = metin ?? "";
  return div.innerHTML.replaceAll('"', "&quot;");
}

// ---------------------------------------------------------------------
// Olaylar (kullanıcı etkileşimleri)
// ---------------------------------------------------------------------
document.getElementById("onceki-ay").addEventListener("click", () => {
  durum.ay -= 1;
  if (durum.ay < 1) { durum.ay = 12; durum.yil -= 1; }
  olaylariGetir();
});

document.getElementById("sonraki-ay").addEventListener("click", () => {
  durum.ay += 1;
  if (durum.ay > 12) { durum.ay = 1; durum.yil += 1; }
  olaylariGetir();
});

// Filtre butonları: tıklanınca aktif olanı değiştir, listeyi yeniden çiz
// (Veriyi tekrar çekmeye gerek yok, elimizdekini süzüyoruz.)
document.getElementById("filtreler").addEventListener("click", (e) => {
  const buton = e.target.closest(".filtre");
  if (!buton) return;
  document.querySelectorAll(".filtre").forEach((b) => b.classList.remove("aktif"));
  buton.classList.add("aktif");
  durum.filtre = buton.dataset.tur;
  listeyiCiz();
});

document.getElementById("starlink-goster").addEventListener("change", (e) => {
  durum.starlink = e.target.checked;
  listeyiCiz();
});

// Görünüm butonları: Liste / Takvim
const gorunumButonlari = document.querySelectorAll(".gorunum");
function gorunumButonlariniGuncelle() {
  gorunumButonlari.forEach((b) => b.classList.toggle("aktif", b.dataset.gorunum === durum.gorunum));
}
gorunumButonlari.forEach((buton) => {
  buton.addEventListener("click", () => {
    durum.gorunum = buton.dataset.gorunum;
    tercihYaz(durum.gorunum);
    gorunumButonlariniGuncelle();
    if (durum.olaylar.length) listeyiCiz();
  });
});
gorunumButonlariniGuncelle();

olaylariGetir();
