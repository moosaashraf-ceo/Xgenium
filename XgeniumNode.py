import time
import requests
import pandas as pd
import yfinance as yf

# ==========================================
# CONFIGURATION
# ==========================================
# Telegram Setup (Get these from BotFather and @userinfobot on Telegram)
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"

# Assets to monitor (BTC, Gold, S&P 500, Nvidia)
# yfinance tickers: BTC-USD (Bitcoin), GC=F (Gold), ^GSPC (S&P 500), NVDA (Nvidia)
TICKERS = ["BTC-USD", "GC=F", "^GSPC", "NVDA"]
INTERVAL = "1h"    # Use 1-hour chunks so we can see the exact hours before the market opens
PERIOD = "730d"    # yfinance allows a maximum of 730 days for hourly data 

def send_telegram_message(message):
    """Sends a formatted text alert to your Telegram channel/chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Telegram Error: {response.text}")
    except Exception as e:
        print(f"Failed to send telegram message: {e}")

def analyze_asset(ticker_symbol):
    """Fetches data including pre/post market and executes chart-reading."""
    ticker = yf.Ticker(ticker_symbol)
    
    # ADDING prepost=True HERE IS THE SECRET TO PRE-MARKET ALERTS
    df = ticker.history(period=PERIOD, interval=INTERVAL, prepost=True)

    if df.empty or len(df) < 50:
        return

    # Get latest data points
    latest_bar = df.iloc[-1]
    prev_bar = df.iloc[-2]

    current_price = latest_bar["Close"]
    current_volume = latest_bar["Volume"]

    # 2. TECHNIQUE 1: Moving Averages (Trend)
    df["SMA20"] = df["Close"].rolling(window=20).mean()
    df["SMA50"] = df["Close"].rolling(window=50).mean()

    sma20 = df["SMA20"].iloc[-1]
    sma50 = df["SMA50"].iloc[-1]
    trend = "BULLISH" if sma20 > sma50 else "BEARISH "

    # 3. TECHNIQUE 2: Volume Confirmation
    avg_volume_5d = df["Volume"].iloc[-6:-1].mean()
    volume_is_rising = current_volume > avg_volume_5d

    volume_signal = "Neutral"
    if volume_is_rising:
        if current_price > prev_bar["Close"]:
            volume_signal = "STRONG BUYER SUPPORT 💪"
        elif current_price < prev_bar["Close"]:
            volume_signal = "STRONG SELLER PRESSURE 🚨"

    # 4. TECHNIQUE 3: Volatility Breakouts (Bollinger Bands + 2%)
    df["StdDev"] = df["Close"].rolling(window=20).std()
    df["Upper_Band"] = df["SMA20"] + (2 * df["StdDev"])
    df["Lower_Band"] = df["SMA20"] - (2 * df["StdDev"])

    upper_band = df["Upper_Band"].iloc[-1]
    lower_band = df["Lower_Band"].iloc[-1]

    volatility_signal = "Normal"
    # Check if price broke the band AND went 2% further
    if current_price > (upper_band * 1.02):
        volatility_signal = "EXTREME BULLISH VOLATILITY 🚀 (+2% past band)"
    elif current_price < (lower_band * 0.98):
        volatility_signal = "EXTREME BEARISH VOLATILITY 🩸 (-2% past band)"

    # 5. TECHNIQUE 4: ATH & Recent Low Anchors
    all_time_high = df["High"].max()
    ath_date = df["High"].idxmax().strftime("%Y-%m-%d")

    # Find the data *since* that All-Time High date
    df_since_ath = df.loc[df.index >= df["High"].idxmax()]
    recent_low_since_ath = df_since_ath["Low"].min()

    # Calculations for distances
    drop_from_ath_pct = ((all_time_high - current_price) / all_time_high) * 100
    bounce_from_low_pct = (
        ((current_price - recent_low_since_ath) / recent_low_since_ath) * 100
    )

    # 6. CONSTRUCT THE TELEGRAM ALERT
    # We only send an alert if Volume or Volatility shows something interesting
    if volume_signal != "Neutral" or volatility_signal != "Normal":
        alert_msg = (
            f"*SIGNAL ALERT: {ticker_symbol}*\n"
            f"*Current Price:* ${current_price:.2f}\n"
            f"----------------------------------\n"
            f"*Trend (SMA 20/50):* {trend}\n"
            f"*Volume Action:* {volume_signal}\n"
            f"*Volatility:* {volatility_signal}\n"
            f"----------------------------------\n"
            f"*ATH:* ${all_time_high:.2f} ({ath_date})\n"
            f"*Drop from ATH:* -{drop_from_ath_pct:.1f}%\n"
            f"*Recent Low since ATH:* ${recent_low_since_ath:.2f}\n"
            f"*Bounce from Recent Low:* +{bounce_from_low_pct:.1f}%\n"
        )
        send_telegram_message(alert_msg)
        print(f"Alert sent for {ticker_symbol}")
    else:
        print(f"Scanned {ticker_symbol}: No major setup found.")


# ==========================================
# MAIN EXECUTION LOOP
# ==========================================
if __name__ == "__main__":
    print("Raspberry Pi Trading Scanner Started...")
    while True:
        for ticker in TICKERS:
            try:
                analyze_asset(ticker)
            except Exception as e:
                print(f"Error scanning {ticker}: {e}")

        # Sleep for 1 hour before scanning again (keeps Pi lightweight)
        print("Scanning finished. Sleeping for 1 hour...")
        time.sleep(3600)
