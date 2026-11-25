// =====================================================================
// Service worker: tarayıcının sitemiz için arka planda çalıştırdığı yardımcı.
// Sayfa ile internet arasına girer; her isteği (fetch) görür ve ne yapılacağına karar verir.
//
// Stratejimiz: "ÖNCE İNTERNET, OLMAZSA KAYITLI KOPYA"
//   - İnternet varsa her zaman en güncel hali gelir (eski içerik takılı kalmaz)
//     ve gelen cevabın bir kopyası kaydedilir.
//   - İnternet yoksa son kaydedilen kopya gösterilir.
//   - Hiç kaydı olmayan bir sayfa istenirse "Çevrimdışısın" sayfası gösterilir.
//
// Bu dosyayı değiştirince tarayıcı yeni sürümü kendiliğinden fark eder (sunucu bu dosya için
// "her seferinde kontrol et" diyor). Kayıt biçimini değiştirirsen SURUM'ü artır: eski kayıtlar silinir.
// =====================================================================

const SURUM = "v1";
const KAYIT = `uzay-gunlugu-${SURUM}`;
const CEVRIMDISI_SAYFASI = "/cevrimdisi.html";

// Kurulum: çevrimdışı sayfasını ve ikonları baştan kaydet
self.addEventListener("install", (olay) => {
  olay.waitUntil(
    caches.open(KAYIT)
      .then((kayit) => kayit.addAll([CEVRIMDISI_SAYFASI, "/ikonlar/ikon.svg", "/ikonlar/ikon-192.png"]))
      .then(() => self.skipWaiting()),   // beklemeden hemen devreye gir
  );
});

// Etkinleşme: eski sürümlerin kayıtlarını sil
self.addEventListener("activate", (olay) => {
  olay.waitUntil(
    caches.keys()
      .then((adlar) => Promise.all(adlar.filter((ad) => ad !== KAYIT).map((ad) => caches.delete(ad))))
      .then(() => self.clients.claim()),   // açık sayfaları da hemen yönetmeye başla
  );
});

// Hangi istekleri kaydedelim?
function kaydedilsinMi(istek, adres) {
  if (istek.method !== "GET") return false;                        // sadece okuma istekleri
  if (adres.origin === self.location.origin) {
    if (adres.pathname === "/api/iss") return false;               // 3 saniyede bir değişiyor, eskisi işe yaramaz
    if (adres.pathname.startsWith("/api/reminders")) return false; // yöneticiye özel bilgiler
    return true;                                                   // sayfalar, CSS/JS, diğer API'ler
  }
  // Dış adreslerden sadece fontlar ve harita kütüphanesi (resimleri ve harita karolarını değil:
  // çok yer kaplarlar)
  return ["fonts.googleapis.com", "fonts.gstatic.com", "cdnjs.cloudflare.com"].includes(adres.hostname);
}

self.addEventListener("fetch", (olay) => {
  const istek = olay.request;
  const adres = new URL(istek.url);
  if (!kaydedilsinMi(istek, adres)) return;   // bu isteğe karışma, tarayıcı normal şekilde yapsın

  olay.respondWith((async () => {
    try {
      const cevap = await fetch(istek);
      // Sadece başarılı cevapları kaydet (hata sayfasını kaydedip sonra onu göstermeyelim)
      if (cevap.ok || cevap.type === "opaque") {
        const kopya = cevap.clone();   // cevap bir kez okunabilir: biri sayfaya, kopyası kayda
        olay.waitUntil(caches.open(KAYIT).then((kayit) => kayit.put(istek, kopya)));
      }
      return cevap;
    } catch {
      // İnternet yok: kayıtlı kopyaya bak
      const kayitli = await caches.match(istek);
      if (kayitli) return kayitli;
      if (istek.mode === "navigate") return caches.match(CEVRIMDISI_SAYFASI);   // sayfa isteğiyse
      return Response.error();
    }
  })());
});
