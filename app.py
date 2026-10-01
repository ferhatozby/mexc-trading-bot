import logging
import os
import sys
from functools import wraps
from dotenv import load_dotenv

# .exe olarak paketlendiğinde .env exe'nin yanında aranmalı, PyInstaller'ın
# geçici açılış klasöründe değil.
if getattr(sys, "frozen", False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(_BASE_DIR, ".env"))

from flask import Flask, render_template, request, redirect, url_for, flash, session

import db
import scheduler
import mexc_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def resource_path(relative):
    """templates/ ve static/ gibi paketlenmiş dosyaları hem normal çalıştırmada
    hem de PyInstaller ile derlenmiş .exe içinde doğru bulur."""
    base = getattr(sys, "_MEIPASS", _BASE_DIR)
    return os.path.join(base, relative)


app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static"),
)
app.secret_key = os.environ.get("FLASK_SECRET", "degistir-bu-anahtari")

PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD", "")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if PANEL_PASSWORD and not session.get("authed"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if not PANEL_PASSWORD:
        # .env'de şifre tanımlanmamışsa koruma devre dışıdır (uyarı loglanır).
        session["authed"] = True
        return redirect(url_for("index"))

    if request.method == "POST":
        if request.form.get("password") == PANEL_PASSWORD:
            session["authed"] = True
            session.permanent = True
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        flash("Şifre hatalı.")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    jobs = db.list_jobs()
    logs = db.recent_logs(30)
    return render_template(
        "index.html", jobs=jobs, logs=logs, timeframes=mexc_client.SUPPORTED_TIMEFRAMES
    )


@app.route("/test-live", methods=["POST"])
@login_required
def test_live():
    """Gerçek işlem AÇMAZ. Sadece MEXC'ten herkese açık (API key gerektirmeyen)
    canlı mum verisini çekip, o an hangi yönün seçileceğini gösterir."""
    symbol = request.form.get("test_symbol", "").strip().upper()
    timeframe = request.form.get("test_timeframe", "1d")
    try:
        exchange = mexc_client.get_public_exchange()
        info = mexc_client.get_candle_info(exchange, symbol, timeframe)
        yon = "LONG (yeşil mum)" if info["side"] == "long" else "SHORT (kırmızı mum)"
        flash(
            f"[CANLI TEST] {symbol} [{timeframe}] — açılış: {info['open']} · "
            f"kapanış: {info['close']} → {yon}"
        )
    except Exception as e:
        flash(f"[CANLI TEST HATASI] {e}")
    return redirect(url_for("index"))


@app.route("/jobs", methods=["POST"])
@login_required
def create_job():
    symbol = request.form["symbol"].strip().upper()
    side = request.form["side"]
    leverage = int(request.form["leverage"])
    margin_usdt = float(request.form["margin_usdt"])
    start_time = request.form["start_time"]
    end_time = request.form["end_time"]
    mode = request.form["mode"]  # 'daily' | 'once' | 'custom_days'
    candle_timeframe = request.form.get("candle_timeframe", "1d")

    if mode == "daily":
        days = "daily"
    elif mode == "once":
        days = f"once:{request.form['once_date']}"
    else:
        selected = request.form.getlist("weekday")
        days = ",".join(selected) if selected else "daily"

    if leverage < 1 or leverage > 125:
        flash("Kaldıraç 1-125 arasında olmalı.")
        return redirect(url_for("index"))
    if margin_usdt <= 0:
        flash("Teminat miktarı 0'dan büyük olmalı.")
        return redirect(url_for("index"))

    job_id = db.add_job(symbol, side, leverage, margin_usdt, start_time, end_time, days, candle_timeframe)
    job = db.get_job(job_id)
    scheduler.schedule_job(job)
    flash(f"İş #{job_id} oluşturuldu ve zamanlandı.")
    return redirect(url_for("index"))


@app.route("/jobs/<int:job_id>/toggle", methods=["POST"])
@login_required
def toggle_job(job_id):
    job = db.get_job(job_id)
    if job:
        new_state = not bool(job["active"])
        db.set_job_active(job_id, new_state)
        if new_state:
            scheduler.schedule_job(db.get_job(job_id))
        else:
            scheduler.unschedule_job(job_id)
        flash(f"İş #{job_id} {'aktif' if new_state else 'pasif'} edildi.")
    return redirect(url_for("index"))


@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
def remove_job(job_id):
    scheduler.unschedule_job(job_id)
    db.delete_job(job_id)
    flash(f"İş #{job_id} silindi.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    scheduler.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
