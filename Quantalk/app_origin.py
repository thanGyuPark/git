import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv

# ── utils 모듈 임포트 ─────────────────────────────────────────────────────
try:
    load_dotenv()
    from utils.data_fetcher import get_index_data, get_stock_detail
    from utils.indicators import calculate_indicators, interpret_indicator
    from utils.sentiment import get_wordcloud_base64, get_market_news_with_sentiment
    from utils.chatbot import chatbot_response
except ImportError as e:
    st.error(f"utils 모듈 오류: {e}")
    st.info("utils 폴더 안에 필요한 파일들이 있는지 확인하고, 모든 라이브러리가 설치되었는지 (pip install) 확인해주세요!")
    st.stop()

# ── 페이지 설정 ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="퀀톡 - AI 금융 대시보드", layout="wide", page_icon="chart-increasing")

# ── 세션 상태 초기화 ───────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "main"
if "ticker" not in st.session_state:
    st.session_state.ticker = ""
if "reset_ticker_input" not in st.session_state:
    st.session_state.reset_ticker_input = False  # ✅ 위젯 입력값 리셋 트리거

# ✅ 중요: text_input(위젯) 생성 전에만 session_state로 해당 key를 수정할 수 있음
if st.session_state.reset_ticker_input:
    st.session_state["ticker_input_widget"] = ""  # ✅ OK (위젯 생성 전)
    st.session_state.reset_ticker_input = False

# ── 사이드바 ─────────────────────────────────────────────────────────────
st.sidebar.image("https://img.icons8.com/fluency/96/000000/financial-analyst.png", width=80)
st.sidebar.title("퀀톡 v1.5")

ticker_input = st.sidebar.text_input(
    "종목 티커 입력 (예: 005930, AAPL)",
    key="ticker_input_widget",
    placeholder="입력 후 엔터",
).strip().upper()

# ✅ 자동 이동은 "메인 페이지에서만" 실행 (상세→메인 복귀 시 튕김 방지)
if st.session_state.page == "main":
    if ticker_input and st.session_state.ticker != ticker_input:
        st.session_state.page = "detail"
        st.session_state.ticker = ticker_input
        st.rerun()

# '종목 분석하기' 버튼 로직
if st.sidebar.button("종목 분석하기", type="primary"):
    if ticker_input:
        st.session_state.page = "detail"
        st.session_state.ticker = ticker_input
        st.rerun()

# ── 메인 대시보드 ─────────────────────────────────────────────────────────
if st.session_state.page == "main":
    st.title("실시간 시장 대시보드")

    # 주요 지수
    cols = st.columns(4)
    indices = {"나스닥": "^IXIC", "다우": "^DJI", "S&P500": "^GSPC", "공포지수(VIX)": "^VIX"}
    for col, (name, sym) in zip(cols, indices.items()):
        data = get_index_data(sym)
        if data:
            col.metric(name, f"{data['price']:,.2f}", f"{data['change']:+.2f}%")

    # 환율 & 비트코인
    col5, col6 = st.columns(2)
    krw = get_index_data("KRW=X")
    btc = get_index_data("BTC-USD")
    col5.metric(
        "USD/KRW",
        f"{krw['price']:,.0f}원" if krw else "N/A",
        f"{krw['change']:+.2f}%" if krw else ""
    )
    col6.metric(
        "비트코인",
        f"${btc['price']:,.0f}" if btc else "N/A",
        f"{btc['change']:+.2f}%" if btc else ""
    )

    # 금주 일정
    st.subheader("금주 주요 경제 일정")
    events = pd.DataFrame([
        {"날짜": "2025-12-11", "국가": "미국", "지표": "CPI 발표", "중요도": "★★★"},
        {"날짜": "2025-12-12", "국가": "한국", "지표": "금리 결정", "중요도": "★★★"},
        {"날짜": "2025-12-13", "국가": "유로존", "지표": "ECB 금리", "중요도": "★★"},
    ])
    st.dataframe(events, width="stretch", hide_index=True)

    # 실시간 뉴스
    st.subheader("실시간 시장 뉴스")
    with st.spinner("뉴스 불러오는 중..."):
        news_list = get_market_news_with_sentiment(limit=12)

    for item in news_list:
        icon = "🟢" if item.get("sentiment", 0) > 0.05 else "🔴" if item.get("sentiment", 0) < -0.05 else "⚪"
        st.markdown(f"{icon} **{item.get('title', '제목 없음')}**")
        st.caption(f"{item.get('source', '퀀톡')} · {item.get('time_ago', '방금 전')}")

    # 챗봇
    st.subheader("AI 금융 비서")
    if prompt := st.chat_input("시장이나 종목에 대해 물어보세요"):
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("생각 중..."):
                resp = chatbot_response(prompt)
            st.write(resp)

