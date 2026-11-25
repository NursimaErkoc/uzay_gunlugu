# Uzay Günlüğü: Devam Notları

> **Yeni oturumda:** Claude'a şunu yaz: *"DEVAM.md dosyasını oku, kaldığımız yerden devam edelim."*
>
> Bu dosyada **hiçbir şifre veya anahtar yok**. Gizli değerler sadece `.env` dosyasında ve Render/GitHub ayarlarında duruyor. GitHub'a gönderilmesi güvenli.

Son güncelleme: 25 Kasım 2026 (Bu Gece Gökyüzü bölümü eklendi)

---

## 1. Proje özeti

NASA'nın günün fotoğrafını, günün uzay bilgisini, güncel uzay haberlerini, bu gecenin gökyüzünü (Ay, Güneş, gezegenler) ve aylık uzay takvimini (gökyüzü olayları, roket fırlatmaları, uzay etkinlikleri) gösteren, olaylar için e-posta hatırlatması gönderen bir web sitesi. Amaç: API, Git/GitHub, backend, frontend, veritabanı, test, CI ve yayınlama gibi temel yazılım bileşenlerini **gerçek bir proje yaparak öğrenmek**.

| | |
|---|---|
| **Canlı site** | https://uzay-gunlugu.onrender.com |
| **GitHub** | https://github.com/NursimaErkoc/uzay_gunlugu (public) |
| **Yerel klasör** | `C:\Users\hp\Desktop\uzay_günlüğü` |
| **Sağlık/teşhis sayfası** | https://uzay-gunlugu.onrender.com/api/saglik |
| **API dokümantasyonu** | https://uzay-gunlugu.onrender.com/docs |

## 2. Çalışma şekli (Claude için önemli)

- Kullanıcı **yazılıma yeni başlıyor**. Her şey **Türkçe**, adım adım ve kavramları açıklayarak anlatılmalı.
- Her adımın sonunda durulur, kullanıcı dener ve onaylar, sonra devam edilir.
- **Git akışı:** Her değişiklik için yeni dal → commit → push → GitHub'da PR → testler ✅ → Merge → `git switch main` + `git pull`. Git komutlarını kullanıcı kendisi çalıştırıyor (öğrenme amaçlı).
- Merge sonrası **Render otomatik yayına alıyor** (2-4 dk).
- Ortam: **Windows 11, VS Code, PowerShell**. Python 3.14.10, sanal ortam `.venv`.
- ⚠️ **Windows Akıllı Uygulama Denetimi**, derlenmiş DLL içeren paketleri engelliyor (SQLAlchemy/SQLModel engellendi). **Saf Python paketleri tercih edilmeli** (bu yüzden `sqlite3` ve `pg8000` kullanıldı).
- `.exe` dosyaları (uvicorn.exe, pip.exe) Uygulama Denetimi tarafından engellenebiliyor. Her zaman `python -m uvicorn` ve `python -m pip` kullanılmalı.
- Kullanıcıdan asla şifre/anahtar istenmez; sohbete yazdırılmaz. `.env` okunurken değerler gizlenmeli.

## 3. Komutlar

```
# Sunucuyu başlat (proje klasöründe)
.venv\Scripts\python -m uvicorn app.main:app --reload --app-dir backend
#   -> http://127.0.0.1:8000  (site)   http://127.0.0.1:8000/docs  (API)

# Testler (şu an 149 test, hepsi geçiyor)
.venv\Scripts\python -m pytest -v

# Paketler
.venv\Scripts\pip install -r requirements-dev.txt
```

## 4. Mimari

```
Tarayıcı (HTML/CSS/JS) ──fetch──► FastAPI (backend/app) ──► Dış servisler
                                      │                       NASA APOD (science.nasa.gov WordPress API)
                                      │                       Spaceflight News API · Launch Library 2
                                      │                       Google çeviri / MyMemory · Resend (e-posta)
                                      ▼
                        SQLite (yerelde) / PostgreSQL-Neon (canlıda)
GitHub Actions: testler her push'ta; "Hatırlatma kontrolü" 15 dk'da bir siteyi çağırır
```

