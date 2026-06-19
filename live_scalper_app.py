import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

IST = pytz.timezone("Asia/Kolkata")

st.set_page_config(
    page_title="MRP Smart Scalper",
    page_icon="⚡",
    layout="wide"
)

st_autorefresh(interval=60000, key="scalper_refresh")

# ── Header ──
st.markdown("<h2 style='text-align:center; color:#00E676;'>⚡ MRP Smart Scalper</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;'>30-Min Direction + 1-Min Entry + Volume + EMA Filter</p>", unsafe_allow_html=True)

now = datetime.datetime.now(IST)
st.markdown(f"<p style='text-align:center; color:gray;'>Last Updated: {now.strftime('%I:%M:%S %p IST')}</p>", unsafe_allow_html=True)

st.markdown("---")

# ── Market Hours Check ──
market_open  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
is_weekday   = now.weekday() < 5
is_market_open = is_weekday and market_open <= now <= market_close

if not is_market_open:
    st.warning("⏰ Market is closed. App runs live between 9:15 AM and 3:30 PM on weekdays.")
    st.info("💡 Come back tomorrow morning at 9:15 AM.")
    st.stop()

# ── Watchlist ──
WATCHLIST = {
    "RELIANCE":  "RELIANCE.NS",
    "HDFCBANK":  "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN":      "SBIN.NS",
    "INFY":      "INFY.NS",
    "TCS":       "TCS.NS",
    "TATAMOTORS":"TATAMOTORS.NS",
    "WIPRO":     "WIPRO.NS",
    "AXISBANK":  "AXISBANK.NS",
    "BAJFINANCE":"BAJFINANCE.NS"
}

EMA_PERIOD    = 9
VOLUME_PERIOD = 20


# ── Helper: Calculate EMA ──
def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


# ── Helper: Get 30-min direction ──
def get_30min_direction(symbol):
    try:
        df = yf.Ticker(symbol).history(period="2d", interval="30m")
        if df.empty or len(df) < 2:
            return "NEUTRAL"

        # Get last two complete 30-min candles
        latest   = df.iloc[-1]
        previous = df.iloc[-2]

        latest_close   = float(latest['Close'])
        previous_close = float(previous['Close'])
        previous_open  = float(previous['Open'])

        # 30-min candle is bullish if it closed higher than it opened
        candle_bullish = previous_close > previous_open

        # Current price is above previous 30-min close
        price_above = latest_close > previous_close

        if candle_bullish and price_above:
            return "UP"
        elif not candle_bullish and not price_above:
            return "DOWN"
        else:
            return "NEUTRAL"

    except Exception:
        return "NEUTRAL"


