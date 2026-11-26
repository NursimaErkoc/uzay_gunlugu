# Uzay Günlüğü: Devam Notları

> **Yeni oturumda:** Claude'a şunu yaz: *"DEVAM.md dosyasını oku, kaldığımız yerden devam edelim."*
>
> Bu dosyada **hiçbir şifre veya anahtar yok**. Gizli değerler sadece `.env` dosyasında ve Render/GitHub ayarlarında duruyor. GitHub'a gönderilmesi güvenli.

Son güncelleme: 26 Kasım 2026 (Doğum Günü Fotoğrafın ✅, Gezegenlerde Yaşın eklendi)

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

# Testler (şu an 190 test, hepsi geçiyor)
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
backend/tests/       190 test (pytest)
frontend/            index.html · gokyuzu.html · iss.html · dunya.html · asteroitler.html · agirlik.html · gokharitasi.html · dogumgunu.html · yas.html · events.html · style.css · ortak.js (ikonlar + yıldızlar) · app.js · gokyuzu.js · iss.js · dunya.js · asteroitler.js · agirlik.js · gokharitasi.js · dogumgunu.js · yas.js · events.js · veri/gok.json (yıldız verisi; `araclar/gok_verisi_hazirla.py` üretir)
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

Son merge: **PR #21** (`dogum-gunu`). Üzerinde çalışılan dal: `yas` (merge edilince burayı güncelle).

## 6. ⏳ Açık konular (sırayla)

### 6.1 Canlı sitede çeviri: DeepL'e geçildi (dal: `deepl`)
**Teşhis (25 Kasım):** Google Render'ı engelliyor (`HTTP 302`). MyMemory'nin kotası e-postaya rağmen her gün doluyor: büyük ihtimalle kota Render'ın **paylaşılan IP adresine** göre de uygulanıyor (başka siteler bitiriyor). Beklemek çözüm değil.

