"""
.exe için giriş noktası. build.bat bunu PyInstaller ile derler.
Sırasıyla: lisansı doğrular -> zamanlayıcıyı başlatır -> web sunucusunu
başlatır -> tarayıcıda paneli otomatik açar.
"""
import os
import sys
import threading
import time
import webbrowser

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def check_license():
    lic_path = os.path.join(BASE_DIR, "license.lic")
    if not os.path.exists(lic_path):
        print("HATA: 'license.lic' dosyası bulunamadı.")
        print("Bu dosya .exe ile aynı klasörde olmalı.")
        input("\nKapatmak için Enter'a basın...")
        sys.exit(1)

    with open(lic_path, "r", encoding="utf-8") as f:
        lic_str = f.read()

    from license_check import verify_license
    ok, info = verify_license(lic_str)
    if not ok:
        print(f"HATA: Lisans geçersiz -> {info}")
        input("\nKapatmak için Enter'a basın...")
        sys.exit(1)

    print(f"✓ Lisans doğrulandı — Müşteri: {info['client']} | Bitiş: {info['expiry']}")


def main():
    check_license()

    import scheduler
    scheduler.start()

    from app import app
    port = int(os.environ.get("PORT", "8000"))

    def open_browser():
        time.sleep(1.2)
        webbrowser.open(f"http://127.0.0.1:{port}")

    threading.Thread(target=open_browser, daemon=True).start()

    print(f"\nPanel başlatılıyor: http://127.0.0.1:{port}")
    print("Bu pencereyi kapatmak botu durdurur. Küçültüp açık bırakabilirsiniz.\n")

    from waitress import serve
    serve(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
