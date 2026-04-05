import argparse
import time
from datetime import datetime, timezone

import ccxt
import pandas as pd

# Mapeo exacto de la tabla HTML: combinacion decimal -> % operabilidad Long
OPERABILITY_LONG = {
    0: 0,
    1: 30,
    2: 25,
    3: 55,
    4: 20,
    5: 50,
    6: 45,
    7: 75,
    8: 15,
    9: 45,
    10: 40,
    11: 70,
    12: 35,
    13: 65,
    14: 60,
    15: 90,
    16: 10,
    17: 40,
    18: 35,
    19: 65,
    20: 30,
    21: 60,
    22: 55,
    23: 85,
    24: 25,
    25: 55,
    26: 50,
    27: 80,
    28: 45,
    29: 75,
    30: 70,
    31: 100,
}

# Orden de bits: 5m 15m 1H 4H 1D
# Formato: (label, ccxt_timeframe, velas_cerradas_a_revisar_para_cruce)
TIMEFRAMES = [
    ("5m", "5m", 3),
    ("15m", "15m", 3),
    ("1H", "1h", 2),
    ("4H", "4h", 2),
    ("1D", "1d", 2),
]


def build_exchange(exchange_id: str):
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({"enableRateLimit": True})
    exchange.load_markets()
    return exchange


def fetch_ema_state(
    exchange,
    symbol: str,
    timeframe: str,
    cross_lookback: int,
    limit: int = 250,
):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    min_required = max(30, cross_lookback + 2)
    if len(ohlcv) < min_required:
        raise ValueError(f"No hay suficientes velas para {timeframe}.")

    df = pd.DataFrame(
        ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )

    # Usamos la vela cerrada mas reciente (penultima) para evitar ruido de vela en formacion.
    close_series = df["close"]
    ema7 = close_series.ewm(span=7, adjust=False).mean()
    ema20 = close_series.ewm(span=20, adjust=False).mean()

    last_closed_idx = len(df) - 2
    curr_fast = float(ema7.iloc[last_closed_idx])
    curr_slow = float(ema20.iloc[last_closed_idx])

    bullish = curr_fast > curr_slow

    cross_up = False
    cross_down = False

    # Detecta cruce ocurrido dentro de las ultimas N velas cerradas.
    start_idx = max(1, last_closed_idx - cross_lookback + 1)
    for i in range(start_idx, last_closed_idx + 1):
        prev_fast = float(ema7.iloc[i - 1])
        prev_slow = float(ema20.iloc[i - 1])
        curr_i_fast = float(ema7.iloc[i])
        curr_i_slow = float(ema20.iloc[i])

        if prev_fast <= prev_slow and curr_i_fast > curr_i_slow:
            cross_up = True
        if prev_fast >= prev_slow and curr_i_fast < curr_i_slow:
            cross_down = True

    candle_ts_ms = int(df["timestamp"].iloc[-2])
    candle_dt = datetime.fromtimestamp(candle_ts_ms / 1000, tz=timezone.utc)

    return {
        "bullish": bullish,
        "cross_up": cross_up,
        "cross_down": cross_down,
        "ema7": curr_fast,
        "ema20": curr_slow,
        "candle_dt": candle_dt,
        "cross_lookback": cross_lookback,
    }


def evaluate_confluence(exchange, symbol: str):
    bits = []
    states = []

    for label, tf, cross_lookback in TIMEFRAMES:
        state = fetch_ema_state(
            exchange,
            symbol=symbol,
            timeframe=tf,
            cross_lookback=cross_lookback,
        )
        bit = "1" if state["bullish"] else "0"
        bits.append(bit)
        states.append((label, state))

    binary = "".join(bits)
    combo = int(binary, 2)
    operability = OPERABILITY_LONG.get(combo, None)

    return {
        "binary": binary,
        "combo": combo,
        "operability": operability,
        "states": states,
    }


