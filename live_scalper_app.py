import streamlit as st
import yfinance as yf
import pandas as pd

# 1. Page Configuration tailored for Mobile Phone Screens
st.set_page_config(page_title="1-Min Scalping Dashboard", layout="centered")

st.markdown("<h2 style='text-align: center; color: #1E88E5;'>⚡ Live 1-Minute Micro-Scalper</h2>", unsafe_allow_html=True)
st.write("Track quick momentum shifts cleanly on your phone. Execute trades manually on Kite.")
st.markdown("---")

# 2. Watchlist (Highly active NSE stocks)
watchlist = ["SBIN.NS", "TATAMOTORS.NS", "RELIANCE.NS", "WIPRO.NS", "INFY.NS"]

st.sidebar.header("⚙️ Strategy Settings")
st.sidebar.write("**Timeframe:** 1 Minute")
st.sidebar.write("**Risk-to-Reward:** 1:2 Ratio")

st.markdown("### 🔍 Real-Time Scanned Signals")

# 3. Main Data Loop
for stock in watchlist:
    try:
        # FIXED: Fetch data for ONE specific ticker at a time to prevent MultiIndex format crashes
        ticker_object = yf.Ticker(stock)
        stock_data = ticker_object.history(period="1d", interval="1m")
        
        if not stock_data.empty and len(stock_data) >= 2:
            # Get the absolute latest closed candle and the one before it
            latest_candle = stock_data.iloc[-1]
            previous_candle = stock_data.iloc[-2]
            
            current_price = float(latest_candle['Close'])
            prev_high = float(previous_candle['High'])
            prev_low = float(previous_candle['Low'])
            
            clean_stock_name = stock.replace('.NS', '')
            
            # --- 🟢 BUY LOGIC ---
            if current_price > prev_high:
                target_price = current_price + 0.50
                stop_loss_price = current_price - 1.00
                
                st.info(
                    f"**🚀 {clean_stock_name}** | Price: ₹{current_price:.2f}\n\n"
                    f"**Signal:** 🟢 BUY BREAKOUT\n\n"
                    f"🎯 **Target:** ₹{target_price:.2f} | 🛑 **Stop-Loss:** ₹{stop_loss_price:.2f}"
                )
                
            # --- 🔴 SELL LOGIC ---
            elif current_price < prev_low:
                target_price = current_price - 0.50
                stop_loss_price = current_price + 1.00
                
                st.warning(
                    f"**📉 {clean_stock_name}** | Price: ₹{current_price:.2f}\n\n"
                    f"**Signal:** 🔴 SELL BREAKDOWN\n\n"
                    f"🎯 **Target:** ₹{target_price:.2f} | 🛑 **Stop-Loss:** ₹{stop_loss_price:.2f}"
                )
            
            # --- ⚪ SIDEWAYS LOGIC ---
            else:
                st.write(f"⚪ {clean_stock_name}: **₹{current_price:.2f}** (Searching for direction...)")
                
    except Exception as error:
        # Silently skip any connection errors to keep your mobile view clean
        continue

st.markdown("---")
st.caption("Refresh your mobile browser page at any time to pull the latest 1-minute ticks.")