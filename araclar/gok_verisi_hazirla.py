"""
Gök Haritası için yıldız verisini hazırlar -> frontend/veri/gok.json

Sadece veri güncellenmek istenirse bir kez çalıştırılır (site çalışırken gerekmez):
    python araclar/gok_verisi_hazirla.py

Kaynak: d3-celestial (Olaf Frohn), BSD 3-Clause lisansı - https://github.com/ofrohn/d3-celestial
Oradaki büyük dosyaları indirip sitenin ihtiyacı kadarını, küçük bir dosyaya yazıyoruz:
  - Çıplak gözle görülebilen yıldızlar (kadir <= 5,5; ~2.850 yıldız)
  - Parlak yıldızların adları
  - 88 takımyıldızın Türkçe adı, etiket yeri ve çizgileri
Koordinatlar: sağ açıklık (ra) ve dik açıklık (dec), derece cinsinden (J2000).
"""
import json
import pathlib

import httpx

ADRES = "https://raw.githubusercontent.com/ofrohn/d3-celestial/master/data/"
HEDEF = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "veri" / "gok.json"
EN_SONUK_KADIR = 5.5
AD_KADIR = 1.6   # bundan parlak yıldızların adı haritada yazılır

# Haritada yazılacak birkaç ünlü (ama 1,6'dan sönük) yıldız
EK_ADLAR = {"Polaris", "Algol", "Mizar", "Alkaid", "Dubhe", "Mintaka", "Alnitak", "Alnilam", "Bellatrix",
            "Hamal", "Alpheratz", "Denebola", "Rasalhague", "Alphard"}
HARIC = {"Toliman"}   # Alfa Centauri ile üst üste biniyor
# Bazı yıldızların bizdeki bilinen adları (geri kalanı uluslararası adıyla kalır)
YILDIZ_ADI = {"Polaris": "Kutup Yıldızı", "Rigil Kentaurus": "Alfa Centauri", "Arcturus": "Arktürüs",
              "Capella": "Kapella", "Pollux": "Polluks", "Castor": "Kastor"}
# Kaynaktaki Türkçe takımyıldız adlarından düzeltmek istediklerimiz
TAKIMYILDIZ_ADI = {"Cas": "Kassiopeia", "Peg": "Kanatlı At", "CrA": "Güney Tacı", "CrB": "Kuzey Tacı",
                   "Cru": "Güney Haçı", "PsA": "Güney Balığı", "Hyi": "Küçük Suyılanı", "Vol": "Uçan Balık",
                   "Sge": "Ok", "Vul": "Tilki", "Cae": "Oyma Kalemi", "Ant": "Hava Pompası",
                   "Nor": "Gönye", "Oct": "Oktant", "Sex": "Sekstant", "Tel": "Teleskop", "Pyx": "Pusula",
                   "Aps": "Cennet Kuşu", "Scl": "Heykeltıraş", "Ori": "Avcı (Orion)"}


def ra(boylam):
    """Kaynak sağ açıklığı -180..180 olarak veriyor; biz 0..360 kullanıyoruz."""
    return round(boylam % 360, 2)


def nokta(k):
    return [ra(k[0]), round(k[1], 2)]


def temiz(ad):
    """Kaynakta bazı adlarda tuhaf boşluk karakterleri var (ör. U+2005); normal boşluğa çevir."""
    return " ".join(ad.split())


def indir(ad):
    cevap = httpx.get(ADRES + ad, timeout=60, follow_redirects=True)
    cevap.raise_for_status()
    return cevap.json()


def main():
    yildizlar = indir("stars.6.json")["features"]
    adlar = indir("starnames.json")
    cizgiler = indir("constellations.lines.json")["features"]
    takimyildizlar = indir("constellations.json")["features"]

    liste, adli = [], []
    for y in sorted(yildizlar, key=lambda y: y["properties"]["mag"]):
        kadir = y["properties"]["mag"]
        if kadir > EN_SONUK_KADIR:
            continue
        try:
            renk = round(float(y["properties"]["bv"]), 2)
        except (TypeError, ValueError):
            renk = 0.6
        liste.append([*nokta(y["geometry"]["coordinates"]), kadir, renk])
        bilgi = adlar.get(str(y["id"]), {})
        ad = bilgi.get("name")
        if ad and ad not in HARIC and (kadir < AD_KADIR or ad in EK_ADLAR):
            adli.append({"ad": temiz(YILDIZ_ADI.get(ad, ad)), "ra": liste[-1][0], "dec": liste[-1][1],
                         "kadir": kadir, "tk": bilgi.get("c")})

    cizgi = {}
    for t in cizgiler:   # Yılan (Ser) iki parça: aynı kısaltmada birleştiriyoruz
        cizgi.setdefault(t["id"], []).extend([[nokta(k) for k in parca] for parca in t["geometry"]["coordinates"]])

    tk = []
    for t in takimyildizlar:
        o = t["properties"]
        tk.append({"k": t["id"], "ad": temiz(TAKIMYILDIZ_ADI.get(t["id"], o.get("tr") or o["name"])),
                   "ra": ra(t["geometry"]["coordinates"][0]), "dec": round(t["geometry"]["coordinates"][1], 2),
                   "onem": int(o.get("rank", 3)), "cizgiler": cizgi.pop(t["id"], [])})   # Yılan iki etiketli; çizgiler bir kez

    veri = {
        "kaynak": "d3-celestial, (c) 2015 Olaf Frohn, BSD 3-Clause - https://github.com/ofrohn/d3-celestial",
        "aciklama": "yildizlar: [sag acik., dik acik., kadir, B-V renk]; koordinatlar J2000, derece",
        "yildizlar": liste, "adlar": adli, "takimyildizlar": tk,
    }
    HEDEF.parent.mkdir(exist_ok=True)
    HEDEF.write_text(json.dumps(veri, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(liste)} yıldız, {len(adli)} ad, {len(tk)} takımyıldız -> {HEDEF} ({HEDEF.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
