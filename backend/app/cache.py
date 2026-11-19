"""
Basit bir önbellek (cache).

Neden? Günün fotoğrafı gün içinde değişmez. Siteye 100 kişi girse bile
NASA'ya 100 kez sormak yerine 1 kez sorup cevabı bir süre hafızada tutarız.
Böylece site hızlanır ve API limitimiz dolmaz.

İki katman var:
- Hafıza (RAM): çok hızlı, ama sunucu yeniden başlayınca silinir.
- Disk (kalici=True): biraz daha yavaş, ama sunucu yeniden başlasa da durur.
  İstek sınırı sıkı olan API'ler (Launch Library: saatte 15) ve
  yavaş işlemler (çeviri) için diski de kullanıyoruz.
"""
import hashlib
import json
import time

from app.config import PROJE_KLASORU

DISK_KLASORU = PROJE_KLASORU / ".onbellek"   # .gitignore'da, GitHub'a gitmez

# Anahtar -> (son geçerlilik zamanı, değer)
_hafiza: dict[str, tuple[float, object]] = {}


def _dosya_yolu(anahtar: str):
    # Anahtar uzun/garip karakterli olabilir; dosya adı için kısa bir "parmak izi" (hash) üret
    parmak_izi = hashlib.sha1(anahtar.encode("utf-8")).hexdigest()
    return DISK_KLASORU / f"{parmak_izi}.json"


def getir(anahtar: str):
    """Önbellekte geçerli bir değer varsa döndürür, yoksa None."""
    kayit = _hafiza.get(anahtar)
    if kayit is None:
        kayit = _diskten_oku(anahtar)
        if kayit is None:
            return None
        _hafiza[anahtar] = kayit   # bir sonraki sefer hafızadan gelsin

    son_gecerlilik, deger = kayit
    if time.time() > son_gecerlilik:   # süresi dolmuş
        del _hafiza[anahtar]
        return None
    return deger


def kaydet(anahtar: str, deger, saniye: int, kalici: bool = False) -> None:
    """Değeri verilen saniye boyunca önbellekte tutar. kalici=True ise diske de yazar."""
    son_gecerlilik = time.time() + saniye
    _hafiza[anahtar] = (son_gecerlilik, deger)
    if kalici:
        try:
            DISK_KLASORU.mkdir(exist_ok=True)
            with open(_dosya_yolu(anahtar), "w", encoding="utf-8") as dosya:
                json.dump({"son": son_gecerlilik, "deger": deger}, dosya, ensure_ascii=False)
        except OSError:
            pass   # diske yazılamazsa sorun değil, hafızada var


def _diskten_oku(anahtar: str):
    try:
        with open(_dosya_yolu(anahtar), encoding="utf-8") as dosya:
            veri = json.load(dosya)
        return veri["son"], veri["deger"]
    except (OSError, ValueError, KeyError):
        return None