# ── Main Scanner ──
def scan_stock(symbol, name):
    try:
        ticker = yf.Ticker(symbol)
        df     = ticker.history(period="1d", interval="1m")

        if df.empty or len(df) < VOLUME_PERIOD + 2:
            return None

        # ── Calculate indicators ──
        df['EMA9']       = calculate_ema(df['Close'], EMA_PERIOD)
        df['Volume_Avg'] = df['Volume'].rolling(window=VOLUME_PERIOD).mean()

        latest   = df.iloc[-1]
        previous = df.iloc[-2]

        current_price  = round(float(latest['Close']),      2)
        prev_high      = round(float(previous['High']),     2)
        prev_low       = round(float(previous['Low']),      2)
        current_ema    = round(float(latest['EMA9']),       2)
        current_volume = float(latest['Volume'])
        avg_volume     = float(latest['Volume_Avg'])

        # ── Candle size filter ──
        candle_size = abs(prev_high - prev_low) / prev_low
        if candle_size < 0.001:
            return None

        # ── Volume confirmation ──
        volume_ok = current_volume > avg_volume

        # ── 30-min direction ──
        direction_30m = get_30min_direction(symbol)

        # ── Price closed above/below level ──
        broke_high = current_price > prev_high
        broke_low  = current_price < prev_low

        # ── EMA filter ──
        above_ema = current_price > current_ema
        below_ema = current_price < current_ema

        # ────────────────────────────
        # BUY — all 3 filters must pass
        # ────────────────────────────
        if (
            broke_high
            and volume_ok
            and above_ema
            and direction_30m == "UP"
        ):
            stop_loss = round(current_price * 0.995, 2)
            target    = round(current_price * 1.01,  2)
            risk      = round(current_price - stop_loss, 2)
            reward    = round(target - current_price,    2)

            return {
                "name":         name,
                "signal":       "BUY",
                "price":        current_price,
                "prev_high":    prev_high,
                "prev_low":     prev_low,
                "ema":          current_ema,
                "volume_ok":    volume_ok,
                "direction_30m":direction_30m,
                "target":       target,
                "stop_loss":    stop_loss,
                "risk":         risk,
                "reward":       reward
            }

        # ────────────────────────────
        # SELL — all 3 filters must pass
        # ────────────────────────────
        elif (
            broke_low
            and volume_ok
            and below_ema
            and direction_30m == "DOWN"
        ):
            stop_loss = round(current_price * 1.005, 2)
            target    = round(current_price * 0.99,  2)
            risk      = round(stop_loss - current_price, 2)
            reward    = round(current_price - target,    2)

            return {
                "name":         name,
                "signal":       "SELL",
                "price":        current_price,
                "prev_high":    prev_high,
                "prev_low":     prev_low,
                "ema":          current_ema,
                "volume_ok":    volume_ok,
                "direction_30m":direction_30m,
                "target":       target,
                "stop_loss":    stop_loss,
                "risk":         risk,
                "reward":       reward
            }

        else:
            return {
                "name":         name,
                "signal":       "NEUTRAL",
                "price":        current_price,
                "ema":          current_ema,
                "volume_ok":    volume_ok,
                "direction_30m":direction_30m,
                "prev_high":    prev_high,
                "prev_low":     prev_low
            }

    except Exception as e:
        print(f"Error on {symbol}: {e}")
        return None


# ── Run scan ──
st.markdown("### 📊 Live Signal Board")

buy_signals  = []
sell_signals = []
neutral      = []
errors       = []

progress = st.progress(0)
status   = st.empty()

for idx, (name, symbol) in enumerate(WATCHLIST.items()):
    status.text(f"Scanning {name}... ({idx+1}/{len(WATCHLIST)})")
    result = scan_stock(symbol, name)

    if result is None:
        errors.append(name)
    elif result["signal"] == "BUY":
        buy_signals.append(result)
    elif result["signal"] == "SELL":
        sell_signals.append(result)
    else:
        neutral.append(result)

    progress.progress((idx + 1) / len(WATCHLIST))

progress.empty()
status.empty()

# ── NIFTY mood bar ──
try:
    nifty_df    = yf.Ticker("^NSEI").history(period="1d", interval="1m")
    nifty_price = round(float(nifty_df['Close'].iloc[-1]), 2)
    nifty_open  = round(float(nifty_df['Open'].iloc[0]),  2)
    nifty_change = round(nifty_price - nifty_open, 2)
    nifty_pct   = round((nifty_change / nifty_open) * 100, 2)
    nifty_mood  = "🟢 BULLISH" if nifty_change > 0 else "🔴 BEARISH"
except Exception:
    nifty_price  = 0
    nifty_change = 0
    nifty_pct    = 0
    nifty_mood   = "⚪ NEUTRAL"

col1, col2, col3, col4 = st.columns(4)
col1.metric("NIFTY 50",      f"₹{nifty_price}")
col2.metric("Today Change",  f"₹{nifty_change}", f"{nifty_pct}%")
col3.metric("Market Mood",   nifty_mood)
col4.metric("Signals Found", f"{len(buy_signals) + len(sell_signals)}")

st.markdown("---")

