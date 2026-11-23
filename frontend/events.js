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
  hatirlatmalar: [],      // sunucudaki kurulu hatırlatmalar
  epostaAyarli: false,
  alici: null,
  yetkili: false,         // yönetici mi? (site internetteyken anahtar gerekir)
  anahtarGerekli: false,
};

// ---------------------------------------------------------------------
// Yönetici anahtarı: tarayıcıda saklanır, her hatırlatma isteğine başlık (header) olarak eklenir
// ---------------------------------------------------------------------
function anahtarOku() {
  try { return localStorage.getItem("yonetici-anahtari") || ""; } catch { return ""; }
}
function anahtarYaz(anahtar) {
  try { localStorage.setItem("yonetici-anahtari", anahtar); } catch { /* önemli değil */ }
}

// fetch() ile aynı, ama yönetici anahtarını da gönderir
function yetkiliFetch(adres, ayarlar = {}) {
  return fetch(adres, {
    ...ayarlar,
    headers: { ...(ayarlar.headers || {}), "X-Yonetici-Anahtari": anahtarOku() },
  });
}

async function yoneticiGirisi() {
  const girilen = prompt("🔑 Yönetici anahtarını gir:");
  if (!girilen) return;
  anahtarYaz(girilen.trim());
  await hatirlatmalariGetir();
  if (!durum.yetkili) {
    anahtarYaz("");
    alert("Anahtar yanlış. 😕");
  }
  listeyiCiz();
  hatirlatmalarimPenceresiAc();
}

// Şu an seçili ay, "2026-12" biçiminde
function aktifAy() {
  return `${durum.yil}-${String(durum.ay).padStart(2, "0")}`;
}

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
  const ayMetni = aktifAy();   // 2026-12
  ayBasligi.textContent = new Date(durum.yil, durum.ay - 1, 1)
    .toLocaleDateString("tr-TR", { month: "long", year: "numeric" });     // "Aralık 2026"
  liste.innerHTML = `<p class="yukleniyor">Takvim hazırlanıyor... 🗓️<br>
    <small>İlk açılışta çeviriler yüzünden biraz sürebilir.</small></p>`;

  try {
    const cevap = await fetch(`/api/events?ay=${ayMetni}`);
    const veri = await cevap.json();
    if (!cevap.ok) throw new Error(veri.detail || "Bilinmeyen hata");

    // Cevap gelene kadar kullanıcı ◀ ▶ ile başka aya geçtiyse bu eski cevabı gösterme
    if (ayMetni !== aktifAy()) return;

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

// ---------------------------------------------------------------------
// Hatırlatmalar
// ---------------------------------------------------------------------
const SECENEKLER = [
  { deger: "1saat", metin: "1 saat önce", ms: 60 * 60 * 1000 },
  { deger: "1gun", metin: "1 gün önce", ms: 24 * 60 * 60 * 1000 },
  { deger: "1hafta", metin: "1 hafta önce", ms: 7 * 24 * 60 * 60 * 1000 },
];

async function hatirlatmalariGetir() {
  try {
    const cevap = await yetkiliFetch("/api/reminders");
    const veri = await cevap.json();
    durum.hatirlatmalar = veri.hatirlatmalar;
    durum.epostaAyarli = veri.eposta_ayarli;
    durum.alici = veri.alici;
    durum.yetkili = veri.yetkili;
    durum.anahtarGerekli = veri.anahtar_gerekli;
  } catch {
    durum.hatirlatmalar = [];
  }
  hatirlatmaSayaciniGuncelle();
}

function hatirlatmaSayaciniGuncelle() {
  const sayi = durum.hatirlatmalar.filter((h) => h.durum === "bekliyor").length;
  document.getElementById("hatirlatma-sayisi").textContent = sayi ? `(${sayi})` : "";
}

// Bir olay için "ne zaman hatırlatayım?" penceresi
function hatirlatmaPenceresiAc(olayId) {
  const olay = durum.olaylar.find((o) => o.id === olayId);
  if (!olay) return;
  const kalanMs = new Date(olay.tarih) - new Date();
  const kurulu = durum.hatirlatmalar.filter((h) => h.olay_id === olay.id && h.durum === "bekliyor");

  const secenekler = SECENEKLER.map((s) => {
    const varMi = kurulu.find((h) => h.ne_zaman === s.deger);
    if (varMi) {
      return `<div class="secenek-satiri">✅ ${s.metin}
        <button class="kucuk-buton" data-eylem="sil" data-hid="${varMi.id}">Kaldır</button></div>`;
    }
    // Seçilemeyecek durumlar: zamanı geçmiş ya da saati belli değil
    const uygunDegil = s.ms >= kalanMs || (s.deger === "1saat" && olay.kesinlik === "gun");
    return `<label class="secenek-satiri${uygunDegil ? " pasif" : ""}">
      <input type="radio" name="ne-zaman" value="${s.deger}" ${uygunDegil ? "disabled" : ""}> ${s.metin}
      ${uygunDegil ? `<small>(uygun değil)</small>` : ""}</label>`;
  }).join("");

  const uyari = durum.epostaAyarli ? "" :
    `<div class="not">⚠️ E-posta ayarları henüz yapılmamış. Hatırlatmayı kurabilirsin ama
     <code>.env</code> dosyasına Gmail bilgileri eklenene kadar e-posta gönderilmez.</div>`;

  detayIcerik.innerHTML = `
    <h3 class="gun-basligi">🔔 Hatırlatma kur</h3>
    <p><strong>${olay.ikon} ${metinTemizle(olay.baslik)}</strong><br>
       <small>${gunBasligi(gunAnahtari(olay.tarih))}${olay.kesinlik === "gun" ? "" : ", " + saatYaz(olay.tarih)}</small></p>
    ${uyari}
    <p>E-posta ne zaman gelsin?${durum.alici ? ` <small>(${metinTemizle(durum.alici)})</small>` : ""}</p>
    <div class="secenekler">${secenekler}</div>
    <p id="hatirlatma-mesaji" class="form-mesaji"></p>
    <button class="ana-buton" data-eylem="kur" data-id="${metinTemizle(olay.id)}">Hatırlatmayı kur</button>`;
  if (!detay.open) detay.showModal();
}

async function hatirlatmaKur(olayId) {
  const secili = detayIcerik.querySelector('input[name="ne-zaman"]:checked');
  const mesaj = document.getElementById("hatirlatma-mesaji");
  if (!secili) {
    mesaj.textContent = "Önce bir seçenek işaretle.";
    return;
  }
  // POST isteği: sunucuya veri gönderiyoruz (JSON olarak)
  const cevap = await yetkiliFetch("/api/reminders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ olay_id: olayId, ay: aktifAy(), ne_zaman: secili.value }),
  });
  const veri = await cevap.json();
  if (!cevap.ok) {
    mesaj.textContent = "😕 " + (typeof veri.detail === "string" ? veri.detail : "Kurulamadı");
    return;
  }
  await hatirlatmalariGetir();
  listeyiCiz();
  hatirlatmaPenceresiAc(olayId);   // pencereyi güncel haliyle yeniden çiz
  document.getElementById("hatirlatma-mesaji").textContent = `✅ Kuruldu! ${veri.ne_zaman_metni} e-posta gelecek.`;
}

