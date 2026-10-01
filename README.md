# MEXC Otomasyon Botu

Belirlediğiniz parite, kaldıraç, teminat tutarı ve zaman aralığına göre MEXC Futures
üzerinde otomatik long/short pozisyon açıp kapatan basit bir panel + bot.

## ⚠️ Önemli güvenlik notu

- MEXC hesabınızda API anahtarı oluştururken **sadece "Futures Trade" iznini açın**.
- **"Withdraw" (çekme) iznini kesinlikle kapalı bırakın.** Bu, anahtar çalınsa bile
  paranın hesaptan çıkamayacağı anlamına gelir.
- Botu önce **küçük bir teminat tutarıyla** (ör. 5-10 USDT) test edin, doğru çalıştığını
  gördükten sonra tutarı artırın.
- Bu bot yalnızca girdiğiniz parametreleri uygular; piyasa hareketinden doğacak
  kâr/zarardan bot değil, işlem kararını veren kişi sorumludur.

## Kurulum (VPS üzerinde, Ubuntu 22.04/24.04 varsayımıyla)

```bash
# 1. Sunucuya bağlan, Python ve gerekli paketleri kur
sudo apt update && sudo apt install -y python3-pip python3-venv

# 2. Proje dosyalarını sunucuya yükle (scp, git, vs.) ve klasöre gir
cd mexc-bot

# 3. Sanal ortam oluştur ve bağımlılıkları kur
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. .env dosyasını oluştur
cp .env.example .env
nano .env   # API anahtarlarını ve FLASK_SECRET değerini gir

# 5. Deneme çalıştırması
python3 app.py
# Tarayıcıdan http://SUNUCU_IP:8000 adresine girip paneli test et
```

## 7/24 çalışması için systemd servisi

`/etc/systemd/system/mexc-bot.service` dosyasını oluştur:

