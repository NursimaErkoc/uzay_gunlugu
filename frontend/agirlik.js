// =====================================================================
// Gezegenlerde Ağırlığın sayfası
// İnternete bağlanmadan, tamamen tarayıcıda hesaplanır. ikon() -> ortak.js'den geliyor.
//
// Hesap:  oradaki ağırlık = Dünya'daki ağırlık × (oradaki çekim / Dünya'daki çekim)
//   ör. Ay'da çekim 1,62, Dünya'da 9,81 m/s² -> oran 0,165 -> 50 kg'lık biri Ay'da 8,3 kg gösterir.
// Zıplama yüksekliği çekimle TERS orantılı (çekim yarıya inerse iki kat yükseğe çıkarsın).
// Düşme süresi: t = √(2h / g)   (h = 1 metre)
// =====================================================================

const DUNYA_CEKIMI = 9.81;          // m/s²
const DUNYADA_ZIPLAMA = 0.5;        // metre
const DUSME_YUKSEKLIGI = 1;         // metre

// cekim: yüzey çekimi (m/s²). "yerde": Türkçe "-de" ekli hali (Mars'ta, Ay'da ...)
const CISIMLER = [
  { ad: "Güneş", yerde: "Güneş'te", sinif: "gunes", cekim: 274.0,
    bilgi: "Ayakta durabilseydin bile kendi ağırlığın seni ezerdi. Yüzeyi yaklaşık 5.500 °C." },
  { ad: "Merkür", yerde: "Merkür'de", sinif: "merkur", cekim: 3.70,
    bilgi: "Mars'tan küçük ama çekimi neredeyse aynı: içinde çok büyük ve yoğun bir demir çekirdek var." },
  { ad: "Venüs", yerde: "Venüs'te", sinif: "venus", cekim: 8.87,
    bilgi: "Çekimi Dünya'ya en çok benzeyen gezegen; ama hava basıncı Dünya'nın 92 katı." },
  { ad: "Dünya", yerde: "Dünya'da", sinif: "dunya", cekim: DUNYA_CEKIMI,
    bilgi: "Karşılaştırma noktamız. Şu an buradasın." },
  { ad: "Ay", yerde: "Ay'da", sinif: "ay", cekim: 1.62,
    bilgi: "Apollo astronotları bu yüzden yürümek yerine kanguru gibi zıplayarak ilerledi." },
  { ad: "Mars", yerde: "Mars'ta", sinif: "mars", cekim: 3.72,
    bilgi: "Gelecekte Mars'a gidecek astronotlar, bu düşük çekimde kaslarını kaybetmemek için her gün spor yapmak zorunda." },
  { ad: "Jüpiter", yerde: "Jüpiter'de", sinif: "jupiter", cekim: 24.79,
    bilgi: "Güneş Sistemi'nin en güçlü gezegen çekimi. Burada bir adım atmak bile yorucu olurdu." },
  { ad: "Satürn", yerde: "Satürn'de", sinif: "saturn", cekim: 10.44,
    bilgi: "Ortalama yoğunluğu sudan az: dev bir küvete koyabilseydik yüzerdi." },
  { ad: "Uranüs", yerde: "Uranüs'te", sinif: "uranus", cekim: 8.69,
    bilgi: "Dünya'dan 4 kat büyük ama yüzeyinde biraz daha hafif hissederdin." },
  { ad: "Neptün", yerde: "Neptün'de", sinif: "neptun", cekim: 11.15,
    bilgi: "Güneş Sistemi'nin en hızlı rüzgârları burada esiyor: saatte 2.000 km'yi aşıyor." },
  { ad: "Plüton", yerde: "Plüton'da", sinif: "pluton", cekim: 0.62,
    bilgi: "Bir basketbol potasının üstüne kadar zıplayabilirdin. 2006'dan beri cüce gezegen sayılıyor." },
];

const giris = document.getElementById("agirlik");
const kutu = document.getElementById("cisimler");
const HAFIZA_ANAHTARI = "uzay-agirlik";

// ---------------------------------------------------------------------
// Sayı biçimleri (Türkçe: virgül ve nokta)
// ---------------------------------------------------------------------
function sayi(deger, ondalik) {
  return deger.toLocaleString("tr-TR", { minimumFractionDigits: ondalik, maximumFractionDigits: ondalik });
}
function kgYaz(kg) { return `${sayi(kg, kg >= 100 ? 0 : 1)} kg`; }
function yukseklikYaz(m) { return m < 1 ? `${sayi(m * 100, 0)} cm` : `${sayi(m, 1)} m`; }
function sureYaz(sn) { return `${sayi(sn, 2)} sn`; }

// ---------------------------------------------------------------------
// Kartları çiz
// ---------------------------------------------------------------------
function kartlariCiz() {
  const kg = Number(giris.value);
  const gecerli = Number.isFinite(kg) && kg > 0 && kg <= 1000;
  giris.setAttribute("aria-invalid", String(!gecerli));

  kutu.innerHTML = CISIMLER.map((c) => {
    const oran = c.cekim / DUNYA_CEKIMI;
    const agirlik = gecerli ? kgYaz(kg * oran) : "—";
    const zipla = DUNYADA_ZIPLAMA / oran;
    const dusme = Math.sqrt((2 * DUSME_YUKSEKLIGI) / c.cekim);
    return `
      <article class="cisim cisim-${c.sinif} ${c.sinif === "dunya" ? "buradasin" : ""}">
        <div class="cisim-ust">
          <span class="cisim-diski" aria-hidden="true"></span>
          <h3>${c.ad}</h3>
          <span class="cisim-oran" title="Dünya'nın kaç katı">×${sayi(oran, oran < 1 ? 2 : 1)}</span>
        </div>
        <p class="cisim-agirlik"><span class="gizli">${c.yerde} ağırlığın: </span>${agirlik}</p>
        <dl class="cisim-degerler">
          <div><dt>Zıplama</dt><dd>${yukseklikYaz(zipla)}</dd></div>
          <div><dt>1 m'den düşüş</dt><dd>${sureYaz(dusme)}</dd></div>
        </dl>
        <p class="cisim-bilgi">${c.bilgi}</p>
      </article>`;
  }).join("");

  if (gecerli) {
    try { localStorage.setItem(HAFIZA_ANAHTARI, String(kg)); } catch { /* gizli sekmede olmayabilir */ }
  }
}

// Önceki ziyarette yazılan değeri hatırla (sadece bu tarayıcıda kalır, hiçbir yere gönderilmez)
try {
  const kayitli = localStorage.getItem(HAFIZA_ANAHTARI);
  if (kayitli) giris.value = kayitli;
} catch { /* sorun değil, 50 kg ile başlarız */ }

giris.addEventListener("input", kartlariCiz);
kartlariCiz();
