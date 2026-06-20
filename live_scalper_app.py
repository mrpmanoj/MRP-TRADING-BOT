import streamlit as st
import yfinance as yf
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

IST = pytz.timezone("Asia/Kolkata")

st.set_page_config(
    page_title="MRP Smart Scalper",
    page_icon="⚡",
    layout="wide"
)

st_autorefresh(interval=30000, key="scalper_refresh")

# ── Header ──
st.markdown("<h2 style='text-align:center; color:#00E676;'>⚡ MRP Smart Scalper</h2>", unsafe_allow_html=True)

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
    st.stop()

# ── Session State ──
if "active_trade"    not in st.session_state:
    st.session_state.active_trade = None
if "trade_confirmed" not in st.session_state:
    st.session_state.trade_confirmed = False
if "signal_pending"  not in st.session_state:
    st.session_state.signal_pending = None
if "trade_log"       not in st.session_state:
    st.session_state.trade_log = []

# ── Watchlist ──
WATCHLIST = {
    "RELIANCE":   "RELIANCE.NS",
    "HDFCBANK":   "HDFCBANK.NS",
    "ICICIBANK":  "ICICIBANK.NS",
    "SBIN":       "SBIN.NS",
    "INFY":       "INFY.NS",
    "TCS":        "TCS.NS",
    "TATAMOTORS": "TATAMOTORS.NS",
    "WIPRO":      "WIPRO.NS",
    "AXISBANK":   "AXISBANK.NS",
    "BAJFINANCE": "BAJFINANCE.NS"
}

EMA_PERIOD    = 9
VOLUME_PERIOD = 20


# ── Helpers ──
def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def get_30min_direction(symbol):
    try:
        df = yf.Ticker(symbol).history(period="2d", interval="30m")
        if df.empty or len(df) < 2:
            return "NEUTRAL"
        latest        = df.iloc[-1]
        previous      = df.iloc[-2]
        latest_close  = float(latest['Close'])
        prev_close    = float(previous['Close'])
        prev_open     = float(previous['Open'])
        candle_bullish = prev_close > prev_open
        price_above   = latest_close > prev_close
        if candle_bullish and price_above:
            return "UP"
        elif not candle_bullish and not price_above:
            return "DOWN"
        return "NEUTRAL"
    except Exception:
        return "NEUTRAL"


def get_live_price(symbol):
    try:
        df = yf.Ticker(symbol).history(period="1d", interval="1m")
        if df.empty:
            return None
        return round(float(df['Close'].iloc[-1]), 2)
    except Exception:
        return None


def scan_stock(symbol, name):
    try:
        df = yf.Ticker(symbol).history(period="1d", interval="1m")
        if df.empty or len(df) < VOLUME_PERIOD + 2:
            return None

        df['EMA9']       = calculate_ema(df['Close'], EMA_PERIOD)
        df['Volume_Avg'] = df['Volume'].rolling(window=VOLUME_PERIOD).mean()

        latest   = df.iloc[-1]
        previous = df.iloc[-2]

        current_price  = round(float(latest['Close']),   2)
        prev_high      = round(float(previous['High']),  2)
        prev_low       = round(float(previous['Low']),   2)
        current_ema    = round(float(latest['EMA9']),    2)
        current_volume = float(latest['Volume'])
        avg_volume     = float(latest['Volume_Avg'])

        candle_size = abs(prev_high - prev_low) / prev_low
        if candle_size < 0.001:
            return None

        volume_ok     = current_volume > avg_volume
        direction_30m = get_30min_direction(symbol)
        broke_high    = current_price > prev_high
        broke_low     = current_price < prev_low
        above_ema     = current_price > current_ema
        below_ema     = current_price < current_ema

        if broke_high and volume_ok and above_ema and direction_30m == "UP":
            return {
                "name":      name,
                "symbol":    symbol,
                "signal":    "BUY",
                "price":     current_price,
                "target":    round(current_price * 1.01,  2),
                "stop_loss": round(current_price * 0.995, 2),
                "ema":       current_ema,
                "volume_ok": volume_ok,
                "direction": direction_30m
            }

        elif broke_low and volume_ok and below_ema and direction_30m == "DOWN":
            return {
                "name":      name,
                "symbol":    symbol,
                "signal":    "SELL",
                "price":     current_price,
                "target":    round(current_price * 0.99,  2),
                "stop_loss": round(current_price * 1.005, 2),
                "ema":       current_ema,
                "volume_ok": volume_ok,
                "direction": direction_30m
            }

        return None

    except Exception:
        return None


# ════════════════════════════════════════
# SECTION 1 — ACTIVE TRADE MONITOR
# If trade is confirmed, show monitor only
# No new signals shown until trade is closed
# ════════════════════════════════════════

