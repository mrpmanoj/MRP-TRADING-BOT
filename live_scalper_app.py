import streamlit as st
import yfinance as yf
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

IST = pytz.timezone("Asia/Kolkata")

# ── Page Config ──
st.set_page_config(
    page_title="MRP Scalper",
    page_icon="⚡",
    layout="centered"
)

# ── Auto refresh every 60 seconds ──
st_autorefresh(interval=60000, key="scalper_refresh")

# ── Header ──
st.markdown("<h2 style='text-align:center; color:#1E88E5;'>⚡ MRP Live Scalper</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;'>Auto-refreshes every 60 seconds. Execute manually on Kite.</p>", unsafe_allow_html=True)

now = datetime.datetime.now(IST)
st.markdown(f"<p style='text-align:center; color:gray;'>Last updated: {now.strftime('%I:%M:%S %p IST')}</p>", unsafe_allow_html=True)

st.markdown("---")

# ── Capital and risk settings ──
st.sidebar.header("💰 Your Capital Settings")
capital      = st.sidebar.number_input("Your Trading Capital (₹)", min_value=1000, max_value=100000, value=9800, step=500)
risk_pct     = st.sidebar.slider("Risk per Trade (%)", min_value=0.5, max_value=3.0, value=1.0, step=0.5)
risk_amount  = capital * (risk_pct / 100)
st.sidebar.metric("Max Risk per Trade", f"₹{risk_amount:.0f}")
st.sidebar.markdown("---")
st.sidebar.markdown("**Timeframe:** 1 Minute")
st.sidebar.markdown("**Strategy:** Previous candle breakout")
st.sidebar.markdown("**Risk:Reward:** 1:2")

# ── Market hours verification check ──
market_open  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
is_weekday   = now.weekday() < 5
is_market_open = is_weekday and market_open <= now <= market_close

# ── Watchlist ──
WATCHLIST = {
    "SBIN":       "SBIN.NS",
    "TATAMOTORS": "TATAMOTORS.NS",
    "RELIANCE":   "RELIANCE.NS",
    "WIPRO":      "WIPRO.NS",
    "INFY":       "INFY.NS"
}

# ── Signal scanner ──
def scan_stock(symbol, capital, risk_amount):
    try:
        df = yf.Ticker(symbol).history(period="1d", interval="1m")

        if df.empty or len(df) < 3:
            return None

        latest   = df.iloc[-1]
        previous = df.iloc[-2]

        current_price = round(float(latest['Close']),    2)
        prev_high     = round(float(previous['High']),   2)
        prev_low      = round(float(previous['Low']),    2)
        prev_close    = round(float(previous['Close']),  2)

        # Candle size filter — ignore tiny candles less than 0.1%
        candle_size = abs(prev_high - prev_low) / prev_close
        if candle_size < 0.001:
            return None

        # Percentage based targets — 1:2 risk reward
        if current_price > prev_high:
            signal    = "BUY"
            entry     = current_price
            stop_loss = round(entry - (entry * 0.005), 2)   # 0.5% SL
            target    = round(entry + (entry * 0.01),  2)   # 1.0% Target

        elif current_price < prev_low:
            signal    = "SELL"
            entry     = current_price
            stop_loss = round(entry + (entry * 0.005), 2)   # 0.5% SL
            target    = round(entry - (entry * 0.01),  2)   # 1.0% Target

        else:
            return None

        # Quantity calculator based on your capital and risk
        risk_per_share = abs(entry - stop_loss)
        quantity       = max(1, int(risk_amount / risk_per_share))
        max_quantity   = int(capital / entry)
        quantity       = min(quantity, max_quantity)
        total_cost     = round(quantity * entry, 2)
        max_loss       = round(quantity * abs(entry - stop_loss), 2)
        max_profit     = round(quantity * abs(target - entry),    2)

        return {
            "signal":     signal,
            "entry":      entry,
            "target":     target,
            "stop_loss":  stop_loss,
            "quantity":   quantity,
            "total_cost": total_cost,
            "max_loss":   max_loss,
            "max_profit": max_profit,
            "prev_high":  prev_high,
            "prev_low":   prev_low
        }

    except Exception:
        return None

