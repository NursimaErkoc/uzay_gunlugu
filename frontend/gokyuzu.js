// =====================================================================
// Bu Gece Gökyüzü sayfası
// /api/gece'den bu gecenin bilgilerini alıp Ay, Güneş ve Gezegenler kartlarını doldurur.
// ikon(), metinTemizle(), yukleniyorHtml(), hataHtml() -> ortak.js'den geliyor.
// =====================================================================

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
const KAYIT_ANAHTARI = "uzay-gunlugu-konum";

const sehirKutusu = document.getElementById("sehir");
const konumButonu = document.getElementById("konumumu-kullan");
const konumMesaji = document.getElementById("konum-mesaji");
const VARSAYILAN_MESAJ = konumMesaji.textContent;

// ---------------------------------------------------------------------
// 1) Konum seçimi
// Seçilen konum tarayıcıda (localStorage) hatırlanır. localStorage bazı durumlarda
// (gizli sekme vb.) çalışmayabilir; o yüzden try/catch içinde kullanıyoruz.
// ---------------------------------------------------------------------
function kayitliKonum() {
  try {
    const konum = JSON.parse(localStorage.getItem(KAYIT_ANAHTARI));
    // Bozuk ya da eski biçimli bir kayıt varsa kullanma
    return konum && typeof konum.enlem === "number" && typeof konum.boylam === "number" ? konum : null;
  } catch {
    return null;
  }
}

function konumuKaydet(konum) {
  try {
    localStorage.setItem(KAYIT_ANAHTARI, JSON.stringify(konum));
  } catch { /* kaydedemezsek sorun değil */ }
}

function sehirListesiniDoldur(secili) {
  const secenekler = SEHIRLER.map((s) =>
    `<option value="${s.ad}" ${s.ad === secili ? "selected" : ""}>${s.ad}</option>`);
  if (secili === "Konumum") secenekler.unshift(`<option value="Konumum" selected>Konumum</option>`);
  sehirKutusu.innerHTML = secenekler.join("");
}

sehirKutusu.addEventListener("change", () => {
  const sehir = SEHIRLER.find((s) => s.ad === sehirKutusu.value);
  if (!sehir) return;
  sehirListesiniDoldur(sehir.ad);   // "Konumum" seçeneği listeden kalksın
  konumuKaydet(sehir);
  konumMesaji.textContent = VARSAYILAN_MESAJ;
  geceyiGetir(sehir);
});

konumButonu.addEventListener("click", () => {
  if (!navigator.geolocation) {
    konumMesaji.textContent = "Tarayıcın konum özelliğini desteklemiyor.";
    return;
  }
  konumMesaji.textContent = "Konum alınıyor…";
  navigator.geolocation.getCurrentPosition(
    (yer) => {
      const konum = {
        ad: "Konumum",
        // 2 ondalık (~1 km) yeterli; sunucu zaten 1 ondalığa yuvarlıyor
        enlem: Number(yer.coords.latitude.toFixed(2)),
        boylam: Number(yer.coords.longitude.toFixed(2)),
      };
      sehirListesiniDoldur("Konumum");
      konumuKaydet(konum);
      konumMesaji.textContent = `Konumun kullanılıyor (yaklaşık). ${VARSAYILAN_MESAJ}`;
      geceyiGetir(konum);
    },
    () => { konumMesaji.textContent = "Konum alınamadı. İzin vermediysen listeden şehir seçebilirsin."; },
    { timeout: 10000, maximumAge: 10 * 60 * 1000 },
  );
});

// ---------------------------------------------------------------------
// 2) Veriyi getir
// ---------------------------------------------------------------------
async function geceyiGetir(konum) {
  const kutular = ["ay-icerik", "gunes-icerik", "gezegen-icerik"].map((id) => document.getElementById(id));
  kutular.forEach((k) => (k.innerHTML = yukleniyorHtml("Gökyüzü hesaplanıyor")));
  try {
    const cevap = await fetch(`/api/gece?enlem=${konum.enlem}&boylam=${konum.boylam}`);
    const veri = await cevap.json();
    if (!cevap.ok) throw new Error(veri.detail || "Bilinmeyen hata");
    ayGoster(veri.ay);
    gunesGoster(veri.gunes);
    gezegenleriGoster(veri.gezegenler, veri.gunes);
  } catch (hata) {
    kutular.forEach((k) => (k.innerHTML = hataHtml("Gökyüzü bilgisi alınamadı.", hata.message)));
  }
}

// ---------------------------------------------------------------------
// 3) Zaman yazdırma yardımcıları
// Sunucu zamanları UTC gönderiyor ("...Z"). new Date() bunu otomatik olarak
// cihazın saat dilimine çevirir.
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

function tarihUzun(iso) {
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "long", weekday: "long" });
}