# ── 종목 상세 대시보드 ───────────────────────────────────────────────────
else:
    ticker = st.session_state.ticker
    st.title(f"{ticker} · 종목 상세 분석")

    # 데이터 로딩
    with st.spinner(f"{ticker} 데이터 불러오는 중..."):
        data = get_stock_detail(ticker)

    if not data:
        st.error(f"[{ticker}] 종목을 찾을 수 없습니다.")
        if st.button("메인으로 돌아가기"):
            st.session_state.page = "main"
            st.session_state.ticker = ""
            st.session_state.reset_ticker_input = True  # ✅
            st.rerun()
        st.stop()

    df = data["history"]
    info = data["info"]

    # 기본 정보
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("현재가", f"{info['price']:,.0f}원")
    c2.metric("등락률", f"{info['change_pct']:+.2f}%", f"{info['change']:+,.0f}원")
    c3.metric("거래량", f"{info['volume']:,.0f}")
    mc = info.get("marketCap", 0)
    c4.metric("시가총액", f"{mc/1e12:.2f}조" if mc else "N/A")

    # 캔들차트
    fig = go.Figure(data=[
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
        )
    ])
    fig.update_layout(title=f"{ticker} 주가 차트 (6개월)", height=600)
    st.plotly_chart(fig, width="stretch")

    # 기술 지표
    st.subheader("주요 기술 지표")
    try:
        indicators = calculate_indicators(df)
        ind_df = pd.DataFrame(indicators.items(), columns=["지표", "값"])
        ind_df["해석"] = ind_df["지표"].apply(lambda x: interpret_indicator(x, indicators[x]))
        st.dataframe(ind_df.style.format({"값": "{:.4f}"}), width="stretch")
    except Exception as e:
        st.warning(f"지표 계산 오류: {e}")

    # 뉴스
    st.subheader(f"{ticker} 최근 뉴스")
    with st.spinner("뉴스 불러오는 중..."):
        news_list = get_market_news_with_sentiment(ticker=ticker, limit=10)

    for item in news_list:
        icon = "🟢" if item.get("sentiment", 0) > 0.05 else "🔴" if item.get("sentiment", 0) < -0.05 else "⚪"
        st.markdown(f"{icon} **{item.get('title', '제목 없음')}**")
        st.caption(f"{item.get('source', '퀀톡')} · {item.get('time_ago', '방금 전')}")

    # 워드클라우드
    st.subheader("금일 키워드 클라우드")
    wc = get_wordcloud_base64(ticker)
    if wc:
        st.image(wc, width=700)
    else:
        st.info("오늘 뉴스가 부족해요")

    # 투자 매력도
    st.subheader("AI 종합 투자 매력도")
    score = 50
    if "indicators" in locals():
        rsi = indicators.get("RSI", 50)
        if rsi < 30:
            score += 25
        if rsi > 70:
            score -= 25
        if indicators.get("MACD_hist", 0) > 0:
            score += 15
        if indicators.get("BB_Position", 0.5) < 0.2:
            score += 15
        if indicators.get("GoldenCross", False):
            score += 20

    score = max(0, min(100, score))
    st.progress(score / 100)
    level = ["강력 매도", "매도", "관망", "매수", "강력 매수"][min(score // 20, 4)]
    st.markdown(f"### **{score}점 → {level}**")

    # 챗봇
    st.subheader(f"{ticker} 전용 AI 비서")
    if prompt := st.chat_input(f"{ticker}에 대해 물어보세요"):
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            resp = chatbot_response(f"종목: {ticker}\n{prompt}")
            st.write(resp)

    # 하단 '메인 시장 대시보드로 돌아가기' 버튼
    st.markdown("---")
    if st.button("메인 시장 대시보드로 돌아가기", key="bottom_back_button", type="secondary"):
        st.session_state.page = "main"
        st.session_state.ticker = ""
        st.session_state.reset_ticker_input = True  # ✅ 다음 run에서 입력칸 비움
        st.rerun()