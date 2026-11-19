"""
Basit bir önbellek (cache).

Neden? Günün fotoğrafı gün içinde değişmez. Siteye 100 kişi girse bile
NASA'ya 100 kez sormak yerine 1 kez sorup cevabı bir süre hafızada tutarız.
Böylece site hızlanır ve API limitimiz dolmaz.
"""
import time

# Anahtar -> (son geçerlilik zamanı, değer)
_hafiza: dict[str, tuple[float, object]] = {}


def getir(anahtar: str):
    """Önbellekte geçerli bir değer varsa döndürür, yoksa None."""
    kayit = _hafiza.get(anahtar)
    if kayit is None:
        return None
    son_gecerlilik, deger = kayit
    if time.time() > son_gecerlilik:   # süresi dolmuş
        del _hafiza[anahtar]
        return None
    return deger


def kaydet(anahtar: str, deger, saniye: int) -> None:
    """Değeri verilen saniye boyunca önbellekte tutar."""
    _hafiza[anahtar] = (time.time() + saniye, deger)