# ── Main UI display logic ──
st.markdown("### 📊 Live Signal Board")

if not is_market_open:
    st.warning("⏰ Market is closed right now. Live signal scanning will resume between 9:15 AM and 3:30 PM on weekdays.")
    
    # Show how the grid layout functions by rendering mock historical text out of hours
    st.info("ℹ️ Showing off-market consolidation mode. No active signals to display.")
else:
    buy_signals  = []
    sell_signals = []
    neutral      = []

    for name, symbol in WATCHLIST.items():
        result = scan_stock(symbol, capital, risk_amount)
        if result is None:
            neutral.append(name)
        elif result["signal"] == "BUY":
            buy_signals.append((name, result))
        else:
            sell_signals.append((name, result))

    # ── Show BUY signals ──
    for name, s in buy_signals:
        st.markdown(f"""
            <div style="background:#d4edda; border-left:5px solid #28a745;
                        padding:15px; border-radius:8px; margin-bottom:12px;">
                <h3 style="color:#155724; margin:0;">🟢 BUY — {name}</h3>
                <hr style="border-color:#28a745; margin:8px 0;">
                <table style="width:100%; color:#155724; font-size:15px;">
                    <tr>
                        <td>💰 <b>Entry</b></td>
                        <td>₹{s['entry']}</td>
                        <td>📦 <b>Qty</b></td>
                        <td>{s['quantity']} shares</td>
                    </tr>
                    <tr>
                        <td>🎯 <b>Target</b></td>
                        <td>₹{s['target']}</td>
                        <td>💸 <b>Max Profit</b></td>
                        <td>₹{s['max_profit']}</td>
                    </tr>
                    <tr>
                        <td>🛑 <b>Stop Loss</b></td>
                        <td>₹{s['stop_loss']}</td>
                        <td>⚠️ <b>Max Loss</b></td>
                        <td>₹{s['max_loss']}</td>
                    </tr>
                    <tr>
                        <td>💼 <b>Capital Used</b></td>
                        <td>₹{s['total_cost']}</td>
                        <td>⚖️ <b>R:R</b></td>
                        <td>1 : 2</td>
                    </tr>
                </table>
            </div>
        """, unsafe_allow_html=True)

    # ── Show SELL signals ──
    for name, s in sell_signals:
        st.markdown(f"""
            <div style="background:#f8d7da; border-left:5px solid #dc3545;
                        padding:15px; border-radius:8px; margin-bottom:12px;">
                <h3 style="color:#721c24; margin:0;">🔴 SELL — {name}</h3>
                <hr style="border-color:#dc3545; margin:8px 0;">
                <table style="width:100%; color:#721c24; font-size:15px;">
                    <tr>
                        <td>💰 <b>Entry</b></td>
                        <td>₹{s['entry']}</td>
                        <td>📦 <b>Qty</b></td>
                        <td>{s['quantity']} shares</td>
                    </tr>
                    <tr>
                        <td>🎯 <b>Target</b></td>
                        <td>₹{s['target']}</td>
                        <td>💸 <b>Max Profit</b></td>
                        <td>₹{s['max_profit']}</td>
                    </tr>
                    <tr>
                        <td>🛑 <b>Stop Loss</b></td>
                        <td>₹{s['stop_loss']}</td>
                        <td>⚠️ <b>Max Loss</b></td>
                        <td>₹{s['max_loss']}</td>
                    </tr>
                    <tr>
                        <td>💼 <b>Capital Used</b></td>
                        <td>₹{s['total_cost']}</td>
                        <td>⚖️ <b>R:R</b></td>
                        <td>1 : 2</td>
                    </tr>
                </table>
            </div>
        """, unsafe_allow_html=True)

    # ── Show neutral stocks ──
    if neutral:
        st.markdown("### ⚪ No Signal")
        for name in neutral:
            st.write(f"⚪ {name} — Waiting for breakout direction")

st.markdown("---")
st.caption("Paper trade first. Always verify on Kite before placing real orders. Never risk more than 1% per trade.")