if st.session_state.trade_confirmed and st.session_state.active_trade:
    trade = st.session_state.active_trade
    live_price = get_live_price(trade["symbol"])

    if live_price:
        is_buy  = trade["signal"] == "BUY"
        entry   = trade["price"]
        target  = trade["target"]
        sl      = trade["stop_loss"]

        if is_buy:
            pnl        = round((live_price - entry) * trade.get("qty", 1), 2)
            hit_target = live_price >= target
            hit_sl     = live_price <= sl
        else:
            pnl        = round((entry - live_price) * trade.get("qty", 1), 2)
            hit_target = live_price <= target
            hit_sl     = live_price >= sl

        pnl_color = "#28a745" if pnl >= 0 else "#dc3545"

        # ── EXIT ALERT ──
        if hit_target:
            st.markdown(f"""
                <div style="background:#d4edda; border:3px solid #28a745;
                            padding:20px; border-radius:12px; text-align:center;">
                    <h1 style="color:#155724; margin:0;">🎯 TARGET HIT!</h1>
                    <h2 style="color:#155724;">{trade['name']} reached ₹{live_price}</h2>
                    <h3 style="color:#155724;">EXIT YOUR POSITION NOW ON KITE</h3>
                    <p style="font-size:18px;">Your target was ₹{target}</p>
                </div>
            """, unsafe_allow_html=True)

            # Browser notification
            st.markdown("""
                <script>
                if (Notification.permission === 'granted') {
                    new Notification('🎯 TARGET HIT! Exit your position NOW on Kite!');
                } else if (Notification.permission !== 'denied') {
                    Notification.requestPermission().then(function(permission) {
                        if (permission === 'granted') {
                            new Notification('🎯 TARGET HIT! Exit your position NOW on Kite!');
                        }
                    });
                }
                </script>
            """, unsafe_allow_html=True)

        elif hit_sl:
            st.markdown(f"""
                <div style="background:#f8d7da; border:3px solid #dc3545;
                            padding:20px; border-radius:12px; text-align:center;">
                    <h1 style="color:#721c24; margin:0;">🛑 STOP LOSS HIT!</h1>
                    <h2 style="color:#721c24;">{trade['name']} dropped to ₹{live_price}</h2>
                    <h3 style="color:#721c24;">EXIT YOUR POSITION NOW ON KITE</h3>
                    <p style="font-size:18px;">Your stop loss was ₹{sl}</p>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("""
                <script>
                if (Notification.permission === 'granted') {
                    new Notification('🛑 STOP LOSS HIT! Exit your position NOW on Kite!');
                } else if (Notification.permission !== 'denied') {
                    Notification.requestPermission().then(function(permission) {
                        if (permission === 'granted') {
                            new Notification('🛑 STOP LOSS HIT! Exit your position NOW on Kite!');
                        }
                    });
                }
                </script>
            """, unsafe_allow_html=True)

        else:
            # Trade still running — show live monitor
            st.markdown(f"""
                <div style="background:#fff3cd; border:2px solid #ffc107;
                            padding:20px; border-radius:12px;">
                    <h2 style="color:#856404; margin:0 0 10px 0;">
                        📊 TRADE ACTIVE — {trade['name']} ({trade['signal']})
                    </h2>
                    <table style="width:100%; font-size:16px; color:#856404;">
                        <tr>
                            <td>💰 <b>Entry</b></td>
                            <td>₹{entry}</td>
                            <td>📡 <b>Live Price</b></td>
                            <td>₹{live_price}</td>
                        </tr>
                        <tr>
                            <td>🎯 <b>Target</b></td>
                            <td>₹{target}</td>
                            <td>🛑 <b>Stop Loss</b></td>
                            <td>₹{sl}</td>
                        </tr>
                        <tr>
                            <td>💸 <b>Live P&L</b></td>
                            <td colspan="3">
                                <span style="color:{pnl_color}; font-size:20px; font-weight:bold;">
                                    ₹{pnl:+g}
                                </span>
                            </td>
                        </tr>
                    </table>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # Manual exit button
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ I Exited This Trade", use_container_width=True, type="primary"):
                # Log the trade
                st.session_state.trade_log.append({
                    "time":   now.strftime("%I:%M %p"),
                    "stock":  trade["name"],
                    "signal": trade["signal"],
                    "entry":  entry,
                    "exit":   live_price,
                    "pnl":    pnl
                })
                st.session_state.active_trade    = None
                st.session_state.trade_confirmed = False
                st.session_state.signal_pending  = None
                st.rerun()

        with col2:
            st.info("🔒 No new signals until you exit this trade.")

    st.stop()


# ════════════════════════════════════════
# SECTION 2 — SIGNAL CONFIRMATION
# Signal found — ask if trade was taken
# ════════════════════════════════════════

if st.session_state.signal_pending and not st.session_state.trade_confirmed:
    s = st.session_state.signal_pending
    is_buy     = s["signal"] == "BUY"
    bg_color   = "#d4edda" if is_buy else "#f8d7da"
    text_color = "#155724" if is_buy else "#721c24"
    border     = "#28a745" if is_buy else "#dc3545"
    icon       = "🟢" if is_buy else "🔴"

    st.markdown(f"""
        <div style="background:{bg_color}; border:3px solid {border};
                    padding:20px; border-radius:12px; margin-bottom:20px;">
            <h2 style="color:{text_color}; margin:0 0 10px 0;">
                {icon} {s['signal']} SIGNAL — {s['name']}
            </h2>
            <table style="width:100%; font-size:16px; color:{text_color};">
                <tr>
                    <td>💰 <b>Entry Price</b></td>
                    <td>₹{s['price']}</td>
                    <td>📈 <b>30-Min Trend</b></td>
                    <td>{s['direction']} ✅</td>
                </tr>
                <tr>
                    <td>🎯 <b>Target (1%)</b></td>
                    <td>₹{s['target']}</td>
                    <td>📊 <b>EMA Filter</b></td>
                    <td>✅ Confirmed</td>
                </tr>
                <tr>
                    <td>🛑 <b>Stop Loss (0.5%)</b></td>
                    <td>₹{s['stop_loss']}</td>
                    <td>📦 <b>Volume</b></td>
                    <td>Above Avg ✅</td>
                </tr>
            </table>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### Did you take this trade on Kite?")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ YES — I Took This Trade", use_container_width=True, type="primary"):
            st.session_state.active_trade    = s
            st.session_state.trade_confirmed = True
            st.rerun()

    with col2:
        if st.button("❌ NO — Skip This Signal", use_container_width=True):
            st.session_state.signal_pending  = None
            st.session_state.trade_confirmed = False
            st.rerun()

    st.stop()


# ════════════════════════════════════════
# SECTION 3 — SIGNAL SCANNER
# Only runs when no active trade
# ════════════════════════════════════════

# ── NIFTY mood bar ──
try:
    nifty_df     = yf.Ticker("^NSEI").history(period="1d", interval="1m")
    nifty_price  = round(float(nifty_df['Close'].iloc[-1]), 2)
    nifty_open   = round(float(nifty_df['Open'].iloc[0]),  2)
    nifty_change = round(nifty_price - nifty_open, 2)
    nifty_pct    = round((nifty_change / nifty_open) * 100, 2)
    nifty_mood   = "🟢 BULLISH" if nifty_change > 0 else "🔴 BEARISH"
except Exception:
    nifty_price  = 0
    nifty_change = 0
    nifty_pct    = 0
    nifty_mood   = "⚪ NEUTRAL"

col1, col2, col3 = st.columns(3)
col1.metric("NIFTY 50",     f"₹{nifty_price}", f"{nifty_pct}%")
col2.metric("Market Mood",  nifty_mood)
col3.metric("Status",       "🟢 Scanning..." if not st.session_state.active_trade else "🔒 Trade Active")

st.markdown("---")
st.markdown("### 📊 Scanning 10 Stocks...")

progress = st.progress(0)
status   = st.empty()
found_signal = None

for idx, (name, symbol) in enumerate(WATCHLIST.items()):
    status.text(f"Checking {name}... ({idx+1}/{len(WATCHLIST)})")
    result = scan_stock(symbol, name)

    if result and result["signal"] in ["BUY", "SELL"]:
        found_signal = result
        progress.progress(1.0)
        break

    progress.progress((idx + 1) / len(WATCHLIST))

progress.empty()
status.empty()

if found_signal:
    st.session_state.signal_pending = found_signal
    st.rerun()
else:
    st.info(
        f"😴 No signal found right now.\n\n"
        f"All filters checked — OHOL + Volume + EMA + 30-Min Direction.\n\n"
        f"App auto-refreshes every 30 seconds. Stay ready."
    )

# ── Trade Log ──
if st.session_state.trade_log:
    st.markdown("---")
    st.markdown("### 📜 Today's Trade Log")
    for t in reversed(st.session_state.trade_log):
        pnl_color = "green" if t['pnl'] >= 0 else "red"
        st.markdown(
            f"**{t['time']}** | {t['stock']} | {t['signal']} | "
            f"Entry ₹{t['entry']} → Exit ₹{t['exit']} | "
            f"<span style='color:{pnl_color};'>₹{t['pnl']:+g}</span>",
            unsafe_allow_html=True
        )

st.markdown("---")
st.caption("⚠️ Paper trade first. Always verify on Kite. Never risk more than 1% per trade.")