function gunSonra(iso) {
  const gun = Math.round((new Date(iso) - Date.now()) / 86400000);
  return gun <= 0 ? "bugün" : gun === 1 ? "yarın" : `${gun} gün sonra`;
}

// ---------------------------------------------------------------------
// 4) Ay kartı
// ---------------------------------------------------------------------
/**
 * Ay'ın evresini SVG olarak çizer.
 * Aydınlık kısım iki yaydan oluşur:
 *   - dış kenar: dairenin yarısı (büyüyen Ay'da sağ yarı)
 *   - gölge sınırı (terminatör): yatay yarıçapı aydınlık oranına göre değişen bir elips yayı
 * Küçülen Ay'da çizimi aynada çevirir gibi yansıtıyoruz (Kuzey Yarımküre'den görünüş).
 */
function ayCizimi(aydinlik, buyuyen) {
  const r = 50, m = 60;                              // yarıçap, merkez
  const elipsX = Math.abs(1 - 2 * aydinlik) * r;     // gölge sınırının genişliği
  const sisik = aydinlik > 0.5 ? 1 : 0;              // şişkin Ay'da sınır karşı tarafa taşar
  const yol = `M ${m} ${m - r} A ${r} ${r} 0 0 1 ${m} ${m + r} A ${elipsX} ${r} 0 0 ${sisik} ${m} ${m - r} Z`;
  const yansit = buyuyen ? "" : `transform="translate(${2 * m} 0) scale(-1 1)"`;
  return `
    <svg class="ay-cizimi" viewBox="0 0 120 120" role="img" aria-label="Ay'ın bu geceki görünüşü">
      <defs>
        <radialGradient id="ay-isik" cx="45%" cy="40%" r="65%">
          <stop offset="0%" stop-color="#fbf8ee"/>
          <stop offset="100%" stop-color="#c9c3ad"/>
        </radialGradient>
        <clipPath id="ay-diski"><circle cx="${m}" cy="${m}" r="${r}"/></clipPath>
      </defs>
      <circle cx="${m}" cy="${m}" r="${r}" fill="#161b33"/>
      <g ${yansit}><path d="${yol}" fill="url(#ay-isik)"/></g>
      <!-- Ay'daki koyu "denizler" (maria): sadece süs, hafif saydam -->
      <g clip-path="url(#ay-diski)" fill="#000" opacity=".1">
        <circle cx="48" cy="42" r="13"/><circle cx="70" cy="38" r="9"/><circle cx="66" cy="60" r="11"/>
        <circle cx="44" cy="70" r="8"/><circle cx="78" cy="80" r="6"/>
      </g>
      <circle cx="${m}" cy="${m}" r="${r}" fill="none" stroke="rgba(255,255,255,.12)"/>
    </svg>`;
}

function ayGoster(ay) {
  const yuzde = Math.round(ay.aydinlik * 100);
  document.getElementById("ay-icerik").innerHTML = `
    <div class="ay-ust">
      ${ayCizimi(ay.aydinlik, ay.buyuyen)}
      <div>
        <p class="buyuk-deger">${metinTemizle(ay.evre)}</p>
        <p class="soluk">%${yuzde} aydınlık · ${ay.buyuyen ? "büyüyor" : "küçülüyor"}</p>
      </div>
    </div>
    <dl class="bilgi-tablosu">
      <dt>Ay doğuşu</dt><dd>${saatGun(ay.dogus)}</dd>
      <dt>Ay batışı</dt><dd>${saatGun(ay.batis)}</dd>
      <dt>Sonraki dolunay</dt><dd>${tarihUzun(ay.sonraki_dolunay)} <small>${gunSonra(ay.sonraki_dolunay)}</small></dd>
      <dt>Sonraki yeni ay</dt><dd>${tarihUzun(ay.sonraki_yeni_ay)} <small>${gunSonra(ay.sonraki_yeni_ay)}</small></dd>
    </dl>
    <p class="gozlem-notu">${metinTemizle(ay.not)}</p>`;
}

// ---------------------------------------------------------------------
// 5) Güneş kartı
// ---------------------------------------------------------------------
function gunesGoster(gunes) {
  const kutu = document.getElementById("gunes-icerik");
  const saatDk = gunes.gece_suresi_dakika;
  const sure = `${Math.floor(saatDk / 60)} sa ${saatDk % 60} dk`;
  kutu.innerHTML = `
    <dl class="bilgi-tablosu">
      <dt>Gün batımı</dt><dd>${saatGun(gunes.gun_batimi)}</dd>
      <dt>Tam karanlık</dt><dd>${gunes.karanlik_baslangici ? `${saatGun(gunes.karanlik_baslangici)} – ${saatGun(gunes.karanlik_bitisi)}` : "—"}</dd>
      <dt>Gün doğumu</dt><dd>${saatGun(gunes.gun_dogumu)}</dd>
      <dt>Gece süresi</dt><dd>${saatDk ? sure : "—"}</dd>
    </dl>
    ${gunes.not ? `<div class="not">${ikon("uyari")}<span>${metinTemizle(gunes.not)}</span></div>` : ""}
    <p class="aciklama-notu">Tam karanlık: Güneş ufkun 18° altına iner, gökyüzü tamamen kararır.
      Sönük yıldızları görmek için en iyi zaman.</p>`;
}

