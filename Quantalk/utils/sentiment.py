import finnhub
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
load_dotenv()

client = finnhub.Client(api_key=os.getenv("FINNHUB_API_KEY"))

def time_ago(dt_str):
    dt = datetime.fromtimestamp(int(dt_str))
    diff = datetime.now() - dt
    if diff.days > 0:
        return f"{diff.days}일 전"
    elif diff.seconds // 3600 > 0:
        return f"{diff.seconds//3600}시간 전"
    else:
        return f"{diff.seconds//60}분 전"

def get_market_news_with_sentiment(ticker=None, limit=10):
    try:
        if ticker:
            # 회사별 뉴스
            to_date = datetime.today().strftime('%Y-%m-%d')
            from_date = (datetime.today() - timedelta(days=7)).strftime('%Y-%m-%d')
            news = client.company_news(ticker, _from=from_date, to=to_date)
        else:
            # 일반 시장 뉴스
            news = client.general_news('general')[:limit*2]

        result = []
        for n in news[:limit]:
            result.append({
                "title": n['headline'],
                "source": n['source'],
                "time_ago": time_ago(n['datetime']),
                "sentiment": 0.1 if 'positive' in n['headline'].lower() else -0.1 if 'negative' in n['headline'].lower() else 0
            })
        return result
    except:
        return [{"title": "뉴스 서버 연결 중...", "source": "퀀톡", "time_ago": "지금", "sentiment": 0}]

def get_wordcloud_base64(ticker):
    try:
        to_date = datetime.today().strftime('%Y-%m-%d')
        from_date = (datetime.today() - timedelta(days=3)).strftime('%Y-%m-%d')
        news = client.company_news(ticker, _from=from_date, to=to_date)
        text = " ".join([n['headline'] for n in news if len(n['headline']) > 10])
        if len(text) < 50:
            return None
        wc = WordCloud(width=800, height=400, background_color='white', colormap='viridis').generate(text)
        img = BytesIO()
        wc.to_image().save(img, format='PNG')
        return "data:image/png;base64," + base64.b64encode(img.getvalue()).decode()
    except:
        return None