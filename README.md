# 🚀 Uzay Günlüğü

Her gün evrene yeni bir pencere açan, Türkçe bir uzay sitesi. Telefona uygulama olarak da kurulabilir.

**Canlı site:** https://uzay-gunlugu.onrender.com

## Bölümler
| Sayfa | Ne gösteriyor? |
|---|---|
| **Günlük** | NASA'nın günün fotoğrafı, günün uzay bilgisi, bugün uzay tarihinde ne oldu, güncel uzay haberleri (Türkçe çeviriyle) |
| **Bu Gece** | Seçilen şehirde Ay'ın evresi, gün batımı/doğumu, bu gece görülebilen gezegenler |
| **ISS** | Uluslararası Uzay İstasyonu'nun canlı konumu, şehrinin üstünden ne zaman geçeceği, uzaydaki astronotlar |
| **Dünya** | NASA EPIC uydusunun 1,5 milyon km uzaktan çektiği fotoğraflarla Dünya'nın bir günlük dönüşü |
| **Asteroitler** | Bu hafta Dünya'nın yakınından geçen asteroitler, gündelik karşılaştırmalarla |
| **Sondalar** | Voyager, New Horizons, Parker gibi uzay araçlarının şu anki uzaklığı (canlı sayaç) ve onlara mesajın kaç saatte ulaştığı |
| **Ağırlık** | Gezegenlerde ve Ay'da ne kadar ağır olurdun, ne kadar yükseğe zıplardın |
| **Yaşın** | Her gezegende kaç yaşında olurdun, bir sonraki gezegen doğum günün ne zaman |
| **Gök Haritası** | Seçilen şehir ve saatte gökyüzü: yıldızlar, Türkçe adlı takımyıldızlar, Ay ve gezegenler |
| **Doğum Günü** | Doğduğun gün (ve her yaş gününde) NASA'nın yayınladığı uzay fotoğrafı |
| **Uzay Takvimi** | Bu ayın gökyüzü olayları ve roket fırlatmaları; site sahibi için e-posta hatırlatması |

## Teknolojiler
- **Backend:** Python + FastAPI
- **Frontend:** HTML, CSS, JavaScript (kütüphanesiz; harita için Leaflet), PWA (çevrimdışı çalışma)
- **Veritabanı:** SQLite (yerelde), PostgreSQL / Neon (canlıda)
- **Hesaplamalar:** Astronomy Engine (Ay, Güneş, gezegenler), sgp4 (ISS yörüngesi)
- **Veri kaynakları:** NASA APOD, NASA NeoWs, NASA EPIC, Spaceflight News API, Launch Library 2,
  CelesTrak (ISS yörünge bilgisi), d3-celestial (yıldız kataloğu)
- **Yayın:** Render (site), GitHub Actions (testler ve zamanlanmış hatırlatma kontrolü)

## Kurulum
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
python -m pip install -r requirements.txt
copy .env.example .env        # sonra .env içine kendi anahtarlarını yaz
```

Çalıştırmak için:
```bash
python -m uvicorn app.main:app --reload --app-dir backend
```
Sonra tarayıcıda http://127.0.0.1:8000 adresini aç. API dokümantasyonu: http://127.0.0.1:8000/docs

Testler:
```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Yol haritası
- [x] Adım 0: Hazırlık ve Git/GitHub
- [x] Adım 1: İlk API çağrısı
- [x] Adım 2: Kendi API'miz (FastAPI)
- [x] Adım 3: Frontend
- [x] Adım 4: Günün bilgisi ve haberler
- [x] Adım 5: Aylık uzay olayları
- [x] Adım 6: E-posta hatırlatmaları
- [x] Adım 7: Testler ve GitHub Actions
- [x] Adım 8: İnternete yayınlama
- [x] Adım 9: Yeni bölümler: Bu Gece, ISS, Asteroitler, Dünya, Ağırlık, Gök Haritası
- [x] Adım 10: Telefona kurulabilen uygulama (PWA) ve gruplu menü
- [x] Adım 11: Doğum Günü Fotoğrafın, Gezegenlerde Yaşın, Bugün Uzay Tarihinde, Uzay Sondaları

## Lisanslar ve teşekkür
Yıldız ve takımyıldız verisi [d3-celestial](https://github.com/ofrohn/d3-celestial) projesinden alınmıştır
(© 2015 Olaf Frohn, BSD 3-Clause lisansı). Fotoğraflar ve veriler NASA'ya aittir.