def print_report(symbol: str, exchange_id: str, result: dict):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Anchos fijos de columna (sin contar el padding de 1 espacio a cada lado).
    W = {"tf": 3, "sesgo": 13, "cruce": 24, "ema7": 12, "ema20": 12, "vela": 16}
    widths = list(W.values())

    def cell(val, w):
        """Convierte val a str, trunca si es mas largo que w y alinea a la izqda."""
        s = str(val)
        return s[:w] if len(s) > w else s

    def row(*vals):
        cols = [f" {cell(v, w):<{w}} " for v, w in zip(vals, widths)]
        return "|" + "|".join(cols) + "|"

    def hsep(ch="-"):
        segments = ["+" + ch * (w + 2) for w in widths]
        return "".join(segments) + "+"

    # Ancho total del bloque (incluyendo bordes exteriores).
    total = sum(w + 2 for w in widths) + len(widths) + 1

    def banner(text):
        return "| " + f"{text:<{total - 4}}" + " |"

    print()
    print("+" + "=" * (total - 2) + "+")
    print(banner(f"HORA    : {now}"))
    print(banner(f"SYMBOL  : {symbol:<12}  EXCHANGE: {exchange_id.upper()}"))
    print(hsep("="))
    print(row("TF", "SESGO", "CRUCE", "EMA7", "EMA20", "VELA"))
    print(hsep("="))

    for label, s in result["states"]:
        side = "SESGO ALCISTA" if s["bullish"] else "SESGO BAJISTA"
        lk = s["cross_lookback"]
        if s["cross_up"]:
            cross_txt = f"CRUCE AL ALZA (ult {lk}v)"
        elif s["cross_down"]:
            cross_txt = f"CRUCE A LA BAJA (ult {lk}v)"
        else:
            cross_txt = f"SIN CRUCE (ult {lk}v)"

        candle_str = s["candle_dt"].strftime("%Y-%m-%d %H:%M")
        ema7_str  = f"{s['ema7']:.4f}"
        ema20_str = f"{s['ema20']:.4f}"
        print(row(label, side, cross_txt, ema7_str, ema20_str, candle_str))
        print(hsep())

    op = result["operability"]
    op_txt = f"{op}%" if op is not None else "N/A"
    bits_str = " ".join(list(result["binary"]))
    summary = (
        f"BINARIO [{bits_str}]  "
        f"COMBO {result['combo']:>2}  "
        f"OPERABILIDAD LONG: {op_txt}"
    )
    print(banner(summary))
    print("+" + "=" * (total - 2) + "+")


def print_tabla():
    """Imprime la tabla completa de combinaciones binarias y su operabilidad Long."""
    tfs = " ".join(label for label, _, _ in TIMEFRAMES)
    # Anchos derivados del contenido mas largo de cada columna.
    col_binary  = max(len(f"BINARIO ({tfs})"), len("0 0 0 0 0"))
    col_decimal = max(len("DECIMAL"), len(str(31)))
    col_op      = max(len("OPERABILIDAD LONG"), len("100%"))

    def hsep(ch="-"):
        return ("+" + ch * (col_binary + 2) +
                "+" + ch * (col_decimal + 2) +
                "+" + ch * (col_op + 2) + "+")

    def row(b, d, o):
        return (f"| {b:<{col_binary}} | {d:<{col_decimal}} | {o:<{col_op}} |")

    print()
    print(hsep("="))
    print(row(f"BINARIO ({tfs})", "DECIMAL", "OPERABILIDAD LONG"))
    print(hsep("="))
    for combo in range(32):
        binary = format(combo, "05b")
        bits_spaced = " ".join(list(binary))
        op = OPERABILITY_LONG.get(combo)
        op_txt = f"{op}%" if op is not None else "N/A"
        print(row(bits_spaced, str(combo), op_txt))
        print(hsep())


def parse_args():
    parser = argparse.ArgumentParser(
        description="Confluencia MTF EMA7/20 y porcentaje de operabilidad Long.",
    )
    parser.add_argument(
        "--symbol",
        default="DOGE/USDT",
        help="Par de mercado segun formato del exchange.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Minutos entre consultas (modo continuo).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Ejecuta una sola consulta y termina.",
    )
    parser.add_argument(
        "--tabla",
        action="store_true",
        help="Imprime la tabla de combinaciones binarias y operabilidad Long, luego termina.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.tabla:
        print_tabla()
        return

    exchange_id = "binance"
    exchange = build_exchange(exchange_id)

    if args.symbol not in exchange.markets:
        raise ValueError(
            f"El simbolo {args.symbol} no existe en {exchange_id}. "
            "Revisa el formato (ej: BTC/USDT)."
        )

    while True:
        try:
            result = evaluate_confluence(exchange, args.symbol)
            print_report(args.symbol, exchange_id, result)
        except Exception as exc:
            print(f"Error al consultar datos: {exc}")

        if args.once:
            break

        sleep_seconds = max(1, args.interval * 60)
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()