**Çözüm:** Kullanıcı **DeepL API Free**'yi seçti. Sıra: DeepL → Google → MyMemory. `config.DEEPL_API_KEY` (`:fx` ile biten anahtar → `api-free.deepl.com`). Hata mesajlarında anahtar asla görünmez (testli). `/api/saglik` → `deepl_anahtar_tanimli`, `ceviri_son_hatalar.deepl`.
- Yapılacak: kullanıcı DeepL hesabı açıp anahtarı **Render → Environment → `DEEPL_API_KEY`** olarak girecek (anahtarı sohbete yazmasın).
- Kontrol: `/api/saglik` → `deepl_anahtar_tanimli: true` ve haberler açıldıktan sonra `ceviri_son_hatalar.deepl: null`; `/api/news`'te `baslik_tr` dolu. DeepL hata kodları: 403 anahtar yanlış, 456 aylık kota doldu.
- ✅ DeepL canlıda çalışıyor (PR #19). Ama ilk çevirilerde Türkçe harfler bozuk geldi ("TedarikÃ§i"): istek gövdesi charset'siz JSON'du. Düzeltme (dal: `ceviri-harfler`): gövde `ensure_ascii=True` + `charset=utf-8`; `ceviri.bozuk_karakterleri_onar()` her çeviriye VE veritabanından okunan eski kayıtlara uygulanıyor (Neon'daki bozuk kayıtları silmeye gerek yok).
- Aynı dalda: Spaceflight News bazı başlıkları bozuk gönderiyor ("ProtÃ©gÃ©"); `news.bozuk_karakterleri_onar()` düzeltiyor.

### 6.2 GitHub cron gecikmesi
"Hatırlatma kontrolü" 15 dk'da bir çalışmalıydı, ilk gün sadece 1 kez kendiliğinden çalıştı. Birkaç gün izlenecek. Düzensizse: **cron-job.org** (ücretsiz) aynı adresi çağırır: `POST /api/gorevler/hatirlatmalar` + başlık `X-Yonetici-Anahtari`.

### 6.3 Küçük temizlikler
- ✅ README güncellendi (dal: `readme`): bütün bölümler, canlı link, kurulum/test komutları, yol haritası.
- ✅ Birleşmiş eski dallar silindi (26 Kasım'da sadece `main` var). Eski not: `testler`, `yayin`, `eposta-api`, `gorunum`, `ceviri-duzeltme`, `gorunum-ceviri`, `ceviri-teshis`, `bu-gece`, `iss-canli`, `iss-yedek-kaynak`, `iss-gor`, `asteroitler`, `pwa`
  ```
  git branch -d testler yayin eposta-api gorunum ceviri-duzeltme gorunum-ceviri ceviri-teshis bu-gece iss-canli iss-yedek-kaynak iss-gor asteroitler pwa
  git push origin --delete testler yayin eposta-api gorunum ceviri-duzeltme gorunum-ceviri ceviri-teshis bu-gece iss-canli iss-yedek-kaynak iss-gor asteroitler pwa
  ```
- CSS/JS'te büyük değişiklik yapınca tüm `.html` dosyalarındaki `?v=13` → `?v=14` yapılmalı (test_menu.py hepsinin aynı olduğunu kontrol ediyor).
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
8. ~~**Gezegenlerde Ağırlığın**~~ ✅ (dal: `agirlik`): `agirlik.html/js`, sadece frontend. 11 gök cismi kartı: ağırlık, zıplama (Dünya'da 50 cm varsayımı), 1 m'den düşüş süresi, ilginç bilgi. Girilen kg localStorage'da.
9. ~~**Gök Haritası**~~ ✅ (dal: `gokharitasi`): yıldızlar d3-celestial (BSD) verisinden `frontend/veri/gok.json` (kadir ≤ 5,5; 2.851 yıldız, 88 takımyıldız, Türkçe adlar). Yıldız konumu tarayıcıda (stereografik izdüşüm, Doğu solda); Güneş/Ay/gezegenler `GET /api/gok-haritasi?enlem&boylam&zaman` (J2000 ra/dec, 10 dk'ya yuvarlanır). Formülün Python kopyası test_gok_haritasi.py'de astronomy-engine ile karşılaştırılıyor. Eski not: Bu gecenin yıldız/takımyıldız haritası (şehre göre).

Önerilip seçilmeyenler: Uzay Havası (NOAA Kp), Favorilerim, Uzay Bilgi Yarışması, Ötegezegen Keşifleri.

### Yeni bölümler: 2. tur (26 Kasım 2026'da seçildi, bu sırayla)

10. ~~**Doğum Günü Fotoğrafın**~~ ✅ (PR #21): `dogumgunu.html/js`. Doğum tarihi → o günün APOD'u (`/api/apod?tarih=`). NASA'nın WordPress arşivinde 16 Haziran 1995'ten bugüne her gün var (kontrol edildi). 1995 öncesi doğanlar için APOD başladıktan sonraki ilk doğum günü; ‹ › ile yıllar arasında gezinme; 29 Şubat → artık olmayan yılda 28 Şubat. Backend: `nasa.APOD_BASLANGIC`, daha önceki tarih NASA'ya sorulmadan 404. APOD kartının HTML'i `app.js`'ten `ortak.js`'e taşındı (`apodHtml()`, `tarihYaz()`); ana sayfa da onu kullanıyor. Doğum tarihi sadece localStorage'da. Yeni ikon: `pasta`.
11. **Gezegenlerde Yaşın** (dal: `yas`, yapılıyor): `yas.html/js`, sadece frontend, Ağırlık sayfasının kart stilini (`.cisim`) kullanıyor. Merkür'den Plüton'a 9 kart: yaş, yılın tamamlanan kısmı (çubuk), sıradaki gezegen doğum günü (uzaksa yıl + o gün Dünya'daki yaş). Dünya için takvimdeki doğum günü kullanılıyor (29 Şubat → 28 Şubat). Hesap tarihleri tam sayı gün numarasına çevirerek yapılıyor (saat dilimi hatası olmasın). Doğum tarihi Doğum Günü sayfasıyla ortak: `ortak.js` → `dogumTarihiOku()/dogumTarihiKaydet()`. Yeni ikon: `kumsaati`.
12. **Bugün Uzay Tarihinde** (dal: `uzay-tarihi`): kendi veri dosyamız (facts.json gibi; her gün için bir uzay tarihi olayı) + küçük API, ana sayfada kart.
13. **Uzay Sondaları Nerede** (dal: `sondalar`): Voyager 1-2, New Horizons, Parker vb. Dünya'dan uzaklık, ışığın ulaşma süresi, canlı artan sayaç. Backend hesaplaması + yeni sayfa.

✅ **GRUPLU MENÜ** (dal: `menu`): Günlük · **Keşfet ▾** (Bu Gece, ISS, Dünya, Asteroitler) · Uzay Takvimi. `<details class="menu-grup">` ile yapıldı (JS'siz de açılır); ortak.js `menuGruplariniKur()` dışarı tıklayınca/Esc ile kapatır. Ağırlık da gruba eklendi. Gök Haritası da gruba eklendi. Yeni sayfa **bütün sayfalarda** `.menu-acilir` içine eklenmeli; grupta bir sayfa aktifse `<summary class="aktif">` olmalı. `tests/test_menu.py` unutulan sayfayı yakalar.

Tasarım dili: koyu uzay teması, Michroma başlıklar / Exo 2 metin, **emoji yok**. İkonlar `frontend/ortak.js`'teki `IKONLAR` setinden (gerekirse yeni SVG eklenir). Renkler `style.css` başındaki CSS değişkenlerinde.