async function hatirlatmaSil(hatirlatmaId) {
  await yetkiliFetch(`/api/reminders/${hatirlatmaId}`, { method: "DELETE" });
  await hatirlatmalariGetir();
  listeyiCiz();
}

// Tüm hatırlatmaların listesi
function hatirlatmalarimPenceresiAc() {
  if (!durum.yetkili) {
    detayIcerik.innerHTML = `
      <h3 class="gun-basligi">🔔 Hatırlatmalar</h3>
      <p>Hatırlatmalar sadece sitenin sahibine açık.</p>
      <button class="ana-buton" data-eylem="giris">🔑 Yönetici girişi</button>`;
    if (!detay.open) detay.showModal();
    return;
  }

  const bekleyen = durum.hatirlatmalar.filter((h) => h.durum === "bekliyor");
  const gecmis = durum.hatirlatmalar.filter((h) => h.durum !== "bekliyor").slice(0, 10);
  const durumMetni = { gonderildi: "📧 gönderildi", kacirildi: "⏭️ zamanında gönderilemedi" };

  const satir = (h) => `
    <div class="hatirlatma-satiri">
      <div>
        <strong>${metinTemizle(h.ikon || "🔔")} ${metinTemizle(h.baslik)}</strong><br>
        <small>${gunBasligi(gunAnahtari(h.olay_tarihi))} · ${h.durum === "bekliyor"
          ? h.ne_zaman_metni : durumMetni[h.durum] || h.durum}</small>
      </div>
      <button class="kucuk-buton" data-eylem="sil" data-hid="${h.id}" aria-label="Sil">🗑️</button>
    </div>`;

  const epostaDurumu = durum.epostaAyarli
    ? `<p class="form-mesaji">📧 E-postalar şu adrese gidiyor: <strong>${metinTemizle(durum.alici)}</strong></p>
       <button class="kucuk-buton" data-eylem="test">Test e-postası gönder</button>`
    : `<div class="not">⚠️ E-posta ayarları yapılmamış. <code>.env</code> dosyasına
       <code>GMAIL_ADRESI</code> ve <code>GMAIL_UYGULAMA_SIFRESI</code> eklenip sunucu yeniden başlatılmalı.</div>`;

  const cikis = durum.anahtarGerekli
    ? ` <button class="kucuk-buton" data-eylem="cikis">Çıkış yap</button>` : "";

  detayIcerik.innerHTML = `
    <h3 class="gun-basligi">🔔 Hatırlatmalarım${cikis}</h3>
    ${epostaDurumu}
    <p id="hatirlatma-mesaji" class="form-mesaji"></p>
    <h4>Bekleyen</h4>
    ${bekleyen.length ? bekleyen.map(satir).join("") : `<p class="form-mesaji">Henüz hatırlatma yok. Bir olaydaki 🔔 butonuna tıkla.</p>`}
    ${gecmis.length ? `<h4>Geçmiş</h4>${gecmis.map(satir).join("")}` : ""}`;
  if (!detay.open) detay.showModal();
}

