# app.py — 퀀톡 v8.0 (최종 완성본: 뉴스 감정 아이콘 복원 + 레이아웃 최적화)
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
from dotenv import load_dotenv

# =========================
# utils 불러오기
# =========================
try:
    load_dotenv()
    from utils.data_fetcher import get_index_data, get_stock_detail
    from utils.indicators import calculate_indicators, interpret_indicator
    from utils.sentiment import get_wordcloud_base64, get_market_news_with_sentiment
    from utils.chatbot import chatbot_response
except Exception as e:
    st.error(f"utils 오류: {e}")
    st.stop()

# =========================
# 페이지 설정 + 배경
# =========================
st.set_page_config(page_title="퀀톡", layout="wide", page_icon="chart-increase")

st.markdown("""
<style>
.stApp {
  background: radial-gradient(1200px 600px at 50% 0%, rgba(160, 230, 255, 0.50), rgba(140, 210, 245, 0.25) 40%, rgba(120, 190, 235, 0.18) 70%, rgba(110, 180, 230, 0.10));
}
.card {
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.45);
  box-shadow: 0 10px 30px rgba(10, 20, 30, 0.10);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 18px;
  padding: 3px; /* 14px -> 8px 으로 변경 */
  margin-bottom: 3px; /* 12px -> 6px 으로 변경 */
}
.kpi-row { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
.kpi-name { font-size: 12px; font-weight: 700; color: rgba(10,20,30,0.60); }
.kpi-price { font-size: 16px; font-weight: 900; color: rgba(10,20,30,0.85); }
.kpi-chg { font-size: 12px; font-weight: 800; }
.kpi-pos { color: rgba(0,150,80,0.95); }
.kpi-neg { color: rgba(220,60,60,0.95); }
.kpi-flat { color: rgba(90,100,110,0.80); }
/* 챗봇 입력창 확대 */
div[data-testid="stChatInput"] > div > div > input {
    font-size: 16px !important;
    padding: 12px !important;
}
</style>
""", unsafe_allow_html=True)

# =========================
# 세션 상태 + 사이드바
# =========================
if "page" not in st.session_state: st.session_state.page = "main"
if "ticker" not in st.session_state: st.session_state.ticker = ""

st.sidebar.image("https://img.icons8.com/fluency/96/financial-analyst.png", width=80)
st.sidebar.title("퀀톡 v8.0")

ticker_input = st.sidebar.text_input("종목 티커 입력", placeholder="입력 후 엔터").strip().upper()
if ticker_input and st.session_state.ticker != ticker_input:
    st.session_state.page = "detail"
    st.session_state.ticker = ticker_input
    st.rerun()

if st.sidebar.button("종목 분석하기", type="primary"):
    if ticker_input:
        st.session_state.page = "detail"
        st.session_state.ticker = ticker_input
        st.rerun()

if st.session_state.page == "detail":
    if st.sidebar.button("메인으로 돌아가기", type="secondary"):
        st.session_state.page = "main"
        st.session_state.ticker = ""
        st.rerun()

# =========================
# S&P500 티커 로드
# =========================
@st.cache_data(ttl=86400)
def get_sp500_tickers():
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
        df = pd.read_csv(url)
        return df['Symbol'].str.replace('.', '-', regex=False).tolist()[:150]
    except:
        return ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","BRK-B","LLY","JPM"]

# =========================
# 경제 일정
# =========================
@st.cache_data(ttl=3600)
def get_economic_calendar():
    try:
        url = "https://sslecal2.investing.com?columns=exc_currency,exc_importance,exc_title&features=datepicker&countries=25,32,6,37,72,22,17,39,14,10,35,43,56,36,110,11,26,12,4,5&calType=week&timeZone=64&lang=1"
        headers = {"User-Agent": "Mozilla/5.0"}
        data = requests.get(url, headers=headers).json()
        events = []
        for item in data[:10]:
            date = pd.to_datetime(item["date"]).strftime("%m/%d")
            country = item.get("country", "기타")
            title = item.get("title", "제목 없음")
            importance = "★★★" if item.get("importance",0) == 3 else "★★" if item.get("importance",0) == 2 else "★"
            events.append({"날짜": date, "국가": country, "지표": title, "중요도": importance})
        return pd.DataFrame(events)
    except:
        return pd.DataFrame([
            {"날짜": "12/13", "국가": "미국", "지표": "소매판매", "중요도": "★★★"},
            {"날짜": "12/14", "국가": "중국", "지표": "산업생산", "중요도": "★★"},
        ])

