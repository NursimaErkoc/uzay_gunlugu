"""
E-posta gönderme: Gmail'in SMTP sunucusu üzerinden.

SMTP (Simple Mail Transfer Protocol) = e-posta göndermenin standart yolu.
Gmail normal şifrenle girişe izin vermez; Google hesabından alınan
16 haneli bir "uygulama şifresi" gerekir (.env dosyasında GMAIL_UYGULAMA_SIFRESI).
"""
import smtplib
import ssl
from email.message import EmailMessage

from app.config import GMAIL_ADRESI, GMAIL_UYGULAMA_SIFRESI, HATIRLATMA_ALICISI

SMTP_SUNUCUSU = "smtp.gmail.com"
SMTP_PORTU = 465   # SSL ile şifreli bağlantı


class EpostaHatasi(Exception):
    """E-posta gönderilemediğinde fırlatılır."""


def ayarli_mi() -> bool:
    return bool(GMAIL_ADRESI and GMAIL_UYGULAMA_SIFRESI and HATIRLATMA_ALICISI)


def alici_gizli() -> str | None:
    """Alıcı adresini sitede gösterirken gizle: ornek@gmail.com -> or***@gmail.com"""
    if not HATIRLATMA_ALICISI or "@" not in HATIRLATMA_ALICISI:
        return None
    ad, alan = HATIRLATMA_ALICISI.split("@", 1)
    return f"{ad[:2]}***@{alan}"


def gonder(konu: str, duz_metin: str, html: str) -> None:
    """
    E-postayı gönderir. Hem düz metin hem HTML sürümü ekleriz:
    HTML gösteremeyen e-posta programları düz metni gösterir.
    NOT: Bu fonksiyon "senkron" (beklerken her şeyi durdurur). Sunucuyu dondurmamak için
    async kodun içinden  await asyncio.to_thread(gonder, ...)  ile çağırıyoruz.
    """
    if not ayarli_mi():
        raise EpostaHatasi("E-posta ayarları yapılmamış: .env dosyasına GMAIL_ADRESI ve GMAIL_UYGULAMA_SIFRESI ekle.")

    mesaj = EmailMessage()
    mesaj["Subject"] = konu
    mesaj["From"] = f"Uzay Günlüğü <{GMAIL_ADRESI}>"
    mesaj["To"] = HATIRLATMA_ALICISI
    mesaj.set_content(duz_metin)
    mesaj.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP_SSL(SMTP_SUNUCUSU, SMTP_PORTU, context=ssl.create_default_context(), timeout=20) as smtp:
            smtp.login(GMAIL_ADRESI, GMAIL_UYGULAMA_SIFRESI)
            smtp.send_message(mesaj)
    except smtplib.SMTPAuthenticationError as hata:
        raise EpostaHatasi(
            "Gmail girişi reddedildi. GMAIL_ADRESI veya GMAIL_UYGULAMA_SIFRESI hatalı "
            "(normal Gmail şifren değil, 16 haneli uygulama şifresi olmalı)."
        ) from hata
    except (smtplib.SMTPException, OSError) as hata:
        raise EpostaHatasi(f"E-posta gönderilemedi: {hata}") from hata