```ini
[Unit]
Description=MEXC Otomasyon Botu
After=network.target

[Service]
WorkingDirectory=/home/KULLANICI/mexc-bot
Environment="PATH=/home/KULLANICI/mexc-bot/venv/bin"
ExecStart=/home/KULLANICI/mexc-bot/venv/bin/gunicorn -w 1 -b 0.0.0.0:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Not: Gunicorn ile çalıştırırken `app.py` içindeki `if __name__ == "__main__"` bloğu
devreye girmez, bu yüzden zamanlayıcıyı ayrıca başlatan küçük bir `wsgi.py` kullanmak
gerekir (bkz. `wsgi.py` dosyası) — gunicorn komutunu `wsgi:app` olarak değiştirin.

Sonra:
```bash
sudo systemctl daemon-reload
sudo systemctl enable mexc-bot
sudo systemctl start mexc-bot
sudo systemctl status mexc-bot
```

Paneli güvenli tutmak için önüne bir reverse proxy (nginx) + şifre koruması veya
en azından sunucu güvenlik duvarında panel portunu kendi IP'nizle sınırlamanızı öneririm.

## Panel kullanımı

1. Parite (ör. `BTCUSDT`), yön (long/short), kaldıraç ve teminat (USDT) gir.
2. Açılış/kapanış saatini seç.
3. Tekrar: "Her gün", belirli haftanın günleri, veya tek seferlik belirli tarih.
4. "İşi Kaydet" — iş listede görünür ve zamanlayıcı otomatik devreye girer.
5. "İşlem Kayıtları" bölümünden her açma/kapama denemesinin başarılı olup olmadığını
   görebilirsin (hata varsa detayında borsanın döndürdüğü mesaj yazar).

## "Açılış saati = Kapanış saati" ayarı (günlük pozisyon devri)

Bir işte açılış ve kapanış saatini **aynı** girersen (ör. ikisi de 03:00), bot bunu
"her gün aynı saatte: önceki pozisyonu kapat, hemen ardından yeni pozisyonu aç"
olarak anlar — bu ikisi TEK bir adımda, sırayla çalışır (önce kapatma, o başarılı
olursa yeni açma). Böylece "aynı anda iki ayrı tetikleyici" riski oluşmaz.

Bu, özellikle "Otomatik yön" ile birlikte kullanışlıdır: her gün 03:00'da bir
önceki pozisyon kapanır, yeni günün mum rengine göre yeni pozisyon açılır — yani
sürekli dönen (rotating) bir pozisyon elde edilir.

Açılış ve kapanış saatini **farklı** girersen (ör. 09:00 aç, 12:00 kapat), bunlar
eskisi gibi iki ayrı, birbirinden bağımsız zamanlanmış olay olarak çalışır.

## Otomatik yön (önceki mumun rengine göre)

İş oluştururken "Yön" alanında **"Otomatik"** seçilirse, bot her açılışta:
- Borsadan bir önceki **tam kapanmış günlük mumu** çeker,
- Kapanış < Açılış ise (kırmızı/düşüş mum) → **short** açar,
- Kapanış > Açılış ise (yeşil/yükseliş mum) → **long** açar.

**Önemli nüans:** Burada kullanılan "günlük mum", borsanın kendi gün sınırına göredir
(genelde 00:00 UTC), müşterinin belirlediği açılış saatine (ör. 03:00) göre değil.
Eğer müşteri "tam olarak benim açılış saatimden bir önceki 24 saatlik mum" istiyorsa,
bu ayrı bir hesaplama gerektirir — şu anki haliyle borsanın standart günlük mumunu
kullanıyoruz, bu genelde istenen sonuca çok yakın olur ama birebir aynı olmayabilir.

Kaldıraç, teminat ve parite her zaman elle girilir ve değiştirilmediği sürece sabit
kalır; sadece yön otomatik hesaplanır. Panelde her iş satırında o gün hangi yönde
açıldığı ("bugün: Long/Short") görünür.

## Panel şifre koruması

`.env` dosyasındaki `PANEL_PASSWORD` alanına bir şifre yaz. Panel açılınca önce
şifre ekranı gelir; doğru şifre girilmeden hiçbir iş görüntülenemez/oluşturulamaz.
`PANEL_PASSWORD` boş bırakılırsa koruma devre dışı kalır — VPS'e koyarken
mutlaka doldur.

## Windows .exe olarak paketleme (müşteriye program gibi teslim etmek için)

Bu yöntemle web linki değil, müşterinin çift tıklayıp açacağı bir program verirsin.
**Derleme işlemi kendi Windows bilgisayarında yapılmalı** (bu proje Linux üzerinde
hazırlandığı için buradan doğrudan .exe üretilemez).

### 1. Lisans anahtarını değiştir (tek seferlik, ilk kurulumda)

`license_check.py` içindeki şu satırı bul:
```python
SECRET = b"BURAYA-KENDI-GIZLI-ANAHTARINI-YAZ-12345"
```
Bunu kimseyle paylaşmadığın, kendine özel uzun bir metinle değiştir. Bu adımı
atlarsan herkes aynı anahtarla sahte lisans üretebilir.

### 2. Müşteriye özel bir lisans dosyası üret

```bash
python3 generate_license.py
```
Müşteri adını ve bitiş tarihini (ör. "2027-09-26") gir. Bu, `license.lic`
adında bir dosya oluşturur.

### 3. Windows'ta exe'yi derle

Windows bilgisayarında, bu klasörün içinde:
```
build.bat
```
çift tıkla veya çalıştır. Birkaç dakika sürer. Bittiğinde `dist\MexcBot.exe`
oluşur.

### 4. Teslimat paketi

Müşteriye şu 3 dosyayı **aynı klasörde** ver:
- `MexcBot.exe`
- `.env` (MEXC API key/secret'ı doldurulmuş olarak — bkz. `.env.example`)
- `license.lic` (2. adımda ürettiğin)

Müşteri `MexcBot.exe`'ye çift tıklayınca: lisansı kontrol eder, sunucuyu
başlatır ve tarayıcıda paneli otomatik açar. Pencereyi kapatırsa bot durur.

### Lisans hakkında dürüst olmak gerekirse

Bu, kararlı bir kullanıcıyı/tekrar satışı caydıran pratik bir kilit — banka
seviyesinde bir kopya koruması değil. Motive biri exe'yi tersine mühendislikle
inceleyip SECRET'ı bulabilir. Bu ölçekteki bir iş için yeterli, ama "hiçbir
şekilde kırılamaz" diye satma.

## Bilinen sınırlar / geliştirilebilecek noktalar

- Tek bir MEXC hesabı/API anahtarı ile çalışır (çoklu müşteri için ayrı kurulum gerekir).
- Panelde şu an giriş/şifre koruması yok — reverse proxy ile eklenmesi önerilir.
- Ağ kopması sırasında planlanan bir açma/kapama kaçırılırsa, iş "logs" tablosunda
  hata olarak görünür ama otomatik yeniden deneme yapılmaz (istenirse eklenebilir).
