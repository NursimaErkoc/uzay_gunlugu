// =====================================================================
// Bu Gece Gökyüzü sayfası
// /api/gece'den bu gecenin bilgilerini alıp Ay, Güneş ve Gezegenler kartlarını doldurur.
// ikon(), metinTemizle(), yukleniyorHtml(), hataHtml() -> ortak.js'den geliyor.
// =====================================================================

// Konum seçici, saat() ve saatGun() de ortak.js'de (ISS sayfası da kullanıyor).

// ---------------------------------------------------------------------
// 1) Veriyi getir
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


function tarihUzun(iso) {
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "long", weekday: "long" });
}

function gunSonra(iso) {
  const gun = Math.round((new Date(iso) - Date.now()) / 86400000);
  return gun <= 0 ? "bugün" : gun === 1 ? "yarın" : `${gun} gün sonra`;
}

// ---------------------------------------------------------------------
// 2) Ay kartı
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
// 3) Güneş kartı
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
// 4) Gezegenler kartı
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
// Sayfa açılınca: konum seçiciyi kur (kayıtlı konum ya da Ankara ile başlar)
// ---------------------------------------------------------------------
konumSeciciKur({
  secimKutusu: document.getElementById("sehir"),
  konumButonu: document.getElementById("konumumu-kullan"),
  mesajKutusu: document.getElementById("konum-mesaji"),
  degisince: geceyiGetir,
});