# ── BUY signals ──
if buy_signals:
    st.markdown("### 🟢 BUY Signals")
    for s in buy_signals:
        st.markdown(f"""
            <div style="background:#d4edda; border-left:6px solid #28a745;
                        padding:15px; border-radius:10px; margin-bottom:12px;">
                <h3 style="color:#155724; margin:0 0 8px 0;">
                    🟢 BUY — {s['name']}
                </h3>
                <table style="width:100%; color:#155724; font-size:15px;">
                    <tr>
                        <td>💰 <b>Entry Price</b></td>
                        <td>₹{s['price']}</td>
                        <td>📈 <b>30-Min Trend</b></td>
                        <td>{s['direction_30m']} ✅</td>
                    </tr>
                    <tr>
                        <td>🎯 <b>Target (1%)</b></td>
                        <td>₹{s['target']} (+₹{s['reward']})</td>
                        <td>📊 <b>EMA 9</b></td>
                        <td>₹{s['ema']} ✅</td>
                    </tr>
                    <tr>
                        <td>🛑 <b>Stop Loss (0.5%)</b></td>
                        <td>₹{s['stop_loss']} (-₹{s['risk']})</td>
                        <td>📦 <b>Volume</b></td>
                        <td>{'Above Avg ✅' if s['volume_ok'] else 'Low ⚠️'}</td>
                    </tr>
                    <tr>
                        <td>📉 <b>Previous High</b></td>
                        <td>₹{s['prev_high']}</td>
                        <td>⚖️ <b>Risk:Reward</b></td>
                        <td>1 : 2</td>
                    </tr>
                </table>
            </div>
        """, unsafe_allow_html=True)

# ── SELL signals ──
if sell_signals:
    st.markdown("### 🔴 SELL Signals")
    for s in sell_signals:
        st.markdown(f"""
            <div style="background:#f8d7da; border-left:6px solid #dc3545;
                        padding:15px; border-radius:10px; margin-bottom:12px;">
                <h3 style="color:#721c24; margin:0 0 8px 0;">
                    🔴 SELL — {s['name']}
                </h3>
                <table style="width:100%; color:#721c24; font-size:15px;">
                    <tr>
                        <td>💰 <b>Entry Price</b></td>
                        <td>₹{s['price']}</td>
                        <td>📉 <b>30-Min Trend</b></td>
                        <td>{s['direction_30m']} ✅</td>
                    </tr>
                    <tr>
                        <td>🎯 <b>Target (1%)</b></td>
                        <td>₹{s['target']} (-₹{s['reward']})</td>
                        <td>📊 <b>EMA 9</b></td>
                        <td>₹{s['ema']} ✅</td>
                    </tr>
                    <tr>
                        <td>🛑 <b>Stop Loss (0.5%)</b></td>
                        <td>₹{s['stop_loss']} (+₹{s['risk']})</td>
                        <td>📦 <b>Volume</b></td>
                        <td>{'Above Avg ✅' if s['volume_ok'] else 'Low ⚠️'}</td>
                    </tr>
                    <tr>
                        <td>📈 <b>Previous Low</b></td>
                        <td>₹{s['prev_low']}</td>
                        <td>⚖️ <b>Risk:Reward</b></td>
                        <td>1 : 2</td>
                    </tr>
                </table>
            </div>
        """, unsafe_allow_html=True)

# ── Neutral stocks ──
if neutral:
    st.markdown("### ⚪ Waiting for Signal")
    cols = st.columns(5)
    for idx, s in enumerate(neutral):
        direction_emoji = "📈" if s['direction_30m'] == "UP" else "📉" if s['direction_30m'] == "DOWN" else "➡️"
        with cols[idx % 5]:
            st.markdown(f"""
                <div style="background:#f8f9fa; border:1px solid #dee2e6;
                            padding:10px; border-radius:8px; text-align:center;
                            margin-bottom:8px;">
                    <b>{s['name']}</b><br>
                    ₹{s['price']}<br>
                    {direction_emoji} {s['direction_30m']}<br>
                    <small>EMA: ₹{s['ema']}</small>
                </div>
            """, unsafe_allow_html=True)

# ── Errors ──
if errors:
    with st.expander(f"⚠️ {len(errors)} stocks had data errors"):
        for e in errors:
            st.text(e)

st.markdown("---")
st.caption("⚠️ Paper trade first. Always verify on Kite before placing real orders. Never risk more than 1% per trade.")