"""
Bu betiği SEN çalıştırırsın (müşteri değil), müşteriye özel bir license.lic
dosyası üretmek için. Üretilen dosyayı .exe ile aynı klasöre koyup teslim et.

Kullanım:
    python3 generate_license.py
"""
from license_check import generate_license

if __name__ == "__main__":
    client = input("Müşteri adı/etiketi (ör. 'Yunus Eviz'): ").strip()
    expiry = input("Bitiş tarihi (YYYY-MM-DD, ör. 2027-09-26): ").strip()

    lic = generate_license(client, expiry)
    with open("license.lic", "w") as f:
        f.write(lic)

    print("\nOluşturuldu: license.lic")
    print("Bu dosyayı .exe ile AYNI klasöre koy ve müşteriye öyle teslim et.")
    print(f"Müşteri: {client} | Bitiş: {expiry}")
