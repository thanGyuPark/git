# app.py — 퀀톡 v8.0 (재무 분석 기능 통합 및 최적화)
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import requests
import os
import finnhub
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timedelta

# =========================
# utils 불러오기
# =========================
try:
    load_dotenv()
    from utils.data_fetcher import get_index_data, get_stock_detail
    from utils.indicators import calculate_indicators, interpret_indicator
    from utils.sentiment import get_wordcloud_base64, get_market_news_with_sentiment
    from utils.chatbot import chatbot_response
    from utils.financial_analysis import run_full_analysis_pipeline 
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
  padding: 3px; 
  margin-bottom: 3px; 
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
finnhub_client = finnhub.Client(api_key=os.getenv("FINNHUB_API_KEY"))

@st.cache_data(ttl=3600)
def get_economic_calendar():
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        st.error("Finnhub API 키가 설정되지 않았습니다.")
        return pd.DataFrame()

    try:
        # 1. 날짜 계산
        today = datetime.today()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=13)

        from_date = start_of_week.strftime("%Y-%m-%d")
        to_date = end_of_week.strftime("%Y-%m-%d")

        # 2. requests를 사용하여 직접 API 호출 (라이브러리 버전 문제 해결)
        url = "https://finnhub.io/api/v1/calendar/economic"
        params = {
            "from": from_date,
            "to": to_date,
            "token": api_key
        }
        
        response = requests.get(url, params=params)
        
        # 3. 응답 처리
        if response.status_code != 200:
             # 에러 발생 시 처리
            if response.status_code == 403:
                st.error("API 접근 거부 (403): 무료 키 사용 제한.")
            else:
                st.error(f"API 오류: {response.status_code} - {response.text}")
            return pd.DataFrame()

        data = response.json()
        calendar = data.get("economicCalendar", [])
        
        if not calendar:
            st.warning("수신된 경제 일정 데이터가 없습니다.")
            return pd.DataFrame()

        # 4. 데이터 가공
        country_map = {
            "US": "미국", "EU": "유로존", "CN": "중국", "JP": "일본", "GB": "영국",
            "CA": "캐나다", "AU": "호주", "DE": "독일", "FR": "프랑스", "KR": "한국"
        }

        events = []
        for item in sorted(calendar, key=lambda x: x.get("date", ""))[:15]:
            date_str = item.get("date", "")[:10].replace("-", "/")
            country_code = item.get("country", "기타")
            country = country_map.get(country_code, country_code)
            event = item.get("event", "제목 없음")
            impact = item.get("impact", "").lower()
            importance_icon = "★★★" if impact == "high" else "★★" if impact in ["medium", "moderate"] else "★"

            events.append({
                "날짜": date_str,
                "국가": country,
                "지표": event,
                "중요도": importance_icon
            })

        return pd.DataFrame(events)

    except Exception as e:
        st.error(f"경제 일정 로드 중 시스템 오류: {e}")
        return pd.DataFrame()

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
        # [수정] use_container_width -> width='stretch'
        st.dataframe(events, hide_index=True, width='stretch')
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
                    # [수정] use_container_width -> width='stretch'
                    st.plotly_chart(sparkline(series), width='stretch', config={"displayModeBar": False})
                st.markdown("</div>", unsafe_allow_html=True)

        # 히트맵
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("S&P500 Heatmap")
        sp500 = get_sp500_tickers()
        df_heat = get_market_data(sp500)
        # [수정] use_container_width -> width='stretch'
        st.plotly_chart(treemap_fig(df_heat), width='stretch')
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
# 상세 페이지 (수정됨)
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
    # [수정] use_container_width -> width='stretch'
    st.plotly_chart(fig, width='stretch')

    indicators = calculate_indicators(df)
    st.dataframe(pd.DataFrame(indicators.items(), columns=["지표","값"]))
    
    # =========================================
    # 재무 보고서 분석 섹션
    # =========================================
    st.markdown("---")
    st.subheader(f"📄 {ticker} 재무 보고서 자동 분석 (LLM/RAG 기반)")
    
    # 세션 상태 키 설정
    summary_key = f'analysis_summary_{ticker}'
    pdf_key = f'analysis_pdf_path_{ticker}'

    # 분석 시작 버튼
    if st.button(f"**{ticker} SEC 보고서 분석 시작** (약 30~60초 소요)", type="primary"):
        with st.spinner("SEC 보고서 다운로드 및 LLM 분석 중... 잠시만 기다려주세요."):
            pdf_path, summary_text = run_full_analysis_pipeline(ticker)
        
        st.session_state[summary_key] = summary_text
        st.session_state[pdf_key] = pdf_path
        st.rerun() # 최종 수정 완료

    # 분석 결과 표시
    summary_text = st.session_state.get(summary_key)
    pdf_path = st.session_state.get(pdf_key)
    
    if summary_text:
        if "오류 발생" in summary_text:
             st.error(f"분석 오류: {summary_text}")
        else:
            st.markdown("### 📝 LLM 최종 종합 분석 요약:")
            st.info(summary_text)
        
        # PDF 다운로드 버튼 표시
        if pdf_path and os.path.exists(pdf_path):
            st.markdown("### 📥 상세 보고서 다운로드")
            
            try:
                with open(pdf_path, "rb") as file:
                    st.download_button(
                        label="**PDF 보고서 다운로드**",
                        data=file,
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf"
                    )
            except Exception as e:
                st.error(f"PDF 파일을 로드하는 데 실패했습니다. 파일 경로를 확인해주세요. ({e})")
    
    st.markdown("---")
    
    # =========================================
    # 기존 코드
    # =========================================

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
    # [수정] use_column_width -> width='stretch'
    if wc: st.image(wc, width='stretch')

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