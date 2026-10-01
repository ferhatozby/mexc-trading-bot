"""
Basit, çevrimdışı çalışan lisans sistemi.
Bir lisans dizesi şu formattadır:  <base64_payload>.<hmac_imza>
Payload içinde müşteri adı ve bitiş tarihi var; imza SECRET ile üretiliyor,
bu yüzden SECRET'ı bilmeyen biri geçerli bir lisans üretemez.

ÖNEMLİ: Bu, sıradan kullanıcıları/müşterileri caydıracak düzeydedir; motive
bir kişi .exe'yi tersine mühendislikle SECRET'ı çıkarabilir. Askeri düzey bir
DRM değildir, ama bu ölçekte bir iş için yeterli ve pratik bir çözümdür.
"""
import base64
import hashlib
import hmac
import json
import datetime

# ÖNEMLİ: Bu anahtarı kendine özel, kimseyle paylaşmadığın bir değerle değiştir.
# generate_license.py ve main_exe.py İKİSİNDE DE aynı SECRET olmalı.
SECRET = b"BURAYA-KENDI-GIZLI-ANAHTARINI-YAZ-12345"


def generate_license(client_name: str, expiry_date: str) -> str:
    """expiry_date formatı: 'YYYY-MM-DD'"""
    payload = {"client": client_name, "expiry": expiry_date}
    payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("ascii")
    sig = hmac.new(SECRET, payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_license(license_str: str):
    """Döner: (gecerli_mi: bool, mesaj_veya_bilgi)"""
    try:
        payload_b64, sig = license_str.strip().split(".")
    except ValueError:
        return False, "Lisans formatı hatalı."

    expected_sig = hmac.new(SECRET, payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return False, "Lisans imzası geçersiz (sahte veya bozulmuş dosya)."

    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
        expiry = datetime.datetime.strptime(payload["expiry"], "%Y-%m-%d")
    except Exception as e:
        return False, f"Lisans içeriği okunamadı: {e}"

    if datetime.datetime.now() > expiry:
        return False, f"Lisans süresi doldu ({payload['expiry']})."

    return True, payload