# =========================
# 데이터 함수들
# =========================
@st.cache_data(ttl=60)
def fetch_quote(sym): return get_index_data(sym) or {}
@st.cache_data(ttl=180)
def fetch_detail(ticker): return get_stock_detail(ticker) or {}

def fetch_series(ticker):
    data = fetch_detail(ticker)
    if not data or "history" not in data: return None
    df = data["history"]
    if df is None or df.empty or "Close" not in df.columns: return None
    return df["Close"].tail(60)

def sparkline(series):
    if series is None or series.empty:
        return go.Figure().update_layout(height=80, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor="rgba(0,0,0,0)")
    fig = go.Figure(go.Scatter(y=series.values, mode="lines", fill="tozeroy", line=dict(width=2)))
    fig.update_layout(height=80, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig

def chg_class(x):
    if x is None or pd.isna(x): return "kpi-flat"
    return "kpi-pos" if x > 0.05 else "kpi-neg" if x < -0.05 else "kpi-flat"

@st.cache_data(ttl=180)
def get_market_data(tickers):
    rows = []
    for t in tickers[:150]:
        try:
            d = fetch_detail(t)
            if not d: continue
            info = d.get("info",{})
            hist = d.get("history", pd.DataFrame())
            if hist.empty: continue
            chg = info.get("change_pct") or 0
            mcap = info.get("marketCap") or hist["Close"].iloc[-1]*1e6
            sector = info.get("sector") or "기타"
            rows.append({"sector": sector, "ticker": t, "size": float(mcap), "chg": float(chg)})
        except: continue
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def treemap_fig(df):
    if df.empty: return go.Figure().update_layout(height=500, paper_bgcolor="rgba(0,0,0,0)")
    fig = px.treemap(df, path=["sector","ticker"], values="size", color="chg",
                     color_continuous_scale=["#d84a4a","#f2f2f2","#18a957"], range_color=(-5,5))
    fig.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=500, paper_bgcolor="rgba(0,0,0,0)")
    return fig

