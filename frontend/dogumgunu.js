// =====================================================================
// Doğum Günü Fotoğrafın
// Doğum tarihini alır, NASA'nın o gün yayınladığı fotoğrafı (APOD) gösterir.
// Oklarla başka yılların doğum günlerine geçilebilir.
// Backend'de yeni bir şey yok: ana sayfanın kullandığı /api/apod?tarih= yeterli.
// ikon(), metinTemizle(), yukleniyorHtml(), hataHtml(), apodHtml(), tarihYaz() -> ortak.js
// =====================================================================

const APOD_BASLANGIC = "1995-06-16";             // APOD'un ilk günü
const KAYIT_ANAHTARI = "uzay-gunlugu-dogum-tarihi";

const girdi = document.getElementById("dogum-tarihi");
const yilSecici = document.getElementById("yil-secici");
const yilBasligi = document.getElementById("yil-basligi");
const oncekiButon = document.getElementById("onceki-yil");
const sonrakiButon = document.getElementById("sonraki-yil");
const notKutusu = document.getElementById("dogum-not");
const icerik = document.getElementById("dogum-icerik");

// ---------------------------------------------------------------------
// Tarih yardımcıları
// "2003-05-12" gibi metinleri doğrudan karşılaştırabiliriz: biçim aynı olduğu
// sürece alfabetik sıra = tarih sırası. Saat dilimi derdi de olmaz.
// ---------------------------------------------------------------------
const ikiHane = (sayi) => String(sayi).padStart(2, "0");
const isoYaz = (yil, ay, gun) => `${yil}-${ikiHane(ay)}-${ikiHane(gun)}`;

// Bugün, kullanıcının kendi saatine göre (toISOString UTC verir, gece yarısı yanılırdı)
function bugunIso() {
  const simdi = new Date();
  return isoYaz(simdi.getFullYear(), simdi.getMonth() + 1, simdi.getDate());
}

const artikYil = (yil) => (yil % 4 === 0 && yil % 100 !== 0) || yil % 400 === 0;

// Belli bir yıldaki doğum günü. 29 Şubat doğumlular artık olmayan yıllarda 28 Şubat'ı kutlar.
function yilinDogumGunu(dogum, yil) {
  if (dogum.ay === 2 && dogum.gun === 29 && !artikYil(yil)) {
    return { tarih: isoYaz(yil, 2, 28), kaydirildi: true };
  }
  return { tarih: isoYaz(yil, dogum.ay, dogum.gun), kaydirildi: false };
}

// Fotoğrafı olan bütün doğum günleri: APOD başladıktan sonra ve bugüne kadar
function fotografliYillar(dogum) {
  const bugun = bugunIso();
  const yillar = [];
  for (let yil = dogum.yil; yil <= Number(bugun.slice(0, 4)); yil++) {
    const { tarih } = yilinDogumGunu(dogum, yil);
    if (tarih >= APOD_BASLANGIC && tarih <= bugun) yillar.push(yil);
  }
  return yillar;
}

// "12 yıl önce", "dün", "3 gün önce"
function neKadarOnce(isoTarih) {
  const gun = Math.round((new Date(bugunIso()) - new Date(isoTarih)) / 86400000);
  if (gun === 0) return "bugün";
  if (gun === 1) return "dün";
  if (gun < 365) return `${gun} gün önce`;
  return `${Math.floor(gun / 365.25)} yıl önce`;
}

// ---------------------------------------------------------------------
// Sayfanın durumu
// ---------------------------------------------------------------------
let dogum = null;         // { yil, ay, gun, iso }
let yillar = [];          // fotoğrafı olan doğum günü yılları
let sira = 0;             // yillar içinde şu an gösterilen
let istekNo = 0;          // hızlı tıklamada eski cevap yenisinin üstüne yazmasın diye

