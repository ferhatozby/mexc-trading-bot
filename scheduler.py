"""
Zamanlanmış açma/kapama işlerini yönetir.
Her job için iki APScheduler görevi kurulur: start_time'da aç, end_time'da kapat.
"""
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime

import db
import mexc_client

log = logging.getLogger("scheduler")

API_KEY = os.environ.get("MEXC_API_KEY", "")
API_SECRET = os.environ.get("MEXC_API_SECRET", "")

_scheduler = BackgroundScheduler()


def _get_exchange():
    if not API_KEY or not API_SECRET:
        raise RuntimeError("MEXC_API_KEY / MEXC_API_SECRET .env dosyasında tanımlı değil")
    return mexc_client.get_exchange(API_KEY, API_SECRET)


def _do_rotate(job_id):
    """
    start_time == end_time olan işler için: önce (varsa) önceki pozisyonu
    kapatır, SONRA yeni yönü hesaplayıp yeni pozisyonu açar. Tek bir tetikleyici
    içinde sırayla çalıştığı için 'aynı anda iki ayrı tetikleyici' riski olmaz.
    """
    job = db.get_job(job_id)
    if not job or not job["active"]:
        return

    exchange = _get_exchange()

    # 1) Varsa önceki pozisyonu kapat
    quantity = job.get("open_quantity")
    if quantity:
        close_side = job.get("resolved_side") or job["side"]
        try:
            order = mexc_client.close_position(exchange, job["symbol"], close_side, quantity)
            db.set_open_quantity(job_id, None)
            db.add_log(job_id, "close_ok", f"order_id={order.get('id')}")
            log.info(f"[job {job_id}] (rotate) önceki pozisyon kapatıldı")
        except Exception as e:
            db.add_log(job_id, "close_error", str(e))
            log.exception(f"[job {job_id}] (rotate) kapatma hatası — yeni pozisyon açılmadı")
            return  # kapatma başarısızsa yeni pozisyon açmak riskli, dur

    # 2) Yeni pozisyonu aç
    try:
        side = job["side"]
        if side == "auto":
            side = mexc_client.get_auto_side(exchange, job["symbol"], job.get("candle_timeframe", "1d"))
        db.set_resolved_side(job_id, side)

        order, new_quantity = mexc_client.open_position(
            exchange, job["symbol"], side, job["leverage"], job["margin_usdt"]
        )
        db.set_open_quantity(job_id, new_quantity)
        db.add_log(job_id, "open_ok", f"yön={side} miktar={new_quantity} order_id={order.get('id')}")
        log.info(f"[job {job_id}] (rotate) yeni pozisyon açıldı, yön={side}")
    except Exception as e:
        db.add_log(job_id, "open_error", str(e))
        log.exception(f"[job {job_id}] (rotate) açma hatası")


def _do_open(job_id):
    job = db.get_job(job_id)
    if not job or not job["active"]:
        return
    try:
        exchange = _get_exchange()

        side = job["side"]
        if side == "auto":
            side = mexc_client.get_auto_side(exchange, job["symbol"], job.get("candle_timeframe", "1d"))
        db.set_resolved_side(job_id, side)

        order, quantity = mexc_client.open_position(
            exchange, job["symbol"], side, job["leverage"], job["margin_usdt"]
        )
        db.set_open_quantity(job_id, quantity)
        db.add_log(job_id, "open_ok", f"yön={side} miktar={quantity} order_id={order.get('id')}")
        log.info(f"[job {job_id}] pozisyon açıldı, yön={side}, miktar={quantity}")
    except Exception as e:
        db.add_log(job_id, "open_error", str(e))
        log.exception(f"[job {job_id}] açma hatası")


def _do_close(job_id):
    job = db.get_job(job_id)
    if not job or not job["active"]:
        return
    quantity = job.get("open_quantity")
    if not quantity:
        db.add_log(job_id, "close_error", "Açık pozisyon miktarı bulunamadı, kapatma atlandı")
        return
    # 'auto' modda hangi yönde açıldığını resolved_side'dan al, yoksa job['side']'ı kullan.
    side = job.get("resolved_side") or job["side"]
    try:
        exchange = _get_exchange()
        order = mexc_client.close_position(exchange, job["symbol"], side, quantity)
        db.set_open_quantity(job_id, None)
        db.add_log(job_id, "close_ok", f"order_id={order.get('id')}")
        log.info(f"[job {job_id}] pozisyon kapatıldı")
    except Exception as e:
        db.add_log(job_id, "close_error", str(e))
        log.exception(f"[job {job_id}] kapatma hatası")


_DAY_MAP = {"mon": "mon", "tue": "tue", "wed": "wed", "thu": "thu",
            "fri": "fri", "sat": "sat", "sun": "sun"}


def schedule_job(job: dict):
    """job['days'] formatı: 'daily' | 'mon,wed,fri' | 'once:YYYY-MM-DD'"""
    job_id = job["id"]
    same_time = job["start_time"] == job["end_time"]
    start_h, start_m = map(int, job["start_time"].split(":"))
    end_h, end_m = map(int, job["end_time"].split(":"))

    if job["days"].startswith("once:"):
        date_str = job["days"].split(":", 1)[1]
        start_dt = datetime.strptime(f"{date_str} {job['start_time']}", "%Y-%m-%d %H:%M")
        if same_time:
            _scheduler.add_job(_do_rotate, DateTrigger(run_date=start_dt),
                                id=f"rotate_{job_id}", replace_existing=True, args=[job_id])
        else:
            end_dt = datetime.strptime(f"{date_str} {job['end_time']}", "%Y-%m-%d %H:%M")
            _scheduler.add_job(_do_open, DateTrigger(run_date=start_dt),
                                id=f"open_{job_id}", replace_existing=True, args=[job_id])
            _scheduler.add_job(_do_close, DateTrigger(run_date=end_dt),
                                id=f"close_{job_id}", replace_existing=True, args=[job_id])
        return

    if job["days"] == "daily":
        day_of_week = "*"
    else:
        day_of_week = ",".join(_DAY_MAP[d.strip()] for d in job["days"].split(","))

    if same_time:
        # Açılış = kapanış saati: "önceki pozisyonu kapat, hemen yenisini aç" tek adımda.
        _scheduler.add_job(
            _do_rotate, CronTrigger(day_of_week=day_of_week, hour=start_h, minute=start_m),
            id=f"rotate_{job_id}", replace_existing=True, args=[job_id],
        )
        return

    _scheduler.add_job(
        _do_open, CronTrigger(day_of_week=day_of_week, hour=start_h, minute=start_m),
        id=f"open_{job_id}", replace_existing=True, args=[job_id],
    )
    _scheduler.add_job(
        _do_close, CronTrigger(day_of_week=day_of_week, hour=end_h, minute=end_m),
        id=f"close_{job_id}", replace_existing=True, args=[job_id],
    )


def unschedule_job(job_id):
    for prefix in ("open_", "close_", "rotate_"):
        try:
            _scheduler.remove_job(f"{prefix}{job_id}")
        except Exception:
            pass


def start():
    db.init_db()
    for job in db.list_jobs():
        if job["active"]:
            schedule_job(job)
    _scheduler.start()
    log.info("Zamanlayıcı başlatıldı")


def get_scheduler():
    return _scheduler