# =========================
# 메인 페이지
# =========================
def main_page():
    st.title("실시간 시장 대시보드")

    left, center, right = st.columns([0.35, 0.40, 0.25], gap="small")

    # LEFT: AI 비서 + 경제 일정 (최하단 배치)
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("AI 금융 비서")
        if "main_chat" not in st.session_state:
            st.session_state.main_chat = [{"role": "assistant", "content": "안녕하세요! 시장 상황이나 종목에 대해 물어보세요."}]
        
        # 대화 히스토리 (스크롤 가능 + 높이 확대)
        chat_container = st.container(height=600)
        with chat_container:
            for m in st.session_state.main_chat:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])

        # 입력창 확대
        if prompt := st.chat_input("질문 입력", key="main_chat_input"):
            st.session_state.main_chat.append({"role": "user", "content": prompt})
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)
            with chat_container:
                with st.chat_message("assistant"):
                    with st.spinner("생각 중..."):
                        response = chatbot_response(prompt)
                    st.markdown(response)
            st.session_state.main_chat.append({"role": "assistant", "content": response})
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # 경제 일정 (챗봇 아래 배치)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("금주 주요 경제 일정")
        events = get_economic_calendar()
        st.dataframe(events, hide_index=True, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # CENTER: KPI + 히트맵 + 요약
    with center:
        # KPI
        r1c1, r1c2 = st.columns(2)
        r2c1, r2c2 = st.columns(2)

        kpis = [
            ("S&P 500", "^GSPC", r1c1),
            ("NASDAQ", "^IXIC", r1c2)
        ]

        for name, sym, col in kpis:
            q = fetch_quote(sym)
            price = q.get("price")
            chg = q.get("change")
            cls = chg_class(chg)
            series = fetch_series(sym)
            if series is None or series.empty:
                series = fetch_series(sym.replace("^", "") if "^" in sym else sym)

            with col:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown(f"""
                <div class="kpi-row">
                  <div class="kpi-name">{name}</div>
                  <div class="kpi-price">{(float(price) if price else 0):,.2f}</div>
                </div>
                <div class="kpi-chg {cls}">{(float(chg) if chg else 0):+,.2f}%</div>
                """, unsafe_allow_html=True)
                if series is not None and not series.empty:
                    st.plotly_chart(sparkline(series), use_container_width=True, config={"displayModeBar": False})
                st.markdown("</div>", unsafe_allow_html=True)

        # 히트맵
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("S&P500 Heatmap")
        sp500 = get_sp500_tickers()
        df_heat = get_market_data(sp500)
        st.plotly_chart(treemap_fig(df_heat), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # 히트맵 요약
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("오늘의 시장 요약")
        up = len(df_heat[df_heat["chg"] > 0])
        down = len(df_heat[df_heat["chg"] < 0])
        col1, col2 = st.columns(2)
        col1.metric("상승 종목", f"{up}개")
        col2.metric("하락 종목", f"{down}개")
        st.markdown("</div>", unsafe_allow_html=True)

    # RIGHT: 실시간 속보 (감정 아이콘 복원 + 강조)
    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("실시간 속보")
        news = get_market_news_with_sentiment(limit=8)
        for n in news:
            sentiment_score = n.get('sentiment', 0) or 0
            if sentiment_score > 0.05:
                icon = "🟢"
            elif sentiment_score < -0.05:
                icon = "🔴"
            else:
                icon = "⚪"
            st.markdown(f"<span style='font-size:24px'>{icon}</span> **{n.get('title','제목 없음')}**", unsafe_allow_html=True)
            st.caption(f"{n.get('source','')} · {n.get('time_ago','방금 전')}")
        st.markdown("</div>", unsafe_allow_html=True)

# =========================
# 상세 페이지
# =========================
def detail_page(ticker):
    st.title(f"{ticker} · 종목 분석")
    if st.button("메인으로 돌아가기"):
        st.session_state.page = "main"
        st.session_state.ticker = ""
        st.rerun()

    data = get_stock_detail(ticker)
    if not data:
        st.error("데이터를 불러올 수 없습니다")
        st.stop()

    df = data['history']
    info = data['info']

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("현재가", f"{info.get('price',0):,.0f}원")
    c2.metric("등락률", f"{info.get('change_pct',0):+.2f}%")
    c3.metric("거래량", f"{info.get('volume',0):,.0f}")
    c4.metric("시총", f"{info.get('marketCap',0)/1e12:.1f}조")

    fig = go.Figure(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close']))
    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True)

    indicators = calculate_indicators(df)
    st.dataframe(pd.DataFrame(indicators.items(), columns=["지표","값"]))

    st.subheader("최근 뉴스")
    news = get_market_news_with_sentiment(ticker=ticker, limit=8)
    for n in news:
        sentiment_score = n.get('sentiment', 0) or 0
        if sentiment_score > 0.05:
            icon = "🟢"
        elif sentiment_score < -0.05:
            icon = "🔴"
        else:
            icon = "⚪"
        st.markdown(f"<span style='font-size:24px'>{icon}</span> **{n.get('title','')}**", unsafe_allow_html=True)

    wc = get_wordcloud_base64(ticker)
    if wc: st.image(wc, use_column_width=True)

    st.subheader(f"{ticker} 전용 AI 비서")
    if prompt := st.chat_input(f"{ticker}에 대해 물어보세요"):
        with st.chat_message("user"): st.write(prompt)
        with st.chat_message("assistant"): st.write(chatbot_response(f"종목: {ticker}\n{prompt}"))

# =========================
# 라우터
# =========================
if st.session_state.page == "main":
    main_page()
else:
    detail_page(st.session_state.ticker)