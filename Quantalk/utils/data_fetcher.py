import yfinance as yf
import finnhub
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()

finnhub_client = finnhub.Client(api_key=os.getenv("FINNHUB_API_KEY"))
def get_index_data(symbol):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="5d")
        if len(hist) < 2: return None
        price = round(hist['Close'].iloc[-1], 2)
        change = round((price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2] * 100, 2)
        return {"price": price, "change": change}
    except:
        return None

def get_stock_detail(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="6mo", interval="1d")
        info = t.info
        price = info.get('currentPrice') or info.get('regularMarketPrice') or hist['Close'].iloc[-1]
        prev = info.get('previousClose') or hist['Close'].iloc[-2]
        return {
            "history": hist,
            "info": {
                "price": price,
                "change": price - prev,
                "change_pct": round((price - prev)/prev * 100, 2),
                "volume": int(hist['Volume'].iloc[-1]),
                "marketCap": info.get('marketCap', 0)
            }
        }
    except Exception as e:
        print(e)
        return None