"""
MEXC Futures (swap) işlemleri için ince bir sarmalayıcı.
ccxt kütüphanesi üzerinden çalışır. Tüm fonksiyonlar hata durumunda
exception fırlatır; çağıran taraf (scheduler.py) bunu loglar.
"""
import ccxt
import logging

log = logging.getLogger("mexc_client")


def get_exchange(api_key: str, api_secret: str):
    """Verilen API anahtarlarıyla bir ccxt MEXC swap istemcisi döner."""
    exchange = ccxt.mexc({
        "apiKey": api_key,
        "secret": api_secret,
        "options": {"defaultType": "swap"},
        "enableRateLimit": True,
    })
    return exchange


def normalize_symbol(symbol: str) -> str:
    """'BTCUSDT' veya 'BTC_USDT' gibi girişleri ccxt formatına çevirir: 'BTC/USDT:USDT'."""
    s = symbol.upper().replace("_", "").replace("/", "").replace(":USDT", "")
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}/USDT:USDT"
    raise ValueError(f"Desteklenmeyen parite formatı: {symbol}")


SUPPORTED_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]


def get_public_exchange():
    """API anahtarı gerektirmeyen, sadece herkese açık piyasa verisini okuyan
    bir istemci. Canlı test/önizleme için kullanılır — gerçek işlem açmaz."""
    return ccxt.mexc({"options": {"defaultType": "swap"}, "enableRateLimit": True})


def get_candle_info(exchange, symbol: str, timeframe: str = "1d") -> dict:
    """Verilen zaman diliminde bir önceki TAM KAPANMIŞ mumun tüm bilgisini döner."""
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise ValueError(f"Desteklenmeyen zaman dilimi: {timeframe}")

    market_symbol = normalize_symbol(symbol)
    ohlcv = exchange.fetch_ohlcv(market_symbol, timeframe=timeframe, limit=3)
    if not ohlcv:
        raise RuntimeError(f"{market_symbol} için mum verisi alınamadı")

    # Son eleman genelde henüz kapanmamış "şu anki" mum olabilir,
    # bu yüzden ondan önceki tam kapanmış mumu kullanıyoruz.
    candle = ohlcv[-2] if len(ohlcv) >= 2 else ohlcv[-1]
    ts, o, h, l, c, v = candle
    side = "short" if c < o else "long"
    return {"timestamp": ts, "open": o, "high": h, "low": l, "close": c, "volume": v, "side": side}


def get_auto_side(exchange, symbol: str, timeframe: str = "1d") -> str:
    """Verilen zaman dilimindeki önceki tam kapanmış mumun rengine göre 'long'/'short' döner."""
    info = get_candle_info(exchange, symbol, timeframe)
    log.info(
        f"{symbol} [{timeframe}] önceki mum: açılış={info['open']} "
        f"kapanış={info['close']} -> {info['side']}"
    )
    return info["side"]


def open_position(exchange, symbol: str, side: str, leverage: int, margin_usdt: float):
    """
    Piyasa emriyle pozisyon açar.
    side: 'long' veya 'short'
    margin_usdt: pozisyona ayrılacak teminat miktarı (USDT), kaldıraç ile çarpılarak
                 gerçek pozisyon büyüklüğü hesaplanır.
    Döndürür: (order, quantity)
    """
    market_symbol = normalize_symbol(symbol)
    market = exchange.market(market_symbol)

    exchange.set_leverage(leverage, market_symbol)

    ticker = exchange.fetch_ticker(market_symbol)
    price = ticker["last"]
    if not price:
        raise RuntimeError(f"{market_symbol} için fiyat alınamadı")

    notional = margin_usdt * leverage
    quantity = notional / price
    # Borsanın izin verdiği miktar hassasiyetine yuvarla
    quantity = float(exchange.amount_to_precision(market_symbol, quantity))

    order_side = "buy" if side == "long" else "sell"

    log.info(f"Pozisyon açılıyor: {market_symbol} {side} miktar={quantity} kaldıraç={leverage}x")
    order = exchange.create_order(
        symbol=market_symbol,
        type="market",
        side=order_side,
        amount=quantity,
        params={},
    )
    return order, quantity


def close_position(exchange, symbol: str, side: str, quantity: float):
    """Açık pozisyonu ters yönde reduceOnly emirle kapatır."""
    market_symbol = normalize_symbol(symbol)
    close_side = "sell" if side == "long" else "buy"

    log.info(f"Pozisyon kapatılıyor: {market_symbol} {side} miktar={quantity}")
    order = exchange.create_order(
        symbol=market_symbol,
        type="market",
        side=close_side,
        amount=quantity,
        params={"reduceOnly": True},
    )
    return order