function dogumTarihiSecildi(iso) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso) || iso > bugunIso() || iso < girdi.min) {
    notKutusu.innerHTML = "";
    yilSecici.hidden = true;
    icerik.innerHTML = hataHtml("Geçerli bir doğum tarihi seç.");
    return;
  }
  const [yil, ay, gun] = iso.split("-").map(Number);
  dogum = { yil, ay, gun, iso };
  yillar = fotografliYillar(dogum);
  sira = 0;     // ilk fotoğraflı doğum günü: 1995 sonrası doğanlar için doğdukları gün
  kaydet(iso);
  goster();
}

async function goster() {
  const yil = yillar[sira];
  const { tarih, kaydirildi } = yilinDogumGunu(dogum, yil);
  const yas = yil - dogum.yil;

  // Yıl başlığı ve oklar
  yilSecici.hidden = false;
  yilBasligi.textContent = yas === 0 ? `${yil} · Doğduğun gün` : `${yil} · ${yas}. yaş günün`;
  oncekiButon.disabled = sira === 0;
  sonrakiButon.disabled = sira === yillar.length - 1;

  // Bilgi notları
  const notlar = [];
  if (tarih.slice(5) === bugunIso().slice(5) && yas > 0) {
    notlar.push(`${ikon("pasta")}<span><strong>Bugün doğum günün, iyi ki doğdun!</strong></span>`);
  }
  if (sira === 0 && dogum.iso < APOD_BASLANGIC) {
    notlar.push(`${ikon("bilgi")}<span>NASA bu fotoğrafları 16 Haziran 1995'te yayınlamaya başladı.
      Doğduğun günün fotoğrafı yok, bu yüzden APOD başladıktan sonraki ilk doğum gününden başlıyoruz.</span>`);
  }
  if (kaydirildi) {
    notlar.push(`${ikon("takvim")}<span>${yil} artık yıl değil, 29 Şubat yok. Bu yıl 28 Şubat'ın fotoğrafı gösteriliyor.</span>`);
  }
  notKutusu.innerHTML = notlar.map((n) => `<div class="not">${n}</div>`).join("");

  // Fotoğraf
  const buIstek = ++istekNo;
  icerik.innerHTML = yukleniyorHtml("NASA arşivi taranıyor", tarihYaz(tarih));
  try {
    const cevap = await fetch(`/api/apod?tarih=${tarih}`);
    const veri = await cevap.json();
    if (buIstek !== istekNo) return;   // bu arada başka bir yıla geçildi
    if (cevap.status === 404) {
      icerik.innerHTML = hataHtml("NASA arşivinde bu güne ait fotoğraf bulunamadı.", "Oklarla başka bir yıla bakabilirsin.");
      return;
    }
    if (!cevap.ok) throw new Error(veri.detail || "Bilinmeyen hata");
    icerik.innerHTML = `<p class="dogum-zaman">${ikon("pasta")}<span>${neKadarOnce(tarih)}</span></p>` + apodHtml(veri);
  } catch (hata) {
    if (buIstek !== istekNo) return;
    icerik.innerHTML = hataHtml("Fotoğraf alınamadı.", hata.message);
  }
}

// ---------------------------------------------------------------------
// Doğum tarihi tarayıcıda saklanır (gizli sekmede localStorage çalışmayabilir)
// ---------------------------------------------------------------------
function kaydet(iso) {
  try { localStorage.setItem(KAYIT_ANAHTARI, iso); } catch { /* önemli değil */ }
}
function kayitliTarih() {
  try { return localStorage.getItem(KAYIT_ANAHTARI); } catch { return null; }
}

// ---------------------------------------------------------------------
// Başlat
// ---------------------------------------------------------------------
girdi.max = bugunIso();
girdi.addEventListener("change", () => girdi.value && dogumTarihiSecildi(girdi.value));
oncekiButon.addEventListener("click", () => { if (sira > 0) { sira--; goster(); } });
sonrakiButon.addEventListener("click", () => { if (sira < yillar.length - 1) { sira++; goster(); } });

const kayitli = kayitliTarih();
if (kayitli) {
  girdi.value = kayitli;
  dogumTarihiSecildi(kayitli);
}