```
backend/app/
  main.py            uç noktalar, yönetici anahtarı kontrolü, zamanlayıcı, önbellek başlıkları
  config.py          .env ayarları          db.py      SQLite/Postgres katmanı (pg8000)
  cache.py           hafıza + disk önbellek  mailer.py  Resend API (canlı) / Gmail SMTP (yerel)
  services/          nasa.py · facts.py · news.py · events.py · gokyuzu.py · iss.py · neo.py · epic.py · ceviri.py · reminders.py
backend/data/        facts.json (64 bilgi) · meteor_showers.json
backend/tests/       149 test (pytest)
frontend/            index.html · gokyuzu.html · iss.html · dunya.html · asteroitler.html · events.html · style.css · ortak.js (ikonlar + yıldızlar) · app.js · gokyuzu.js · iss.js · dunya.js · asteroitler.js · events.js
                     manifest.json · sw.js (service worker) · cevrimdisi.html · ikonlar/ (svg + 180/192/512 png)
.github/workflows/   testler.yml · hatirlatmalar.yml (cron)
```

**Ortam değişkenleri** (sadece adları; değerler `.env`'de ve Render'da):
- Yerel `.env`: `NASA_API_KEY`, `GMAIL_ADRESI`, `GMAIL_UYGULAMA_SIFRESI`. Render'a özel değerler `.env`'de **yorum satırı (#)** olarak saklanıyor; `#` işaretleri silinmemeli.
- Render: `NASA_API_KEY`, `GMAIL_ADRESI`, `GMAIL_UYGULAMA_SIFRESI`, `DATABASE_URL` (Neon), `YONETICI_ANAHTARI`, `SITE_ADRESI`, `RESEND_API_KEY`, `MYMEMORY_EPOSTA`
- GitHub Secrets: `SITE_ADRESI`, `YONETICI_ANAHTARI`

## 5. Tamamlananlar

| Adım | İçerik |
|---|---|
| 0-2 | Git/GitHub, ilk API çağrısı, FastAPI backend + önbellek |
| 3 | Frontend. NASA APOD eski API'si bozulduğu için yeni sitenin WordPress API'sine geçildi; Türkçe çeviri |
| 4 | Günün bilgisi + Türkçe haberler |
| 5 | Uzay takvimi: liste + aylık tablo görünümü, gökyüzü olayları astronomy-engine ile hesaplanıyor |
| 6 | E-posta hatırlatmaları (veritabanı + zamanlayıcı) |
| 7 | 66 otomatik test, branch/PR, GitHub Actions |
| 8 | Render + Neon + cron, yönetici anahtarı, çift gönderim kilidi |
| Sonra | Render SMTP'yi engellediği için **Resend** API'ye geçildi (çalışıyor ✅) |
| Sonra | **Yeni görünüm:** koyu tema, hareketli yıldızlar (canvas), Michroma + Exo 2 fontları, emojiler kaldırıldı, SVG ikonlar |
| Sonra | Tarayıcı önbelleği düzeltmesi (`Cache-Control: no-cache` + `?v=2` sürüm etiketleri) |
| Sonra | Çeviriler kalıcı olarak veritabanında (`ceviriler` tablosu), MyMemory yedeği, `/api/saglik` teşhisi |
| Sonra | **Bu Gece Gökyüzü** (`gokyuzu.html`, `GET /api/gece`): Ay evresi çizimi, gün batımı/tam karanlık/gün doğumu, görünen gezegenler + gece çizelgesi, şehir listesi veya tarayıcı konumu (sunucuda 1 ondalığa yuvarlanır, 10 dk önbellek) |
| Sonra | **ISS Şu An Nerede** (`iss.html`, `GET /api/iss`, `GET /api/uzaydakiler`): ISS konumu CelesTrak TLE + **sgp4** ile hesaplanıyor (TLE 6 saat diskte), Leaflet haritası (Esri karoları; CARTO artık anahtar istiyor), yörünge izi, gece tarafı gölgesi, Güneş ışığında/gölgede; uzaydakiler LL2 `astronauts` + `expeditions` ile istasyona göre gruplu (Starman ve Laika ayıklanıyor) |
| Sonra | ISS TLE için **yedek kaynaklar** (CelesTrak → ARISS → wheretheiss.at → TLE API, son çare 7 günlük eski kayıt); canlıda CelesTrak Render'dan zaman aşımı veriyor, ARISS kullanılıyor. `/api/saglik` → `iss_tle` |
| Sonra | **ISS'i Gör** (`GET /api/iss/gecisler`, ISS sayfasında kart): 10 günlük görünür geçişler (ISS >10° + ISS Güneş ışığında + gözlemcide Güneş < -6°), parlaklık tahmini, gölgeye girme, gökyüzü diyagramı, geri sayım. **Heavens-Above ile karşılaştırıldı** (Ankara, 12/12 geçiş, saniyeler içinde aynı). Şehir seçici `ortak.js`'e taşındı (`konumSeciciKur`), Bu Gece ve ISS sayfası aynı seçimi paylaşıyor |
| Sonra | **Yaklaşan Asteroitler** (`asteroitler.html`, `GET /api/asteroitler`, `services/neo.py`): NASA NeoWs, 7 gün, 6 saat disk önbelleği. **NASA anahtarı ilk kez burada kullanılıyor.** ⚠️ NeoWs cevabındaki `links` alanı anahtarı içeriyor: sadece gereken alanlar tarayıcıya gönderiliyor, hata mesajlarına istek adresi yazılmıyor (testle korunuyor). Karşılaştırmalar (Ay'ın X katı, Galata Kulesi/futbol sahası/Eyfel, mermi/uçak hızı), logaritmik uzaklık çizelgesi (SVG, ipucu kutusu), "potansiyel tehlikeli" açıklaması |
| Sonra | **PWA**: `manifest.json`, `sw.js` (strateji: önce internet, olmazsa kayıtlı kopya; `/api/iss` ve `/api/reminders` kaydedilmez; kayıt biçimi değişirse sw.js'deki `SURUM` artırılmalı), `cevrimdisi.html`, ikonlar SVG'den Edge ile PNG'ye çevrildi (Pillow yok). **Logo:** ince çizgili hilal + noktalı yörünge + küçük uydu (kullanıcı birçok seçenek arasından seçti, "sonra değiştiririz" dedi; çizgi film tarzı ve renkli dolgulu tasarımları beğenmedi, sade ince çizgi tarzını seviyor; uydu, takımyıldız, hilal ve Satürn öğelerini beğendi). Logo değişirse: `ikonlar/ikon.svg` düzenlenir, sonra 512/192/180 PNG'ler Edge headless `--screenshot` ile yeniden üretilir. `ortak.js`: SW kaydı, "Uygulamayı yükle" düğmesi (beforeinstallprompt), iPhone için "Paylaş → Ana Ekrana Ekle" notu, çevrimdışı şeridi |
| Sonra | **Dünya'nın Fotoğrafı** (`dunya.html`, `GET /api/dunya?tarih=`, `services/epic.py`): NASA EPIC, anahtarsız. Günün 10-20 fotoğrafı **akıcı** oynatılıyor: `<canvas>` üzerinde requestAnimationFrame ile çapraz geçiş (kullanıcı ilk sürümdeki sıçramalı geçişin gözü yorduğunu söyledi); fotoğraflar bir kez ekran boyutuna küçültülüp hazır tutuluyor, hız düğmesi (1x/2x/0,5x), zaman çubuğu, önizleme şeridi, görünen bölge adı (merkez boylamına göre), Türkiye görünürlüğü (merkeze <70°), tarih seçici. Son gün 3 saat, geçmiş günler 7 gün önbellekte |

Son merge: **PR #14** (`dunya`). Üzerinde çalışılan dal: `menu` (gruplu menü; merge edilince burayı güncelle).

## 6. ⏳ Açık konular (sırayla)

### 6.1 Canlı sitede çeviri: İLK YAPILACAK
**Durum:** Canlı sitede haberler, APOD ve takvim açıklamaları İngilizce görünüyor. Yerelde çeviri çalışıyor.
- Google çevirisi Render'dan gelen istekleri **engelliyor** (`HTTP 302`). Bu kalıcı, beklenen bir durum.
- MyMemory (yedek): e-posta ayarı Render'da tanımlı ve çalışıyor (`mymemory_eposta_tanimli: true`), ama 24 Kasım'da **günlük kota doldu** ("YOU USED ALL AVAILABLE FREE TRANSLATIONS FOR TODAY"). Kota gece ~03:00'te (TR) sıfırlanıyor.
- Beklenen: Kota sıfırlanınca çeviriler yapılıp **Neon'a kalıcı kaydedilecek**. Sonra sadece yeni metinler çevrilecek.

**Kontrol:** https://uzay-gunlugu.onrender.com/api/saglik → `ceviri_son_hatalar.mymemory` `null` ise çalışıyor. Ayrıca haberlerde `baslik_tr` dolu mu?

**Hâlâ çalışmıyorsa (Plan B):**
- **DeepL API Free:** en iyi kalite, ayda 500 bin karakter. Kart doğrulaması istiyor. `ceviri.py`'ye yeni bir servis fonksiyonu eklenip Render'a `DEEPL_API_KEY` girilir.
- **GitHub Actions ile çeviri:** Cron iş akışı Render dışından çevrilmemiş metinleri çevirip Neon'a yazar.

### 6.2 GitHub cron gecikmesi
"Hatırlatma kontrolü" 15 dk'da bir çalışmalıydı, ilk gün sadece 1 kez kendiliğinden çalıştı. Birkaç gün izlenecek. Düzensizse: **cron-job.org** (ücretsiz) aynı adresi çağırır: `POST /api/gorevler/hatirlatmalar` + başlık `X-Yonetici-Anahtari`.

### 6.3 Küçük temizlikler
- README yol haritasında **Adım 7 ve 8 hâlâ `[ ]`**. İşaretlenmeli, ayrıca README'ye canlı site linki eklenebilir.
- Birleşmiş eski dallar silinebilir: `testler`, `yayin`, `eposta-api`, `gorunum`, `ceviri-duzeltme`, `gorunum-ceviri`, `ceviri-teshis`, `bu-gece`, `iss-canli`, `iss-yedek-kaynak`, `iss-gor`, `asteroitler`, `pwa`
  ```
  git branch -d testler yayin eposta-api gorunum ceviri-duzeltme gorunum-ceviri ceviri-teshis bu-gece iss-canli iss-yedek-kaynak iss-gor asteroitler pwa
  git push origin --delete testler yayin eposta-api gorunum ceviri-duzeltme gorunum-ceviri ceviri-teshis bu-gece iss-canli iss-yedek-kaynak iss-gor asteroitler pwa
  ```
- CSS/JS'te büyük değişiklik yapınca tüm `.html` dosyalarındaki `?v=9` → `?v=10` yapılmalı.
- Kullanıcı ileride site adresini değiştirmek isteyebilir: Render'da yeni servis açmak ya da alan adı bağlamak gerekir.

## 7. 🚀 Sırada: Yeni bölümler

Kullanıcı bu sırayla yapılmasını istedi (25 Kasım 2026):

1. ~~**Bu Gece Gökyüzü**~~ ✅ (PR #8)
2. ~~**ISS Şu An Nerede**~~ ✅ (PR #9, yedek TLE kaynakları PR #10)
3. ~~**ISS'i Gör**~~ ✅ (PR #11)
4. ~~**Yaklaşan Asteroitler**~~ ✅ (PR #12)
5. ~~**PWA**~~ ✅ (PR #13)
6. ~~**Mars'tan Fotoğraflar**~~ ❌ İPTAL (kullanıcı vazgeçti, 25 Kasım 2026). Not: api.nasa.gov/mars-photos kapanmış (Heroku "No such app"); mars.nasa.gov ham görüntü akışları çalışıyordu (Perseverance: /rss/api/?feed=raw_images&category=mars2020, Curiosity: /api/v1/raw_image_items/).
7. ~~**Dünya'nın Bugünkü Fotoğrafı**~~ ✅ (dal: `dunya`)
8. **Gezegenlerde Ağırlığın** ⬅️ SIRADAKİ: Sadece frontend, eğlenceli hesaplayıcı.
9. **Gök Haritası:** Bu gecenin yıldız/takımyıldız haritası (şehre göre).

Önerilip seçilmeyenler: Uzay Havası (NOAA Kp), Favorilerim, Uzay Bilgi Yarışması.

✅ **GRUPLU MENÜ** (dal: `menu`): Günlük · **Keşfet ▾** (Bu Gece, ISS, Dünya, Asteroitler) · Uzay Takvimi. `<details class="menu-grup">` ile yapıldı (JS'siz de açılır); ortak.js `menuGruplariniKur()` dışarı tıklayınca/Esc ile kapatır. Yeni sayfalar (Ağırlık, Gök Haritası) **6 sayfanın hepsinde** `.menu-acilir` içine eklenmeli; grupta bir sayfa aktifse `<summary class="aktif">` olmalı.

Tasarım dili: koyu uzay teması, Michroma başlıklar / Exo 2 metin, **emoji yok**. İkonlar `frontend/ortak.js`'teki `IKONLAR` setinden (gerekirse yeni SVG eklenir). Renkler `style.css` başındaki CSS değişkenlerinde.
