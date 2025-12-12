import pandas as pd
import numpy as np

# --- 1. SMA (단순 이동 평균) 함수 직접 구현 ---
def calculate_sma(series, window):
    # Pandas의 rolling().mean()을 사용하여 SMA 계산
    return series.rolling(window=window, min_periods=window).mean()

# --- 2. RSI (상대강도지수) 함수 직접 구현 ---
def calculate_rsi(series, window=14):
    # 가격 변화량 계산
    delta = series.diff()
    # 상승분 (Gain)과 하락분 (Loss) 분리
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # 초기 이동 평균 (SMA 사용)
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()

    # RS 계산
    rs = avg_gain / avg_loss
    
    # RSI 계산 (NaN 값 처리)
    rsi = 100 - (100 / (1 + rs))
    return rsi

# --- 3. MACD (이동평균 수렴/확산 지수) 함수 직접 구현 ---
def calculate_macd(series, fast_period=12, slow_period=26, signal_period=9):
    # MACD 계산 (EMA 대신 단순 이동평균(SMA) 사용. MACD는 보통 EMA를 사용하나, 편의상 SMA로 대체 가능)
    # MACD의 표준은 EMA입니다. 여기서는 구현의 단순화를 위해 SMA를 사용합니다.
    # EMA 구현이 필요하다면: series.ewm(span=period, adjust=False).mean() 사용

    fast_ma = series.ewm(span=fast_period, adjust=False).mean()  # EMA 12일
    slow_ma = series.ewm(span=slow_period, adjust=False).mean()  # EMA 26일

    macd = fast_ma - slow_ma
    macd_signal = macd.ewm(span=signal_period, adjust=False).mean() # MACD Signal
    macd_hist = macd - macd_signal
    
    return macd, macd_signal, macd_hist

# --- 4. Bollinger Bands (볼린저 밴드) 함수 직접 구현 ---
def calculate_bb(series, window=20, num_std=2):
    # 중간 밴드 (SMA 20일)
    mid_band = series.rolling(window=window).mean()
    # 표준 편차 (Std Dev)
    std_dev = series.rolling(window=window).std()
    
    # 상단/하단 밴드
    upper_band = mid_band + (std_dev * num_std)
    lower_band = mid_band - (std_dev * num_std)
    
    return upper_band, mid_band, lower_band

# --- 메인 지표 계산 함수 (기존 구조 유지) ---
def calculate_indicators(df):
    close = df['Close']
    high, low = df['High'], df['Low']
    
    # 1. RSI 계산
    rsi = calculate_rsi(close).iloc[-1]
    
    # 2. MACD 계산
    macd_line, macd_signal, macd_hist = calculate_macd(close)
    
    # 3. BB 계산
    bb_upper, bb_mid, bb_lower = calculate_bb(close)
    
    # 4. SMA 50/200 계산 (Golden/Dead Cross)
    sma50 = calculate_sma(close, window=50)
    sma200 = calculate_sma(close, window=200)

    # BB Position 계산: (현재가 - 하단 밴드) / (상단 밴드 - 하단 밴드)
    bb_pos = (close.iloc[-1] - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1])
    
    return {
        "RSI": rsi,
        "MACD": macd_line.iloc[-1],
        "MACD_signal": macd_signal.iloc[-1],
        "MACD_hist": macd_hist.iloc[-1],
        "BB_Position": bb_pos,
        "GoldenCross": sma50.iloc[-1] > sma200.iloc[-1] if not pd.isna(sma50.iloc[-1]) and not pd.isna(sma200.iloc[-1]) else False
    }

# --- 해석 함수 (변경 없음) ---
def interpret_indicator(name, value):
    interp = {
        "RSI": "과매도" if value < 30 else "과매수" if value > 70 else "중립",
        "MACD_hist": "매수 신호" if value > 0 else "매도 신호",
        "BB_Position": "하단 근접(저가)" if value < 0.2 else "상단 근접(고가)" if value > 0.8 else "중간",
        "GoldenCross": "골든크로스 발생!" if value else "데드크로스 상태"
    }
    return interp.get(name, "분석 중")