@echo off
REM Bu betiği kendi Windows bilgisayarında, bu klasörün icinde calistir.
REM Once bir kere: pip install -r requirements.txt
REM             ve: pip install pyinstaller

echo Bagimliliklar kuruluyor...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Exe derleniyor...
pyinstaller --onefile --console --name MexcBot ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  main_exe.py

echo.
echo Bitti. Exe dosyasi "dist\MexcBot.exe" icinde.
echo Teslim ederken YANINA su dosyalari da koy:
echo   - .env  (MEXC API bilgileri ile doldurulmus)
echo   - license.lic  (generate_license.py ile uretilmis)
pause
