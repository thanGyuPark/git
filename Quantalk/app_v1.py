import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from dotenv import load_dotenv

# =========================
# utils
# =========================
try:
    load_dotenv()
    from utils.data_fetcher import get_index_data, get_stock_detail
    from utils.indicators import calculate_indicators, interpret_indicator
    from utils.sentiment import get_wordcloud_base64, get_market_news_with_sentiment
    from utils.chatbot import chatbot_response
except Exception as e:
    st.error(f"utils 모듈 오류: {e}")
    st.stop()

# =========================
# Page
# =========================
st.set_page_config(page_title="퀀톡 - AI 금융 대시보드", layout="wide", page_icon="📈")

# =========================
# Session / Navigation (Sidebar)
# =========================
if "page" not in st.session_state:
    st.session_state.page = "main"
if "ticker" not in st.session_state:
    st.session_state.ticker = ""
if "reset_ticker_input" not in st.session_state:
    st.session_state.reset_ticker_input = False

if st.session_state.reset_ticker_input:
    st.session_state["ticker_input_widget"] = ""
    st.session_state.reset_ticker_input = False

st.sidebar.image("https://img.icons8.com/fluency/96/000000/financial-analyst.png", width=80)
st.sidebar.title("퀀톡 v1.5")

ticker_input = st.sidebar.text_input(
    "종목 티커 입력 (예: 005930, AAPL)",
    key="ticker_input_widget",
    placeholder="입력 후 엔터",
).strip().upper()

if st.session_state.page == "main":
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
    if st.sidebar.button("← 메인으로", type="secondary"):
        st.session_state.page = "main"
        st.session_state.ticker = ""
        st.session_state.reset_ticker_input = True
        st.rerun()

