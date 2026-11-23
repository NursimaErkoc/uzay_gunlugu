# 🚀 Uzay Günlüğü

NASA'nın günün fotoğrafını, günün uzay bilgisini, güncel uzay haberlerini ve bu ayın uzay olaylarını gösteren, olaylar için e-posta hatırlatması gönderebilen bir web sitesi.



## Teknolojiler
- **Backend:** Python + FastAPI
- **Frontend:** HTML, CSS, JavaScript
- **Veritabanı:** SQLite (Python'un yerleşik sqlite3 modülü)
- **Veri kaynakları:** NASA APOD (science.nasa.gov), Spaceflight News API, Launch Library 2, Astronomy Engine

## Kurulum
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # sonra .env içine kendi anahtarlarını yaz
```

## Yol haritası
- [x] Adım 0: Hazırlık ve Git/GitHub
- [x] Adım 1: İlk API çağrısı
- [x] Adım 2: Kendi API'miz (FastAPI)
- [x] Adım 3: Frontend
- [x] Adım 4: Günün bilgisi ve haberler
- [x] Adım 5: Aylık uzay olayları
- [x] Adım 6: E-posta hatırlatmaları
- [ ] Adım 7: Testler ve GitHub Actions
- [ ] Adım 8: İnternete yayınlama