async function testEpostasiGonder() {
  const mesaj = document.getElementById("hatirlatma-mesaji");
  mesaj.textContent = "Gönderiliyor...";
  const cevap = await yetkiliFetch("/api/reminders/test", { method: "POST" });
  const veri = await cevap.json();
  mesaj.textContent = cevap.ok ? `✅ ${veri.mesaj}. Gelen kutunu kontrol et!` : `😕 ${veri.detail}`;
}

// Tüm hatırlatma butonları için tek dinleyici (data-eylem="..." ile hangi iş olduğunu anlıyoruz)
document.addEventListener("click", async (e) => {
  const buton = e.target.closest("[data-eylem]");
  if (!buton) return;
  const eylem = buton.dataset.eylem;

  if (eylem === "hatirlat") hatirlatmaPenceresiAc(buton.dataset.id);
  if (eylem === "kur") await hatirlatmaKur(buton.dataset.id);
  if (eylem === "test") await testEpostasiGonder();
  if (eylem === "hatirlatmalarim") hatirlatmalarimPenceresiAc();
  if (eylem === "giris") await yoneticiGirisi();
  if (eylem === "cikis") {
    anahtarYaz("");
    await hatirlatmalariGetir();
    listeyiCiz();
    hatirlatmalarimPenceresiAc();
  }
  if (eylem === "sil") {
    await hatirlatmaSil(buton.dataset.hid);
    // Hangi pencere açıksa onu güncelle
    const kurButonu = detayIcerik.querySelector('[data-eylem="kur"]');
    if (kurButonu) hatirlatmaPenceresiAc(kurButonu.dataset.id);
    else hatirlatmalarimPenceresiAc();
  }
});

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
        ${hatirlatButonu(o)}
      </div>
    </article>`;
}

// Olay kartındaki 🔔 butonu: kurulu hatırlatma varsa onu gösterir
function hatirlatButonu(o) {
  if (!hatirlatilabilir(o)) return "";
  const kurulu = durum.hatirlatmalar.filter((h) => h.olay_id === o.id && h.durum === "bekliyor");
  const metin = kurulu.length
    ? `🔔 Kuruldu: ${kurulu.map((h) => h.ne_zaman_metni).join(", ")}`
    : "🔔 Hatırlat";
  return `<button class="hatirlat-butonu${kurulu.length ? " kurulu" : ""}"
            data-eylem="hatirlat" data-id="${metinTemizle(o.id)}">${metin}</button>`;
}

// Tarihi belli ve henüz gerçekleşmemiş olaylar için hatırlatma kurulabilir (sadece yönetici)
function hatirlatilabilir(o) {
  return durum.yetkili && o.kesinlik !== "ay" && new Date(o.tarih) > new Date();
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

// Sayfa açılınca: önce hatırlatmalar (butonlarda "Kuruldu" yazabilmek için), sonra olaylar
hatirlatmalariGetir().then(olaylariGetir);
