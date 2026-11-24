"""
E-posta gönderme. İki yol var; hangisinin kullanılacağına .env / Render ayarları karar verir:

1) Resend API (RESEND_API_KEY tanımlıysa) -> İNTERNETTE (Render) bu kullanılır.
   Render'ın ücretsiz planı e-posta portlarını (SMTP: 25/465/587) engelliyor.
   Resend'e ise normal bir HTTPS isteğiyle (NASA'ya istek atar gibi) e-posta gönderiyoruz; bu engellenmiyor.
   Kendi alan adın (domain) yoksa Resend sadece hesabı açtığın adrese gönderebilir: bizim için yeterli.

2) Gmail SMTP (GMAIL_ADRESI + GMAIL_UYGULAMA_SIFRESI) -> BİLGİSAYARINDA bu kullanılır.
   SMTP (Simple Mail Transfer Protocol) = e-posta göndermenin klasik yolu.
"""
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from app.config import GMAIL_ADRESI, GMAIL_UYGULAMA_SIFRESI, HATIRLATMA_ALICISI, RESEND_API_KEY

SMTP_SUNUCUSU = "smtp.gmail.com"
SMTP_PORTU = 465   # SSL ile şifreli bağlantı

RESEND_URL = "https://api.resend.com/emails"
RESEND_GONDEREN = "Uzay Günlüğü <onboarding@resend.dev>"   # alan adı olmadan kullanılabilen gönderen


class EpostaHatasi(Exception):
    """E-posta gönderilemediğinde fırlatılır."""


def yontem() -> str | None:
    """Hangi yolla gönderilecek? 'resend', 'smtp' veya None (ayarlanmamış)."""
    if not HATIRLATMA_ALICISI:
        return None
    if RESEND_API_KEY:
        return "resend"
    if GMAIL_ADRESI and GMAIL_UYGULAMA_SIFRESI:
        return "smtp"
    return None


def ayarli_mi() -> bool:
    return yontem() is not None


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
    secilen = yontem()
    if secilen == "resend":
        _resend_ile_gonder(konu, duz_metin, html)
    elif secilen == "smtp":
        _smtp_ile_gonder(konu, duz_metin, html)
    else:
        raise EpostaHatasi(
            "E-posta ayarları yapılmamış: RESEND_API_KEY ya da GMAIL_ADRESI + GMAIL_UYGULAMA_SIFRESI gerekli."
        )


def _resend_ile_gonder(konu: str, duz_metin: str, html: str) -> None:
    try:
        cevap = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},   # API anahtarı başlıkta gider
            json={
                "from": RESEND_GONDEREN,
                "to": [HATIRLATMA_ALICISI],
                "subject": konu,
                "text": duz_metin,
                "html": html,
            },
            timeout=20,
        )
    except httpx.HTTPError as hata:
        raise EpostaHatasi(f"Resend'e ulaşılamadı: {type(hata).__name__}") from hata

    if cevap.status_code in (401, 403):
        # En sık sebepler: anahtar yanlış, ya da alıcı Resend hesabının adresi değil
        raise EpostaHatasi(
            f"Resend isteği reddetti ({cevap.status_code}): {_resend_mesaji(cevap)}. "
            "RESEND_API_KEY doğru mu, ve Resend hesabını hatırlatmaların gideceği adresle mi açtın?"
        )
    if cevap.status_code >= 400:
        raise EpostaHatasi(f"Resend hata verdi ({cevap.status_code}): {_resend_mesaji(cevap)}")


def _resend_mesaji(cevap: httpx.Response) -> str:
    try:
        return cevap.json().get("message", cevap.text[:200])
    except ValueError:
        return cevap.text[:200]


def _smtp_ile_gonder(konu: str, duz_metin: str, html: str) -> None:
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
    except OSError as hata:
        if getattr(hata, "errno", None) == 101:   # "Network is unreachable"
            raise EpostaHatasi(
                "E-posta sunucusuna ulaşılamıyor. Sunucu SMTP portlarını engelliyor olabilir "
                "(Render'ın ücretsiz planı engeller). RESEND_API_KEY tanımlayarak Resend'i kullan."
            ) from hata
        raise EpostaHatasi(f"E-posta gönderilemedi: {hata}") from hata
    except smtplib.SMTPException as hata:
        raise EpostaHatasi(f"E-posta gönderilemedi: {hata}") from hata