# =========================
# CSS (Glass cards)
# =========================
st.markdown(
    """
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
  padding: 14px 14px 12px 14px;
  margin-bottom: 12px;
}
.card-title {
  font-size: 14px;
  font-weight: 800;
  color: rgba(10, 20, 30, 0.80);
  margin-bottom: 8px;
}
.kpi-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}
.kpi-name { font-size: 12px; font-weight: 700; color: rgba(10,20,30,0.60); }
.kpi-price { font-size: 16px; font-weight: 900; color: rgba(10,20,30,0.85); }
.kpi-chg { font-size: 12px; font-weight: 800; }
.kpi-pos { color: rgba(0,150,80,0.95); }
.kpi-neg { color: rgba(220,60,60,0.95); }
.kpi-flat { color: rgba(90,100,110,0.80); }

.item {
  padding: 10px 10px;
  border-radius: 12px;
  background: rgba(255,255,255,0.50);
  border: 1px solid rgba(255,255,255,0.35);
  margin-bottom: 8px;
}
.item:hover { background: rgba(255,255,255,0.68); }
.item-title { font-size: 13px; font-weight: 800; color: rgba(10,20,30,0.82); }
.item-sub { font-size: 11px; color: rgba(10,20,30,0.55); margin-top: 2px; }

div[data-testid="stPlotlyChart"] > div { border-radius: 14px; overflow: hidden; }
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Helpers / Caches
# =========================
def chg_class(x: float | None):
    if x is None:
        return "kpi-flat"
    if x > 0.05:
        return "kpi-pos"
    if x < -0.05:
        return "kpi-neg"
    return "kpi-flat"

def sparkline_from_series(series: pd.Series) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=series.values,
        mode="lines",
        line=dict(width=2),
        fill="tozeroy",
        hoverinfo="skip",
    ))
    fig.update_layout(
        height=80,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig

@st.cache_data(ttl=60, show_spinner=False)
def fetch_quote(sym: str) -> dict:
    return get_index_data(sym) or {}

@st.cache_data(ttl=3600, show_spinner="S&P500 목록 불러오는 중...")  # 1시간 캐싱
def fetch_sp500_tickers(limit=100):
    # Wikipedia에서 동적으로 S&P500 목록 불러오기
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        sp500_table = pd.read_html(url)[0]
        tickers = sp500_table['Symbol'].tolist()[:limit]  # 성능 위해 제한
        return tickers
    except Exception as e:
        st.warning(f"S&P500 목록 불러오기 실패: {e}. 고정 워치리스트 사용.")
        return ["AAPL","MSFT","NVDA","AMZN","GOOG","META","TSLA","AVGO","ORCL","JPM","V","BRK-B","LLY","XOM","COST","HD","WMT"]

@st.cache_data(ttl=180, show_spinner=False)
def fetch_stock_detail_cached(ticker: str) -> dict | None:
    return get_stock_detail(ticker)

@st.cache_data(ttl=180, show_spinner=False)
def fetch_close_series(ticker: str) -> pd.Series | None:
    data = fetch_stock_detail_cached(ticker)
    if not data or "history" not in data:
        return None
    df = data["history"]
    if df is None or df.empty or "Close" not in df.columns:
        return None
    return df["Close"].tail(60)

@st.cache_data(ttl=180, show_spinner=False)
def fetch_market_items(tickers: list[str]) -> pd.DataFrame:
    rows = []
    for t in tickers:
        try:
            detail = fetch_stock_detail_cached(t)
            if not detail:
                continue
            info = detail.get("info", {}) or {}
            hist = detail.get("history", pd.DataFrame())
            if hist is None or hist.empty:
                continue

            if "change_pct" in info and info["change_pct"] is not None:
                chg = float(info["change_pct"])
            else:
                closes = hist["Close"].dropna()
                if len(closes) < 2:
                    continue
                chg = float((closes.iloc[-1] / closes.iloc[-2] - 1.0) * 100)

            mcap = info.get("marketCap", None)
            size = float(mcap) if mcap else float(max(hist["Close"].iloc[-1], 1.0))

            sector = info.get("sector") or info.get("industry") or "Market"
            rows.append({"sector": sector, "ticker": t, "size": size, "chg": chg})
        except Exception:
            continue

    if not rows:
        return pd.DataFrame(columns=["sector", "ticker", "size", "chg"])
    return pd.DataFrame(rows)

def market_treemap_real(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            height=420,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        return fig

    fig = px.treemap(
        df,
        path=["sector", "ticker"],
        values="size",
        color="chg",
        color_continuous_scale=["#d84a4a", "#f2f2f2", "#18a957"],
        range_color=(-5, 5),
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=420,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False,
    )
    return fig


# =========================
# MAIN PAGE
# =========================
def render_main():
    # TOP: 메인 챗봇 카드
    if "main_chat" not in st.session_state:
        st.session_state.main_chat = [
            {"role": "assistant", "content": "무엇을 도와드릴까요? (예: 오늘 시장 요약 / NVDA 리스크 / 매수 타이밍)"}
        ]

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">AI 금융 비서</div>', unsafe_allow_html=True)

    for m in st.session_state.main_chat:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    user_prompt = st.chat_input("시장/종목 질문을 입력하세요 (메인)", key="main_chat_input")
    if user_prompt:
        st.session_state.main_chat.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.write(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("생각 중..."):
                ans = chatbot_response(user_prompt)
            st.write(ans)

        st.session_state.main_chat.append({"role": "assistant", "content": ans})

    st.markdown("</div>", unsafe_allow_html=True)

    # Layout
    left, center, right = st.columns([0.26, 0.50, 0.24], gap="large")

    # LEFT: 일정 + 한줄 + 메모 + 스파크
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">금주 주요 경제 일정</div>', unsafe_allow_html=True)
        events = pd.DataFrame([
            {"날짜": "2025-12-11", "국가": "미국", "지표": "CPI 발표", "중요도": "★★★"},
            {"날짜": "2025-12-12", "국가": "한국", "지표": "금리 결정", "중요도": "★★★"},
            {"날짜": "2025-12-13", "국가": "유로존", "지표": "ECB 금리", "중요도": "★★"},
        ])
        st.dataframe(events, height=220, width="stretch", hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">오늘 한 줄</div>', unsafe_allow_html=True)
        st.write("• KPI/히트맵/속보는 실시간 반영")
        st.write("• 브리핑 챗봇에서 종목+상황을 붙여 물어봐")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Memo</div>', unsafe_allow_html=True)
        st.text_area("오늘의 메모", value="", height=140, label_visibility="collapsed", key="memo_main")
        st.markdown("</div>", unsafe_allow_html=True)

        focus = "NVDA"
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f'<div class="card-title">{focus}</div>', unsafe_allow_html=True)

        ser = fetch_close_series(focus)
        if ser is not None and not ser.empty:
            st.plotly_chart(
                sparkline_from_series(ser),
                width="stretch",
                config={"displayModeBar": False},
                key="spark_left_nvda"
            )
            st.caption("최근 60거래일 종가 추이")
        else:
            st.caption("가격 시계열을 불러오지 못했습니다.")
        st.markdown("</div>", unsafe_allow_html=True)

    # CENTER: KPI + Heatmap + 브리핑
    with center:
        r1c1, r1c2 = st.columns(2, gap="medium")
        r2c1, r2c2 = st.columns(2, gap="medium")

        kpis = [
            ("S&P 500", "^GSPC", r1c1),
            ("NASDAQ", "^IXIC", r1c2),
            ("TSLA", "TSLA", r2c1),
            ("NVDA", "NVDA", r2c2),
        ]

        for name, sym, col in kpis:
            q = fetch_quote(sym)
            price = q.get("price")
            chg = q.get("change")
            cls = chg_class(float(chg) if chg is not None else None)

            series = fetch_close_series(sym)
            if series is None or series.empty:
                series = fetch_close_series(sym.replace("^", ""))

            safe_sym = sym.replace("^", "").replace("/", "_").replace("=", "_")
            chart_key = f"spark_kpi_{safe_sym}"

            with col:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown(
                    f"""
                    <div class="kpi-row">
                      <div class="kpi-name">{name}</div>
                      <div class="kpi-price">{(float(price) if price is not None else 0):,.2f}</div>
                    </div>
                    <div class="kpi-chg {cls}">{(float(chg) if chg is not None else 0):+,.2f}%</div>
                    """,
                    unsafe_allow_html=True,
                )

                if series is not None and not series.empty:
                    st.plotly_chart(
                        sparkline_from_series(series),
                        width="stretch",
                        config={"displayModeBar": False},
                        key=chart_key
                    )
                else:
                    st.caption("시계열 로딩 실패")

                st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">시장 Heatmap (S&P500 Top 100)</div>', unsafe_allow_html=True)

        sp500_tickers = fetch_sp500_tickers(limit=100)  # 동적 불러오기
        df_heat = fetch_market_items(sp500_tickers)

        st.plotly_chart(
            market_treemap_real(df_heat),
            width="stretch",
            config={"displayModeBar": False},
            key="heatmap_sp500"
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">브리핑 챗봇</div>', unsafe_allow_html=True)

        if "brief_chat" not in st.session_state:
            st.session_state.brief_chat = [
                {"role": "assistant", "content": "브리핑 모드입니다. 예: 'NVDA 오늘 뉴스 3줄 요약 + 리스크/기회 시나리오'"} 
            ]

        market_ctx = get_market_news_with_sentiment(limit=5) or []
        nvda_ctx = get_market_news_with_sentiment(ticker="NVDA", limit=3) or []

        def pack_news_ctx(items, title):
            lines = [f"[{title}]"]
            for it in items:
                lines.append(f"- {it.get('title','')} ({it.get('source','')}, {it.get('time_ago','')})")
            return "\n".join(lines)

        ctx_text = pack_news_ctx(market_ctx, "시장 속보") + "\n\n" + pack_news_ctx(nvda_ctx, "NVDA 뉴스")

        for m in st.session_state.brief_chat:
            with st.chat_message(m["role"]):
                st.write(m["content"])

        brief_prompt = st.chat_input("브리핑 질문 입력 (하단)", key="brief_input")
        if brief_prompt:
            st.session_state.brief_chat.append({"role": "user", "content": brief_prompt})
            with st.chat_message("user"):
                st.write(brief_prompt)

            with st.chat_message("assistant"):
                with st.spinner("브리핑 생성 중..."):
                    full_prompt = (
                        "너는 투자 리서치 애널리스트처럼 답한다.\n"
                        "아래 컨텍스트를 기반으로 '3줄 요약 + 리스크 + 기회 + 체크포인트(조건)' 형식으로 답해라.\n\n"
                        f"{ctx_text}\n\n"
                        f"[질문]\n{brief_prompt}"
                    )
                    ans = chatbot_response(full_prompt)
                st.write(ans)

            st.session_state.brief_chat.append({"role": "assistant", "content": ans})

        st.markdown("</div>", unsafe_allow_html=True)

    # RIGHT: 속보
    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">속보</div>', unsafe_allow_html=True)

        news_list = get_market_news_with_sentiment(limit=10) or []
        for n in news_list:
            s = float(n.get("sentiment", 0) or 0)
            icon = "🟢" if s > 0.05 else "🔴" if s < -0.05 else "⚪"
            st.markdown(
                f"""
                <div class="item">
                  <div class="item-title">{icon} {n.get('title','제목 없음')}</div>
                  <div class="item-sub">{n.get('source','')} · {n.get('time_ago','')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)


# =========================
# DETAIL PAGE
# =========================
def render_detail(ticker: str):
    st.title(f"{ticker} · 종목 상세 분석")

    col_back, _ = st.columns([1, 7])
    with col_back:
        if st.button("← 메인으로", key="detail_back_top", type="secondary"):
            st.session_state.page = "main"
            st.session_state.ticker = ""
            st.session_state.reset_ticker_input = True
            st.rerun()

    with st.spinner(f"{ticker} 데이터 불러오는 중..."):
        data = fetch_stock_detail_cached(ticker)

    if not data:
        st.error(f"[{ticker}] 종목을 찾을 수 없습니다.")
        if st.button("메인으로 돌아가기", key="detail_back_error"):
            st.session_state.page = "main"
            st.session_state.ticker = ""
            st.session_state.reset_ticker_input = True
            st.rerun()
        st.stop()

    df = data.get("history")
    info = data.get("info", {}) or {}

    if df is None or df.empty:
        st.error("가격 히스토리 데이터가 비어있습니다.")
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("현재가", f"{info.get('price', 0):,.0f}원" if info.get("price") is not None else "N/A")
    c2.metric("등락률", f"{info.get('change_pct', 0):+.2f}%", f"{info.get('change', 0):+,.0f}원")
    c3.metric("거래량", f"{info.get('volume', 0):,.0f}")
    mc = info.get("marketCap", 0)
    c4.metric("시가총액", f"{mc/1e12:.2f}조" if mc else "N/A")

    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
    )])
    fig.update_layout(title=f"{ticker} 주가 차트 (6개월)", height=600)

    st.plotly_chart(fig, width="stretch", key=f"detail_candle_{ticker}")

    st.subheader("주요 기술 지표")
    try:
        indicators = calculate_indicators(df)
        ind_df = pd.DataFrame(indicators.items(), columns=["지표", "값"])
        ind_df["해석"] = ind_df["지표"].apply(lambda x: interpret_indicator(x, indicators[x]))
        st.dataframe(ind_df.style.format({"값": "{:.4f}"}), width="stretch")
    except Exception as e:
        st.warning(f"지표 계산 오류: {e}")
        indicators = None

    st.subheader(f"{ticker} 최근 뉴스")
    with st.spinner("뉴스 불러오는 중..."):
        news_list = get_market_news_with_sentiment(ticker=ticker, limit=10) or []
    for item in news_list:
        s = float(item.get("sentiment", 0) or 0)
        icon = "🟢" if s > 0.05 else "🔴" if s < -0.05 else "⚪"
        st.markdown(f"{icon} **{item.get('title', '제목 없음')}**")
        st.caption(f"{item.get('source', '퀀톡')} · {item.get('time_ago', '방금 전')}")

    st.subheader("금일 키워드 클라우드")
    wc = get_wordcloud_base64(ticker)
    if wc:
        st.image(wc, width=700)
    else:
        st.info("오늘 뉴스가 부족해요")

    st.subheader("AI 종합 투자 매력도")
    score = 50
    if indicators:
        rsi = indicators.get("RSI", 50)
        if rsi < 30: score += 25
        if rsi > 70: score -= 25
        if indicators.get("MACD_hist", 0) > 0: score += 15
        if indicators.get("BB_Position", 0.5) < 0.2: score += 15
        if indicators.get("GoldenCross", False): score += 20
    score = max(0, min(100, score))
    st.progress(score / 100)
    level = ["강력 매도", "매도", "관망", "매수", "강력 매수"][min(score // 20, 4)]
    st.markdown(f"### **{score}점 → {level}**")

    st.subheader(f"{ticker} 전용 AI 비서")
    chat_key = f"detail_chat::{ticker}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = [{"role": "assistant", "content": f"{ticker}에 대해 무엇을 도와드릴까요?"}]

    for m in st.session_state[chat_key]:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    if prompt := st.chat_input(f"{ticker}에 대해 물어보세요", key=f"detail_input::{ticker}"):
        st.session_state[chat_key].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("생각 중..."):
                ctx = ""
                if indicators:
                    ctx += f"\n[기술지표]\n{ {k: indicators[k] for k in list(indicators.keys())[:8]} }\n"
                if news_list:
                    ctx += "\n[최근뉴스]\n" + "\n".join([f"- {n.get('title','')}" for n in news_list[:5]])
                full = f"종목: {ticker}\n{ctx}\n\n질문: {prompt}"
                resp = chatbot_response(full)
            st.write(resp)

        st.session_state[chat_key].append({"role": "assistant", "content": resp})

    st.markdown("---")
    if st.button("메인으로 돌아가기", key="detail_back_bottom", type="secondary"):
        st.session_state.page = "main"
        st.session_state.ticker = ""
        st.session_state.reset_ticker_input = True
        st.rerun()


# =========================
# Router
# =========================
if st.session_state.page == "main":
    render_main()
else:
    render_detail(st.session_state.ticker)