// ---------------------------------------------------------------------
// 6) Gezegenler kartı
// Her gezegen için gece boyunca görünür olduğu saatleri gösteren bir çubuk çiziyoruz.
// Çubuğun solu gün batımı, sağı gün doğumu.
// ---------------------------------------------------------------------
function gezegenleriGoster(gezegenler, gunes) {
  const kutu = document.getElementById("gezegen-icerik");
  const bas = gunes.gun_batimi ? new Date(gunes.gun_batimi) : null;
  const son = gunes.gun_dogumu ? new Date(gunes.gun_dogumu) : null;
  const cizelgeVar = bas && son;

  // Bir zamanın gece çizelgesindeki yeri (% olarak)
  const yer = (iso) => Math.min(100, Math.max(0, ((new Date(iso) - bas) / (son - bas)) * 100));

  // Çizelgenin üstündeki saat etiketleri: her tam saat başı (çok sıkışmasın diye 2 saatte bir)
  let saatler = "";
  if (cizelgeVar) {
    const isaret = new Date(bas);
    isaret.setMinutes(0, 0, 0);
    isaret.setHours(isaret.getHours() + 1);
    while (isaret < son) {
      if (isaret.getHours() % 2 === 0) {
        saatler += `<span style="left:${yer(isaret.toISOString())}%">${String(isaret.getHours()).padStart(2, "0")}</span>`;
      }
      isaret.setHours(isaret.getHours() + 1);
    }
  }

  const satirlar = gezegenler.map((g) => {
    const sinif = `gezegen-${g.ad.toLowerCase().replace("ü", "u").replace("ö", "o")}`;
    if (!g.gorunur) {
      return `
        <div class="gezegen-satiri gorunmuyor ${sinif}">
          <div class="gezegen-adi">${ikon("gezegen")}<strong>${metinTemizle(g.ad)}</strong></div>
          <p class="soluk">Bu gece görünmüyor (ufkun altında ya da Güneş'e çok yakın).</p>
        </div>`;
    }
    const cubuk = cizelgeVar ? `
      <div class="gece-cubugu" aria-hidden="true">
        <span class="gorunur-aralik" style="left:${yer(g.ilk_gorunus)}%; width:${yer(g.son_gorunus) - yer(g.ilk_gorunus)}%"></span>
        <span class="en-iyi-nokta" style="left:${yer(g.en_iyi_zaman)}%"></span>
      </div>` : "";
    return `
      <div class="gezegen-satiri ${sinif}">
        <div class="gezegen-adi">${ikon("gezegen")}<strong>${metinTemizle(g.ad)}</strong>
          <span class="etiket">${metinTemizle(g.parlaklik)}</span></div>
        <p class="gezegen-ayrinti">
          En iyi zaman <strong>${saatGun(g.en_iyi_zaman)}</strong> · ${metinTemizle(g.yon)} yönünde ·
          ufuktan ${g.yukseklik}° yukarıda
        </p>
        <p class="soluk">Görünür: ${saatGun(g.ilk_gorunus)} – ${saatGun(g.son_gorunus)}</p>
        ${cubuk}
      </div>`;
  });

  // Çizelge başlığı: uçlarda gün batımı/doğumu, altında saatler. Çubuklarla aynı genişlikte.
  const ust = cizelgeVar ? `
    <div class="cizelge-ust" aria-hidden="true">
      <div class="cizelge-uclar">
        <span>${ikon("gunes")} Gün batımı ${saat(gunes.gun_batimi)}</span>
        <span>Gün doğumu ${saat(gunes.gun_dogumu)} ${ikon("gunes")}</span>
      </div>
      <div class="cizelge-saatler">${saatler}</div>
    </div>` : "";
  kutu.innerHTML = ust + satirlar.join("");
}

// ---------------------------------------------------------------------
// Sayfa açılınca: kayıtlı konum varsa onu, yoksa Ankara'yı kullan
// ---------------------------------------------------------------------
const baslangicKonumu = kayitliKonum() || SEHIRLER.find((s) => s.ad === "Ankara");
sehirListesiniDoldur(baslangicKonumu.ad);
geceyiGetir(baslangicKonumu);
