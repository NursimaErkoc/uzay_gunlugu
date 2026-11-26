// =====================================================================
// Gezegenlerde Yaşın
// İnternete bağlanmadan, tamamen tarayıcıda hesaplanır.
// ikon(), dogumTarihiOku(), dogumTarihiKaydet() -> ortak.js
//
// Bir gezegenin "yılı" = Güneş'in etrafında bir tam tur atma süresi.
// Hesap:  oradaki yaşın = yaşadığın gün sayısı / o gezegenin bir yılı (gün)
//   ör. 3.650 gün yaşadın, Mars yılı 687 gün -> Mars'ta 5,3 yaşındasın.
// =====================================================================

// yil: Güneş etrafında bir tur, Dünya günü olarak (NASA Gezegen Bilgi Tablosu)
const GEZEGENLER = [
  { ad: "Merkür", sinif: "merkur", yil: 87.969,
    bilgi: "En kısa yıl burada: her 3 ayda bir doğum günü kutlardın. Ama bir gün doğumundan ötekine 176 Dünya günü geçer, yani tam iki Merkür yılı." },
  { ad: "Venüs", sinif: "venus", yil: 224.701,
    bilgi: "Kendi etrafında 243 günde döner: Venüs'te bir gün, bir yıldan uzundur. Üstelik ters yöne döndüğü için Güneş batıdan doğar." },
  { ad: "Dünya", sinif: "dunya", yil: 365.256,
    bilgi: "Bir yıl 365 gün 6 saat. Artan 6 saatler her 4 yılda bir 29 Şubat olarak takvime eklenir." },
  { ad: "Mars", sinif: "mars", yil: 686.980,
    bilgi: "Bir Mars yılı neredeyse 2 Dünya yılı. Ama bir Mars günü 24 saat 39 dakika, Dünya'nınkine çok yakın." },
  { ad: "Jüpiter", sinif: "jupiter", yil: 4332.589,
    bilgi: "Bir yılı yaklaşık 12 Dünya yılı sürer. İlk Jüpiter doğum gününü ortaokulda kutlarsın." },
  { ad: "Satürn", sinif: "saturn", yil: 10759.22,
    bilgi: "Bir yılı 29,5 Dünya yılı. Galileo halkalarını 1610'da gördüğünden beri Güneş'in etrafında sadece 14 tur attı." },
  { ad: "Uranüs", sinif: "uranus", yil: 30685.4,
    bilgi: "Yan yatmış döner: her kutbu 42 yıl boyunca aralıksız Güneş görür, sonra 42 yıl karanlıkta kalır." },
  { ad: "Neptün", sinif: "neptun", yil: 60189,
    bilgi: "1846'da keşfedildi ve keşfinden sonraki ilk tam turunu ancak 2011'de tamamladı." },
  { ad: "Plüton", sinif: "pluton", yil: 90560,
    bilgi: "1930'da keşfedildi, o günden beri yörüngesinin yarısını bile tamamlamadı. İlk tam turu 2178'de bitecek." },
];

const GUN_MS = 86400000;
const girdi = document.getElementById("dogum-tarihi");
const ozet = document.getElementById("yas-ozet");
const kutu = document.getElementById("gezegenler");

// ---------------------------------------------------------------------
// Tarih yardımcıları. Tarihleri "1970'ten beri kaçıncı gün" sayısına çeviriyoruz:
// tam sayılarla çalışınca saat dilimi ve yaz saati hataları olmaz.
// ---------------------------------------------------------------------
const gunNo = (iso) => Math.round(Date.parse(iso + "T00:00:00Z") / GUN_MS);
const ikiHane = (n) => String(n).padStart(2, "0");

function bugunIso() {
  const s = new Date();
  return `${s.getFullYear()}-${ikiHane(s.getMonth() + 1)}-${ikiHane(s.getDate())}`;
}

// Gün numarasını yazıya çevir: "12 Ocak 2027"
function gunYaz(no, secenek = { day: "numeric", month: "long", year: "numeric" }) {
  return new Date(no * GUN_MS).toLocaleDateString("tr-TR", { ...secenek, timeZone: "UTC" });
}

function sayi(deger, ondalik = 0) {
  return deger.toLocaleString("tr-TR", { minimumFractionDigits: ondalik, maximumFractionDigits: ondalik });
}

// "bugün", "yarın", "47 gün sonra", "18 ay sonra", "3 yıl sonra"
function neZamanSonra(gun) {
  if (gun === 0) return "bugün";
  if (gun === 1) return "yarın";
  if (gun < 365) return `${sayi(gun)} gün sonra`;
  if (gun < 730) return `${Math.round(gun / 30.44)} ay sonra`;
  return `${sayi(Math.round(gun / 365.25))} yıl sonra`;
}

// Dünya'da takvimdeki doğum günü kullanılır (365,256 ile hesaplasak artık yıllar yüzünden
// bir gün kayabilirdi). 29 Şubat doğumlular artık olmayan yıllarda 28 Şubat'ı kutlar.
function dunyaDogumGunu(dogumIso, bugun) {
  const [y, a, g] = dogumIso.split("-").map(Number);
  const yilinGunu = (yil) => {
    const artik = (yil % 4 === 0 && yil % 100 !== 0) || yil % 400 === 0;
    const gun = a === 2 && g === 29 && !artik ? 28 : g;
    return gunNo(`${yil}-${ikiHane(a)}-${ikiHane(gun)}`);
  };
  let yil = Number(bugun.slice(0, 4));
  // Bu yılki geçtiyse seneye. Bugün doğduysa da seneye (doğduğun gün "0. doğum günü" değil)
  if (yilinGunu(yil) < gunNo(bugun) || yil === y) yil++;
  const sonraki = yilinGunu(yil);
  const onceki = yilinGunu(yil - 1);
  const yas = yil - 1 - y + (gunNo(bugun) - onceki) / (sonraki - onceki);
  return { yas: sonraki === gunNo(bugun) ? yil - y : yas, sonrakiNo: sonraki, kacinci: yil - y };
}

