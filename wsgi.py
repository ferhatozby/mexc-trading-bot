"""Gunicorn ile çalıştırmak için: gunicorn -w 1 -b 0.0.0.0:8000 wsgi:app
(app.py'yi doğrudan çalıştırmak yerine bunu kullanın, çünkü gunicorn
'if __name__ == \"__main__\"' bloğunu atlar ve zamanlayıcı başlamaz.)"""
from app import app
import scheduler

scheduler.start()