// ---------------------------------------------------------------------
// Hesap: her gezegen için yaş, yılın ne kadarı bitti, sıradaki doğum günü
// ---------------------------------------------------------------------
function hesapla(dogumIso) {
  const bugun = bugunIso();
  const dogumNo = gunNo(dogumIso);
  const yasanan = gunNo(bugun) - dogumNo;     // bugüne kadar yaşanan gün

  return GEZEGENLER.map((g) => {
    let yas, sonrakiNo, kacinci;
    if (g.ad === "Dünya") {
      ({ yas, sonrakiNo, kacinci } = dunyaDogumGunu(dogumIso, bugun));
    } else {
      yas = yasanan / g.yil;
      kacinci = Math.floor(yas) + 1;                          // sıradaki doğum günü kaçıncı
      sonrakiNo = dogumNo + Math.round(kacinci * g.yil);
      if (sonrakiNo === gunNo(bugun)) yas = kacinci;          // bugün doğum günü
    }
    const kalan = sonrakiNo - gunNo(bugun);
    return { ...g, yas, kacinci, sonrakiNo, kalan,
             ilerleme: kalan === 0 ? 1 : yas - Math.floor(yas) };
  });
}

// ---------------------------------------------------------------------
// Çizim
// ---------------------------------------------------------------------
function yasYaz(yas) {
  if (yas >= 100) return sayi(yas, 0);
  if (yas >= 10) return sayi(yas, 1);
  return sayi(yas, 2);
}

// Kartın sağ üstü: "yılı 88 gün", "yılı 1,9 yıl" (Dünya günü/yılı cinsinden)
function yilUzunlugu(g) {
  if (g.yil < 400) return `yılı ${sayi(g.yil, 0)} gün`;
  return `yılı ${sayi(g.yil / 365.256, 1)} yıl`;
}

function sonrakiYaz(g) {
  if (g.kalan === 0) return `<strong class="yas-bugun">Bugün ${g.kacinci}. ${g.ad} doğum günün!</strong>`;
  // Çok uzaktaysa tarih yerine yıl yeter; o gün Dünya'da kaç yaşında olacağını da söyle
  if (g.kalan > 365 * 3) {
    const dunyaYasi = Math.floor((g.sonrakiNo - gunNo(girdi.value)) / 365.25);
    return `${g.kacinci}. doğum günün <strong>${gunYaz(g.sonrakiNo, { year: "numeric" })}</strong> yılında
      <span class="soluk">(o gün Dünya'da ${dunyaYasi} yaşında olacaksın)</span>`;
  }
  return `${g.kacinci}. doğum günün <strong>${gunYaz(g.sonrakiNo)}</strong>
    <span class="soluk">· ${neZamanSonra(g.kalan)}</span>`;
}

function ciz(dogumIso) {
  const sonuclar = hesapla(dogumIso);
  const yasanan = gunNo(bugunIso()) - gunNo(dogumIso);

  // Özet: kaç gün yaşadın + en yakın gezegen doğum günü (Dünya hariç)
  const enYakin = sonuclar.filter((g) => g.ad !== "Dünya").sort((a, b) => a.kalan - b.kalan)[0];
  ozet.hidden = false;
  ozet.innerHTML = `
    <div><span class="yas-ozet-sayi">${sayi(yasanan)}</span><span class="soluk">gündür Dünya'dasın</span></div>
    <div><span class="yas-ozet-sayi">${enYakin.ad}</span><span class="soluk">sıradaki gezegen doğum günün:
      ${enYakin.kalan === 0 ? "bugün!" : `${gunYaz(enYakin.sonrakiNo, { day: "numeric", month: "long" })}, ${neZamanSonra(enYakin.kalan)}`}</span></div>`;

  kutu.innerHTML = sonuclar.map((g) => `
    <article class="cisim cisim-${g.sinif} ${g.ad === "Dünya" ? "buradasin" : ""}">
      <div class="cisim-ust">
        <span class="cisim-diski" aria-hidden="true"></span>
        <h3>${g.ad}</h3>
        <span class="cisim-oran" title="Güneş etrafında bir tur, Dünya zamanıyla">${yilUzunlugu(g)}</span>
      </div>
      <p class="cisim-agirlik">${yasYaz(g.yas)} <small class="yas-birim">yaşında</small></p>
      <div class="yas-cubuk" role="progressbar" aria-label="${g.ad} yılının tamamlanan kısmı"
           aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(g.ilerleme * 100)}">
        <span style="width:${(g.ilerleme * 100).toFixed(1)}%"></span>
      </div>
      <p class="yas-sonraki">${sonrakiYaz(g)}</p>
      <p class="cisim-bilgi">${g.bilgi}</p>
    </article>`).join("");
}

function tarihSecildi() {
  const iso = girdi.value;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso) || iso > bugunIso() || iso < girdi.min) {
    ozet.hidden = true;
    kutu.innerHTML = `<p class="soluk">Geçerli bir doğum tarihi seç.</p>`;
    return;
  }
  dogumTarihiKaydet(iso);
  ciz(iso);
}

// ---------------------------------------------------------------------
// Başlat: Doğum Günü sayfasında girilen tarih varsa onu kullan
// ---------------------------------------------------------------------
girdi.max = bugunIso();
girdi.addEventListener("change", tarihSecildi);
const kayitli = dogumTarihiOku();
if (kayitli) {
  girdi.value = kayitli;
  tarihSecildi();
}
