#!/usr/bin/env python3
"""
Telegram bot: VN stock scanner (full market) — based on "mua 1"
- Data source: VNDIRECT Open API (legal, no API key)
- Realtime price: last 1‑minute candle at scan time
- History: last 90 daily bars for MA/RSI/HHV/LLV logic
- Parallel fetch for speed; chunk results into 100 symbols per Telegram message
- Shows ALL signals: BuyBreak, BuyNormal, Sell, Short, Cover, Sideway

Run:
  pi                    # Ic            # Icon màu            #            # Icon        # Nhóm MUA THƯỜN        # Nhóm MUA THƯỜNG
        if buy_normal_stocks:
            lines.append("📈 <b>MUA THƯỜNG</b>")
            lines.append("─" * 20)
            display_stocks = buy_normal_stocks[:MAX_PER_GROUP]
            for r in display_stocks:
                lines.append(f"<b>{r['symbol']}</b> • {format_price(r['price'])} • {format_percent(r['pct'])}")
            if len(buy_normal_stocks) > MAX_PER_GROUP:
                lines.append(f"<i>... và {len(buy_normal_stocks) - MAX_PER_GROUP} mã khác</i>")
            lines.append("")    if buy_normal_stocks:
            lines.append("<b>MUA THƯỜNG</b>")
            lines.append("─" * 20)
            for r in buy_normal_stocks:
                lines.append(f"<b>{r['symbol']}</b> • {format_price(r['price'])} • {format_percent(r['pct'])}")
            lines.append("")c cho % thay đổi
            if pct > 2:
                pct_icon = "🟢"
            elif pct > 0:
                pct_icon = "🟡"
            elif pct > -2:
                pct_icon = "🟠"
            else:
                pct_icon = "🔴"
            
            # Format đơn giản: Mã • Giá • % • Tín hiệu
            lines.append(f"📊 <b>{sym}</b> • {price:,.0f}₫ • {pct_icon}<b>{pct:+.2f}%</b>"): Mã • Giá • % • Tín hiệu
            lines.append(f"📊 <b>{sym}</b> • {price:,.0f}₫ • {pct_icon}<b>{pct:+.2f}%</b>")ắc cho % thay đổi
            if pct > 2:
                pct_icon = "🟢"
            elif pct > 0:
                pct_icon = "🟡"
            elif pct > -2:
                pct_icon = "🟠"
            else:
                pct_icon = "🔴" đổi         # Thêm thống kê chi tiết cuối mỗi chunk
        if i == 0:  # Chỉ thêm stats cho chunk đầu tiên
            # Đếm từng loại tín hiệu
            buy_break_count = sum(1 for r in filtered if r["BuyBreak"])
            buy_normal_count = sum(1 for r in filtered if r["BuyNormal"])
            sell_count = sum(1 for r in filtered if r["Sell"])
            other_count = len(filtered) - buy_break_count - buy_normal_count - sell_count
            
            msg += "\n\n📊 <b>THỐNG KÊ TÍN HIỆU</b>"
            msg += f"\n🟢 Mua Break: <b>{buy_break_count}</b> mã"
            msg += f"\n🟡 Mua Thường: <b>{buy_normal_count}</b> mã" 
            msg += f"\n🔴 Bán: <b>{sell_count}</b> mã"
            msg += f"\n⚪ Khác: <b>{other_count}</b> mã"
            msg += f"\n📈 Tổng có tín hiệu: <b>{len(filtered)}</b> mã"
            
            import datetime
            current_time = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
            msg += f"\n🕐 Quét lúc: <i>{current_time}</i>"
            msg += "\n⚠️ <i>Chỉ mang tính chất tham khảo</i>"
            if pct > 2:
                pct_icon = "🟢"
            elif pct > 0:
                pct_icon = "🟡"
            elif pct > -2:
                pct_icon = "🟠"
            else:
                pct_icon = "🔴"o % thay đổi đơn giản
            if pct > 2:
                pct_icon = "🟢"
            elif pct > 0:
                pct_icon = "🟡"
            elif pct > -2:
                pct_icon = "🟠"
            else:
                pct_icon = "🔴"requirements.txt
  (requirements.txt should contain: requests pandas numpy python-telegram-bot==21.4 python-dotenv)
  Create .env with TELEGRAM_BOT_TOKEN=...
  python app.py
"""
from __future__ import annotations
import os, io, sys, time, math, json, datetime as dt
import asyncio
import concurrent.futures as futures
from dataclasses import dataclass
from typing import List, Dict, Tuple

import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

# ---- Windows asyncio fix ----

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

# =====================
# Config
# =====================
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 30))  # Về như cũ
DAILY_LOOKBACK_DAYS = 120   # for MA30/RSI
INTRADAY_MINUTES = 1        # resolution for realtime price
CHUNK_SIZE = 100            # symbols per Telegram message
REQUEST_TIMEOUT = 45        # Về như cũ

# VNDIRECT endpoints
FINFO_STOCKS = "https://api.vndirect.com.vn/v4/stocks"
DCHART = "https://dchart-api.vndirect.com.vn/dchart/history"

@dataclass
class SymbolInfo:
    code: str
    floor: str  # HOSE/HNX/UPCOM

# =====================
# Math helpers
# =====================
def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n, min_periods=1).mean()

def hhv(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n, min_periods=1).max()

def llv(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n, min_periods=1).min()

def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    up = np.where(delta > 0, delta, 0.0)
    down = np.where(delta < 0, -delta, 0.0)
    ru = pd.Series(up, index=close.index).rolling(n, min_periods=1).mean()
    rd = pd.Series(down, index=close.index).rolling(n, min_periods=1).mean()
    rs = ru / rd.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(0)

def ema(series: pd.Series, n: int) -> pd.Series:
    """Exponential Moving Average"""
    return series.ewm(span=n, adjust=False).mean()

# =====================
# Data fetchers
# =====================

def fetch_all_symbols() -> List[SymbolInfo]:
    """Đọc danh sách mã từ file symbols.json (cache tĩnh, không cần API)."""
    try:
        with open("symbols.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            raise ValueError("File symbols.json phải chứa một array")
        
        symbols = []
        for item in data:
            if not isinstance(item, dict) or "code" not in item:
                print(f"⚠️ Bỏ qua item không hợp lệ: {item}")
                continue
            symbols.append(SymbolInfo(code=item["code"], floor=item.get("floor", "")))
        
        print(f"✅ Đã load {len(symbols)} symbols từ file")
        return symbols
        
    except FileNotFoundError:
        raise RuntimeError("❌ Không tìm thấy file symbols.json")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"❌ File symbols.json có lỗi format: {e}")
    except Exception as e:
        raise RuntimeError(f"❌ Lỗi đọc symbols.json: {e}")


def dchart_history(symbol: str, resolution: str, since_epoch: int, to_epoch: int) -> pd.DataFrame:
    """
    Lấy dữ liệu lịch sử giá từ VNDIRECT DChart API (hợp pháp).
    Đã thêm header User-Agent và cơ chế retry để tránh lỗi 403 / timeout.
    """
    params = {
        "symbol": symbol,
        "resolution": resolution,
        "from": since_epoch,
        "to": to_epoch
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://dchart.vndirect.com.vn/",
        "Origin": "https://dchart.vndirect.com.vn",
        "Connection": "keep-alive",
    }

    # Thử lại tối đa 3 lần nếu gặp lỗi kết nối hoặc 403
    for attempt in range(3):
        try:
            r = requests.get(
                DCHART,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            if r.status_code == 403:
                print(f"⚠️ 403 Forbidden khi tải {symbol} (lần {attempt+1}/3), thử lại...")
                time.sleep(2)
                continue
            r.raise_for_status()
            js = r.json()
            if not js or "t" not in js or not js["t"]:
                return pd.DataFrame()
            df = pd.DataFrame({
                "t": js.get("t", []),
                "o": js.get("o", []),
                "h": js.get("h", []),
                "l": js.get("l", []),
                "c": js.get("c", []),
                "v": js.get("v", []),
            })
            df["date"] = pd.to_datetime(df["t"], unit="s").dt.tz_localize(None)
            df = df.rename(columns={"o": "O", "h": "H", "l": "L", "c": "C", "v": "V"})
            df = df[["date", "O", "H", "L", "C", "V"]].dropna().sort_values("date").reset_index(drop=True)
            # Set date làm index để chart hiển thị đúng
            df = df.set_index("date")
            return df

        except requests.exceptions.RequestException as e:
            print(f"⚠️ Lỗi khi tải {symbol} (lần {attempt+1}/3): {e}")
            time.sleep(2)
            continue

    print(f"❌ Không thể tải dữ liệu cho {symbol} sau 3 lần thử.")
    return pd.DataFrame()


def fetch_symbol_bundle(sym: str) -> dict:
    """Fetches both DAILY (for indicators) and 1-min latest (for realtime price) for a symbol."""
    now = int(time.time())
    day_from = int((dt.datetime.utcnow() - dt.timedelta(days=DAILY_LOOKBACK_DAYS+10)).timestamp())
    # Daily history for indicators
    daily = dchart_history(sym, "D", day_from, now)
    if daily.empty or len(daily) < 40:
        return {"symbol": sym, "error": "no_daily"}
    # Intraday latest candle (1 minute) for realtime price
    min_from = int((dt.datetime.utcnow() - dt.timedelta(hours=2)).timestamp())
    intr = dchart_history(sym, str(INTRADAY_MINUTES), min_from, now)
    last_price = None
    if not intr.empty:
        last_price = float(intr["C"].iloc[-1])
    else:
        # fallback to latest daily close
        last_price = float(daily["C"].iloc[-1])
    # yesterday close for pct change
    if len(daily) >= 2:
        prev_close = float(daily["C"].iloc[-2])
    else:
        prev_close = float(daily["C"].iloc[-1])
    pct = None
    if prev_close and prev_close > 0:
        pct = (last_price / prev_close - 1.0) * 100.0
    else:
        pct = 0.0
    return {"symbol": sym, "daily": daily, "price": last_price, "pct": pct}

# =====================
# Filters (mua 1)
# =====================

def apply_filters(daily: pd.DataFrame) -> Dict[str, bool]:
    C,H,L,O,V = [daily[x] for x in ["C","H","L","O","V"]]
    MA30 = sma(C, 30)
    RSI14 = rsi(C, 14)
    HHV5, HHV15 = hhv(C,5), hhv(C,15)
    LLV10 = llv(C,10)
    MAV15, MAV50 = sma(V,15), sma(V,50)

    # Điều kiện nền tăng (theo bộ lọc chuẩn MUA 1)
    base = (
        (C >= C.shift(1)) & (C >= C.shift(2)) & (C >= C.shift(3)) & (C >= C.shift(4)) &  # Giá hiện tại ≥ TẤT CẢ 4 phiên trước
        (C > MA30) &         # Giá > MA30
        (C.shift(1) < 1.04 * C.shift(2))  # Ngày hôm qua không tăng quá 4%
    )
    # Điều kiện phá đỉnh ngắn hạn
    breakout = (HHV5 >= HHV15) & (C > 1.01 * C.shift(1))

    # 1. Mua Breakout = Nền tăng + Phá đỉnh
    mua_break = bool(base.iloc[-1] and breakout.iloc[-1])
    
    # 2. Mua Thường = Nền tăng + Không phá đỉnh
    mua_thuong = bool(base.iloc[-1] and (not breakout.iloc[-1]))

    # 3. Bán (Sell): Giá đóng cửa ≤ đáy của 8 phiên liên tiếp
    LLV8 = llv(C, 8)
    ban = bool((C <= LLV8).iloc[-1])

    # 4. Short: Giá giảm liên tục 4 ngày HOẶC giá ≤ 95% đỉnh gần nhất + điều kiện kỹ thuật
    giam_lien_tuc_4_ngay = (
        (C < C.shift(1)) & (C.shift(1) < C.shift(2)) & 
        (C.shift(2) < C.shift(3)) & (C.shift(3) < C.shift(4))
    )
    gia_duoi_95_dinh = C <= 0.95 * hhv(H, 20)  # đỉnh 20 phiên gần nhất
    short = bool((
        (giam_lien_tuc_4_ngay | gia_duoi_95_dinh) & 
        ((C * V) >= 1_000_000) & (C >= 5)
    ).iloc[-1])

    # 5. Cover: Phục hồi sau nhịp giảm với thanh khoản tốt
    cover = bool((
        (C > 1.02 * H.shift(1)) & (C >= H.shift(2)) &
        ((V >= 1.3 * MAV15) | (V >= 1.3 * MAV50)) &
        (C > O) & (C > MA30) & ((C * V) >= 1_000_000) & (C >= 5) &
        (C < 1.15 * LLV10)  # Không quá nóng
    ).iloc[-1])

    # 6. Sideway: Thị trường đi ngang chặt, chuẩn bị bứt phá
    bien_do_5_ngay = (hhv(H, 5) - llv(L, 5)) / llv(L, 5)
    bien_do_10_ngay = (hhv(H, 10) - llv(L, 10)) / llv(L, 10)
    sideway = bool((
        (bien_do_5_ngay <= 0.10) & (bien_do_10_ngay <= 0.15) &  # Biên độ hẹp
        (C >= 5) & (C <= 200) &  # Vùng giá hợp lý
        ((C * V) >= 1_000_000) & (MAV15 > 50_000) &  # Thanh khoản tốt
        (C > MA30) &  # Trên MA30
        (RSI14 >= 53) & (RSI14 <= 60) &  # RSI trong vùng trung tính tích cực
        (C >= 1.01 * C.shift(1))  # Hôm nay tăng nhẹ
    ).iloc[-1])

    return {
        "BuyBreak": mua_break,
        "BuyNormal": mua_thuong,
        "Sell": ban,
        "Short": short,
        "Cover": cover,
        "Sideway": sideway,
    }

# =====================
# Bộ Lọc MUA SỊN (Hoàn toàn mới - độc lập)
# =====================

def apply_filters_sin(daily: pd.DataFrame) -> Dict[str, bool]:
    """
    Bộ lọc MUA SỊN - Logic riêng theo yêu cầu user:
    
    Phiên hiện tại:
    - Giá cao nhất trong phiên >= giá cao nhất 4 phiên trước * 99%
    - Tại thời điểm quét, giá dương (không âm)
    
    Phiên trước:
    - Nến đỏ (C < O), giảm không quá 2%
    - Volume < Volume MA20
    
    Điều kiện chung:
    - Nằm trên EMA 34
    """
    if len(daily) < 40:  # Cần đủ dữ liệu
        return {"BuySin": False}
    
    C, H, L, O, V = [daily[x] for x in ["C", "H", "L", "O", "V"]]
    
    # Tính toán các chỉ báo cần thiết
    EMA34 = ema(C, 34)
    VOL_MA20 = sma(V, 20)
    
    # === ĐIỀU KIỆN PHIÊN HIỆN TẠI (phiên cuối - index -1) ===
    # 1. Giá cao nhất hiện tại >= giá cao nhất 4 phiên trước * 99%
    h_current = H.iloc[-1]  # Giá cao nhất phiên hiện tại
    h_4_sessions_ago = H.iloc[-5]  # Giá cao nhất 4 phiên trước
    condition_high = h_current >= (h_4_sessions_ago * 0.99)
    
    # 2. Giá hiện tại dương (so với phiên trước)
    c_current = C.iloc[-1]  # Giá đóng cửa hiện tại
    c_previous = C.iloc[-2]  # Giá đóng cửa phiên trước
    condition_positive = c_current > c_previous
    
    # === ĐIỀU KIỆN PHIÊN TRƯỚC (index -2) ===
    # 3. Nến đỏ (C < O) phiên trước
    c_prev = C.iloc[-2]
    o_prev = O.iloc[-2] 
    condition_red_candle = c_prev < o_prev
    
    # 4. Giảm không quá 2% phiên trước
    c_before_prev = C.iloc[-3]  # Giá đóng cửa 2 phiên trước
    pct_change_prev = (c_prev / c_before_prev - 1) * 100
    condition_down_max_2pct = -2 <= pct_change_prev < 0
    
    # 5. Volume phiên trước < Volume MA20
    v_prev = V.iloc[-2]
    vol_ma20_prev = VOL_MA20.iloc[-2]
    condition_low_volume = v_prev < vol_ma20_prev
    
    # === ĐIỀU KIỆN CHUNG ===
    # 6. Giá hiện tại nằm trên EMA 34
    ema34_current = EMA34.iloc[-1]
    condition_above_ema34 = c_current > ema34_current
    
    # === KẾT HỢP TẤT CẢ ĐIỀU KIỆN ===
    mua_sin = bool(
        condition_high and          # H hiện tại >= H[-4] * 99%
        condition_positive and      # Giá hiện tại dương
        condition_red_candle and    # Nến đỏ phiên trước
        condition_down_max_2pct and # Giảm không quá 2% phiên trước
        condition_low_volume and    # Volume thấp phiên trước
        condition_above_ema34       # Nằm trên EMA34
    )
    
    return {
        "BuySin": mua_sin,
        # Debug thông tin (có thể bỏ comment để debug)
        # "debug_high": condition_high,
        # "debug_positive": condition_positive, 
        # "debug_red": condition_red_candle,
        # "debug_down2pct": condition_down_max_2pct,
        # "debug_lowvol": condition_low_volume,
        # "debug_ema34": condition_above_ema34,
    }

# =====================
# Bộ Lọc MUA SỊN 2 (Hoàn toàn mới - độc lập)
# =====================

def apply_filters_sin2(daily: pd.DataFrame) -> Dict[str, bool]:
    """
    Bộ lọc MUA SỊN 2 - Logic theo yêu cầu user:
    
    Phiên hiện tại:
    - Không thấp hơn 4 phiên trước
    - Giá hiện tại dương (tăng)
    - Giá tăng không quá 3%
    
    Phiên trước:
    - Giảm không quá 3%
    
    Điều kiện chung:
    - Giá nằm trên EMA 34 và EMA 89 và MA 50
    """
    if len(daily) < 90:  # Cần đủ dữ liệu cho EMA 89
        return {"BuySin2": False}
    
    C, H, L, O, V = [daily[x] for x in ["C", "H", "L", "O", "V"]]
    
    # Tính toán các chỉ báo cần thiết
    EMA34 = ema(C, 34)
    EMA89 = ema(C, 89)
    MA50 = sma(C, 50)
    
    # === ĐIỀU KIỆN PHIÊN HIỆN TẠI (phiên cuối - index -1) ===
    c_current = C.iloc[-1]  # Giá đóng cửa hiện tại
    c_4_sessions_ago = C.iloc[-5]  # Giá đóng cửa 4 phiên trước
    c_previous = C.iloc[-2]  # Giá đóng cửa phiên trước
    
    # 1. Không thấp hơn 4 phiên trước
    condition_not_lower_than_4sessions = c_current >= c_4_sessions_ago
    
    # 2. Giá hiện tại dương (tăng so với phiên trước)
    condition_positive_current = c_current > c_previous
    
    # 3. Giá tăng không quá 3%
    pct_change_current = (c_current / c_previous - 1) * 100
    condition_increase_max_3pct = 0 < pct_change_current <= 3
    
    # === ĐIỀU KIỆN PHIÊN TRƯỚC (index -2) ===
    c_prev = C.iloc[-2]
    c_before_prev = C.iloc[-3]  # Giá đóng cửa 2 phiên trước
    
    # 4. Giảm không quá 3% phiên trước
    pct_change_prev = (c_prev / c_before_prev - 1) * 100
    condition_decrease_max_3pct = -3 <= pct_change_prev < 0
    
    # === ĐIỀU KIỆN CHUNG ===
    # 7. Giá hiện tại nằm trên EMA 34, EMA 89 và MA 50
    ema34_current = EMA34.iloc[-1]
    ema89_current = EMA89.iloc[-1]
    ma50_current = MA50.iloc[-1]
    
    condition_above_ema34 = c_current > ema34_current
    condition_above_ema89 = c_current > ema89_current
    condition_above_ma50 = c_current > ma50_current
    
    # === KẾT HỢP TẤT CẢ ĐIỀU KIỆN ===
    mua_sin2 = bool(
        condition_not_lower_than_4sessions and  # Không thấp hơn 4 phiên trước
        condition_positive_current and          # Giá hiện tại dương
        condition_increase_max_3pct and         # Tăng không quá 3%
        condition_decrease_max_3pct and         # Giảm không quá 3% phiên trước
        condition_above_ema34 and               # Nằm trên EMA34
        condition_above_ema89 and               # Nằm trên EMA89
        condition_above_ma50                    # Nằm trên MA50
    )
    
    return {
        "BuySin2": mua_sin2,
        # Debug thông tin (có thể bỏ comment để debug)
        # "debug_not_lower_4": condition_not_lower_than_4sessions,
        # "debug_positive": condition_positive_current,
        # "debug_increase_3pct": condition_increase_max_3pct,
        # "debug_decrease_3pct": condition_decrease_max_3pct,
        # "debug_ema34": condition_above_ema34,
        # "debug_ema89": condition_above_ema89,
        # "debug_ma50": condition_above_ma50,
    }

def apply_filters_sin3(daily: pd.DataFrame) -> Dict[str, bool]:
    """
    Bộ lọc MUA SỊN 3 - Logic mới theo yêu cầu:
    
    Phiên hiện tại:
    - Giá dương, tăng không quá 3%
    - Giá không thấp hơn giá thấp nhất 4 phiên gần nhất
    
    Phiên trước:
    - Giá đóng cửa giảm không quá 3%, tăng không quá 3%
    
    Điều kiện chung:
    - Giá nằm trên EMA34, EMA89 và MA50
    """
    if len(daily) < 90:  # Cần đủ dữ liệu cho EMA89
        return {"BuySin3": False}
    
    C, H, L, O, V = [daily[x] for x in ["C", "H", "L", "O", "V"]]
    
    # Tính toán các chỉ báo cần thiết
    EMA34 = ema(C, 34)
    EMA89 = ema(C, 89)
    MA50 = sma(C, 50)
    
    # === ĐIỀU KIỆN PHIÊN HIỆN TẠI (phiên cuối - index -1) ===
    c_current = C.iloc[-1]  # Giá đóng cửa hiện tại
    c_previous = C.iloc[-2]  # Giá đóng cửa phiên trước
    l_current = L.iloc[-1]  # Giá thấp nhất hiện tại
    
    # 1. Giá dương, tăng không quá 3%
    pct_change_current = (c_current / c_previous - 1) * 100
    condition_positive_max_3pct = 0 < pct_change_current <= 3
    
    # 2. Giá không thấp hơn giá thấp nhất 4 phiên gần nhất
    l_recent_4 = L.iloc[-4:].min()  # Giá thấp nhất trong 4 phiên gần nhất
    condition_above_low_4sessions = l_current >= l_recent_4
    
    # === ĐIỀU KIỆN PHIÊN TRƯỚC (index -2) ===
    c_prev = C.iloc[-2]  # Giá đóng cửa phiên trước
    c_before_prev = C.iloc[-3]  # Giá đóng cửa 2 phiên trước
    
    # 3. Giá đóng cửa phiên trước: giảm không quá 3%, tăng không quá 3%
    pct_change_prev = (c_prev / c_before_prev - 1) * 100
    condition_prev_range_3pct = -3 <= pct_change_prev <= 3
    
    # === ĐIỀU KIỆN CHUNG ===
    # 4. Giá hiện tại nằm trên EMA34, EMA89 và MA50
    ema34_current = EMA34.iloc[-1]
    ema89_current = EMA89.iloc[-1] 
    ma50_current = MA50.iloc[-1]
    
    condition_above_ema34 = c_current > ema34_current
    condition_above_ema89 = c_current > ema89_current
    condition_above_ma50 = c_current > ma50_current
    
    # === KẾT HỢP TẤT CẢ ĐIỀU KIỆN ===
    mua_sin3 = bool(
        condition_positive_max_3pct and        # Tăng dương không quá 3%
        condition_above_low_4sessions and      # Không thấp hơn thấp nhất 4 phiên
        condition_prev_range_3pct and          # Phiên trước trong khoảng ±3%
        condition_above_ema34 and              # Trên EMA34
        condition_above_ema89 and              # Trên EMA89
        condition_above_ma50                   # Trên MA50
    )
    
    return {
        "BuySin3": mua_sin3,
        # Debug thông tin (có thể bỏ comment để debug)
        # "debug_positive_max_3pct": condition_positive_max_3pct,
        # "debug_above_low_4sessions": condition_above_low_4sessions,
        # "debug_prev_range_3pct": condition_prev_range_3pct,
        # "debug_above_ema34": condition_above_ema34,
        # "debug_above_ema89": condition_above_ema89,
        # "debug_above_ma50": condition_above_ma50,
    }

def fetch_symbol_bundle_sin2(sym: str) -> dict:
    """Fetch data cho bộ lọc Mua Sịn 2 (tương tự fetch_symbol_bundle)"""
    now = int(time.time())
    day_from = int((dt.datetime.utcnow() - dt.timedelta(days=DAILY_LOOKBACK_DAYS+10)).timestamp())
    
    # Daily history for indicators
    daily = dchart_history(sym, "D", day_from, now)
    if daily.empty or len(daily) < 90:  # Cần nhiều data hơn cho EMA 89
        return {"symbol": sym, "error": "no_daily"}
    
    # Intraday latest candle for realtime price
    min_from = int((dt.datetime.utcnow() - dt.timedelta(hours=2)).timestamp())
    intr = dchart_history(sym, str(INTRADAY_MINUTES), min_from, now)
    last_price = None
    if not intr.empty:
        last_price = float(intr["C"].iloc[-1])
    else:
        last_price = float(daily["C"].iloc[-1])
    
    # yesterday close for pct change
    if len(daily) >= 2:
        prev_close = float(daily["C"].iloc[-2])
    else:
        prev_close = float(daily["C"].iloc[-1])
    pct = None
    if prev_close and prev_close > 0:
        pct = (last_price / prev_close - 1) * 100
    
    # Apply filters
    filters_result = apply_filters_sin2(daily)
    
    return {
        "symbol": sym,
        "price": last_price,
        "pct": pct,
        **filters_result
    }

def fetch_symbol_bundle_sin3(sym: str) -> dict:
    """Fetch data cho bộ lọc Mua Sịn 3 (tương tự fetch_symbol_bundle)"""
    now = int(time.time())
    day_from = int((dt.datetime.utcnow() - dt.timedelta(days=DAILY_LOOKBACK_DAYS+10)).timestamp())
    
    # Daily history for indicators
    daily = dchart_history(sym, "D", day_from, now)
    if daily.empty or len(daily) < 90:  # Cần đủ data cho EMA89
        return {"symbol": sym, "error": "no_daily"}
    
    # Intraday latest candle for realtime price
    latest = dchart_history(sym, "1", now - 60, now)
    if latest.empty:
        last_price = float(daily["C"].iloc[-1])
    else:
        last_price = float(latest["C"].iloc[-1])
    
    # yesterday close for pct change
    if len(daily) >= 2:
        prev_close = float(daily["C"].iloc[-2])
    else:
        prev_close = float(daily["C"].iloc[-1])
    pct = None
    if prev_close and prev_close > 0:
        pct = (last_price / prev_close - 1) * 100
    
    # Apply filters
    filters_result = apply_filters_sin3(daily)
    
    return {
        "symbol": sym,
        "price": last_price,
        "pct": pct,
        **filters_result
    }

def fetch_symbol_bundle_sin(sym: str) -> dict:
    """Fetch data cho bộ lọc Mua Sịn (tương tự fetch_symbol_bundle)"""
    now = int(time.time())
    day_from = int((dt.datetime.utcnow() - dt.timedelta(days=DAILY_LOOKBACK_DAYS+10)).timestamp())
    
    # Daily history for indicators
    daily = dchart_history(sym, "D", day_from, now)
    if daily.empty or len(daily) < 40:
        return {"symbol": sym, "error": "no_daily"}
    
    # Intraday latest candle for realtime price
    min_from = int((dt.datetime.utcnow() - dt.timedelta(hours=2)).timestamp())
    intr = dchart_history(sym, str(INTRADAY_MINUTES), min_from, now)
    last_price = None
    if not intr.empty:
        last_price = float(intr["C"].iloc[-1])
    else:
        last_price = float(daily["C"].iloc[-1])
    
    # yesterday close for pct change
    if len(daily) >= 2:
        prev_close = float(daily["C"].iloc[-2])
    else:
        prev_close = float(daily["C"].iloc[-1])
    pct = None
    if prev_close and prev_close > 0:
        pct = (last_price / prev_close - 1.0) * 100.0
    else:
        pct = 0.0
    
    return {"symbol": sym, "daily": daily, "price": last_price, "pct": pct}

def scan_symbols_sin(symbols: List[str]) -> List[dict]:
    """Quét thị trường với bộ lọc MUA SỊN"""
    rows: List[dict] = []
    try:
        with futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            future_to_symbol = {ex.submit(fetch_symbol_bundle_sin, symbol): symbol for symbol in symbols}
            
            for future in futures.as_completed(future_to_symbol, timeout=30):  # Về như cũ
                symbol = future_to_symbol[future]
                try:
                    bundle = future.result(timeout=5)  # Về như cũ
                    if "error" in bundle:
                        continue
                    
                    # Áp dụng bộ lọc MUA SỊN
                    signals = apply_filters_sin(bundle["daily"])
                    
                    # Chỉ giữ những mã có tín hiệu
                    if any(signals.values()):
                        row = {
                            "symbol": bundle["symbol"],
                            "price": bundle["price"],
                            "pct": bundle["pct"],
                            **signals
                        }
                        rows.append(row)
                        
                except Exception as e:
                    print(f"❌ Error processing {symbol}: {e}")
                    continue
                    
    except futures.TimeoutError:
        pass  # Timeout là bình thường, không cần thông báo
    except Exception as e:
        print(f"❌ Error in scan_symbols_sin: {e}")
    
    return rows

def scan_symbols_sin2(symbols: List[str]) -> List[dict]:
    """Quét thị trường với bộ lọc MUA SỊN 2"""
    rows: List[dict] = []
    try:
        with futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            future_to_symbol = {ex.submit(fetch_symbol_bundle_sin2, symbol): symbol for symbol in symbols}
            
            for future in futures.as_completed(future_to_symbol, timeout=30):  # Về như cũ
                symbol = future_to_symbol[future]
                try:
                    bundle = future.result(timeout=5)  # Về như cũ
                    if "error" in bundle:
                        continue
                    
                    # Chỉ giữ những mã có tín hiệu BuySin2
                    if bundle.get("BuySin2", False):
                        row = {
                            "symbol": bundle["symbol"],
                            "price": bundle["price"],
                            "pct": bundle["pct"],
                            "BuySin2": bundle["BuySin2"]
                        }
                        rows.append(row)
                        
                except Exception as e:
                    print(f"❌ Error processing {symbol}: {e}")
                    continue
                    
    except futures.TimeoutError:
        pass  # Timeout là bình thường, không cần thông báo
    except Exception as e:
        print(f"❌ Error in scan_symbols_sin2: {e}")
    
    return rows

def scan_symbols_sin3(symbols: List[str]) -> List[dict]:
    """Quét thị trường với bộ lọc MUA SỊN 3"""
    rows: List[dict] = []
    try:
        with futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            future_to_symbol = {ex.submit(fetch_symbol_bundle_sin3, symbol): symbol for symbol in symbols}
            
            for future in futures.as_completed(future_to_symbol, timeout=30):  # Về như cũ
                symbol = future_to_symbol[future]
                try:
                    bundle = future.result(timeout=5)  # Về như cũ
                    if "error" in bundle:
                        continue
                    
                    # Chỉ giữ những mã có tín hiệu BuySin3
                    if bundle.get("BuySin3", False):
                        row = {
                            "symbol": bundle["symbol"],
                            "price": bundle["price"],
                            "pct": bundle["pct"],
                            "BuySin3": bundle["BuySin3"]
                        }
                        rows.append(row)
                        
                except Exception as e:
                    print(f"❌ Error processing {symbol}: {e}")
                    continue
                    
    except futures.TimeoutError:
        pass  # Timeout là bình thường, không cần thông báo
    except Exception as e:
        print(f"❌ Error in scan_symbols_sin3: {e}")
    
    return rows

# =====================
# Orchestrator (Bộ lọc gốc)
# =====================

def scan_symbols(symbols: List[str]) -> List[dict]:
    rows: List[dict] = []
    try:
        with futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            # Sử dụng submit thay vì map để có thể set timeout
            future_to_symbol = {ex.submit(fetch_symbol_bundle, symbol): symbol for symbol in symbols}
            
            for future in futures.as_completed(future_to_symbol, timeout=REQUEST_TIMEOUT * 2):
                try:
                    res = future.result(timeout=REQUEST_TIMEOUT)
                    sym = res.get("symbol")
                    if res.get("error"):
                        continue
                    daily: pd.DataFrame = res["daily"]
                    sigs = apply_filters(daily)
                    rows.append({
                        "symbol": sym,
                        "price": float(res["price"]),
                        "pct": float(res["pct"]),
                        **sigs
                    })
                except futures.TimeoutError:
                    symbol = future_to_symbol[future]
                    print(f"⚠️ Timeout cho symbol {symbol}")
                    continue
                except Exception as e:
                    symbol = future_to_symbol[future]
                    print(f"⚠️ Lỗi xử lý symbol {symbol}: {e}")
                    continue
                    
    except (KeyboardInterrupt, futures.TimeoutError) as e:
        print(f"⚠️ Quá trình quét bị gián đoạn: {e}")
        # Trả về kết quả đã có được
        return rows
    except Exception as e:
        print(f"❌ Lỗi không mong muốn trong scan_symbols: {e}")
        return rows
        
    return rows

# =====================
# Telegram bot
# =====================

# Nút scan cố định với Reply Keyboard
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Tạo nút scan cố định
    keyboard = [
        [KeyboardButton("🔍 Quét Tín Hiệu MUA")],
        [KeyboardButton("🔥 Quét Mua Sịn")],  # Nút mới cho bộ lọc Mua Sịn
        [KeyboardButton("❓ Hướng Dẫn")]
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True,     # Tự động resize
        one_time_keyboard=False   # Không ẩn sau khi bấm
    )
    
    await update.message.reply_text(
        "🤖 **Bot Quét Cổ Phiếu Việt Nam**\n\n"
        "📊 Theo dõi **95 mã cổ phiếu** real-time\n"
        "⚡ Phân tích tín hiệu kỹ thuật tự động\n\n"
        "👇 **Sử dụng nút bên dưới:**\n"
        "🔍 **Quét Tín Hiệu MUA** - Tìm mã có tín hiệu mua\n"
        "❓ **Hướng Dẫn** - Xem cách sử dụng bot",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Xử lý tin nhắn từ Reply Keyboard
async def handle_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🔍 Quét Tín Hiệu MUA":
        await update.message.reply_text("⏳ Đang quét toàn bộ mã, vui lòng chờ...")
        await run_scan_send_result(update.message, context)
    
    elif text == "🔥 Quét Mua Sịn":
        await update.message.reply_text("🔥 Đang quét với bộ lọc MUA SỊN, vui lòng chờ...")
        await run_scan_sin_send_result(update.message, context)
    
    elif text == "❓ Hướng Dẫn":
        await update.message.reply_text(
            "📖 **Hướng dẫn sử dụng Bot**\n\n"
            "🔍 **Nút 'Quét Tín Hiệu MUA':**\n"
            "• Quét tất cả mã cổ phiếu với bộ lọc gốc\n"
            "• Tìm các mã có tín hiệu mua tích cực\n"
            "• Phân tích dựa trên MA30, RSI14, HHV/LLV\n\n"
            "🔥 **Nút 'Quét Mua Sịn':**\n"
            "• Bộ lọc hoàn toàn mới và độc lập\n"
            "• Logic sẽ được cấu hình riêng biệt\n"
            "• Tìm kiếm cơ hội đặc biệt\n\n"
            "📊 **Nguồn dữ liệu:** VNDIRECT API\n"
            "💡 **Hai nút độc lập để dễ sử dụng!**",
            parse_mode='Markdown'
        )

# Xử lý khi nhấn nút (giữ lại cho tương thích)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "scan_mua1":
        await query.edit_message_text("⏳ Đang quét toàn bộ mã, vui lòng chờ...")
        await run_scan_send_result(query.message, context)

# Hàm thực hiện scan và gửi kết quả
async def run_scan_send_result(message_source, context: ContextTypes.DEFAULT_TYPE):
    try:
        syminfo = fetch_all_symbols()
        symbols = [s.code for s in syminfo]
    except Exception as e:
        # Gửi lỗi qua reply_text 
        await message_source.reply_text(f"❌ Lỗi tải danh sách mã: {e}")
        return

    # Gửi thông báo đang quét
    await message_source.reply_text(f"🔄 Đang quét {len(symbols)} mã… (song song {MAX_WORKERS} luồng)")
        
    try:
        rows = scan_symbols(symbols)
        if not rows:
            await message_source.reply_text("⚠️ Quá trình quét bị gián đoạn hoặc không có dữ liệu.")
            return
    except KeyboardInterrupt:
        await message_source.reply_text("⚠️ Quá trình quét bị dừng bởi người dùng.")
        return
    except Exception as e:
        await message_source.reply_text(f"❌ Lỗi khi quét: {e}")
        return

    # Lọc ra những mã có ít nhất 1 tín hiệu
    filtered = []
    buy_signals = 0  # Đếm số tín hiệu mua
    for r in rows:
        # Đếm tín hiệu mua
        if r["BuyBreak"] or r["BuyNormal"]:
            buy_signals += 1
        
        if any([r["BuyBreak"], r["BuyNormal"], r["Sell"], r["Short"], r["Cover"], r["Sideway"]]):
            filtered.append(r)

    if not filtered:
        # Thông báo chi tiết khi không có tín hiệu
        total_scanned = len(rows)
        await message_source.reply_text(
            f"📊 <b>KẾT QUẢ QUÉT CỔ PHIẾU</b>\n"
            f"═══════════════════════════\n\n"
            f"🔍 Đã quét: <b>{total_scanned}</b> mã cổ phiếu\n"
            f"🎯 Tín hiệu MUA: <b>0</b> mã\n"
            f"📈 Tín hiệu khác: <b>0</b> mã\n\n"
            f"💡 <i>Hiện tại thị trường chưa có mã nào thỏa mãn điều kiện tín hiệu.</i>\n"
            f"⏰ Hãy thử lại sau hoặc trong giờ giao dịch.",
            parse_mode="HTML"
        )
        return

    # Chia tách rows theo loại tín hiệu
    buy_break_stocks = [r for r in filtered if r["BuyBreak"]]
    buy_normal_stocks = [r for r in filtered if r["BuyNormal"]]
    sell_stocks = [r for r in filtered if r["Sell"]]
    sideway_stocks = [r for r in filtered if r["Sideway"]]
    other_stocks = [r for r in filtered if r["Short"] or r["Cover"]]

    # Function tạo format mới theo từng nhóm - bỏ ký tự "?" và format giá 18.25k
    def build_grouped_format():
        lines = []
        MAX_PER_GROUP = 15  # Giới hạn tối đa 15 mã mỗi nhóm để tránh tin nhắn quá dài
        
        # Header
        lines.append("<b>🔍 KẾT QUẢ QUÉT CỔ PHIẾU</b>")
        lines.append("═" * 30)
        lines.append("")
        
        # Format giá hiển thị chính xác với phần thập phân
        def format_price(price):
            return f"{price:,.1f}"
        
        # Format % đơn giản không có icon màu
        def format_percent(pct):
            return f"<b>{pct:+.2f}%</b>"
        
        # Nhóm MUA BREAK (ưu tiên cao nhất)
        if buy_break_stocks:
            lines.append("🚀 <b>MUA BREAK</b>")
            lines.append("─" * 20)
            display_stocks = buy_break_stocks[:MAX_PER_GROUP]
            for r in display_stocks:
                lines.append(f"<b>{r['symbol']}</b> • {format_price(r['price'])} • {format_percent(r['pct'])}")
            if len(buy_break_stocks) > MAX_PER_GROUP:
                lines.append(f"<i>... và {len(buy_break_stocks) - MAX_PER_GROUP} mã khác</i>")
            lines.append("")
        
        # Nhóm MUA THƯỜNG
        if buy_normal_stocks:
            lines.append("📈 <b>MUA THƯỜNG</b>")
            lines.append("─" * 20)
            for r in buy_normal_stocks:
                lines.append(f"� <b>{r['symbol']}</b> • {format_price(r['price'])} • {format_percent(r['pct'])}")
            lines.append("")
        
        # Nhóm BÁN (giới hạn ít hơn do ít quan trọng)
        if sell_stocks:
            lines.append("📉 <b>BÁN</b>")
            lines.append("─" * 20)
            display_stocks = sell_stocks[:10]  # Chỉ hiển thị 10 mã bán
            for r in display_stocks:
                lines.append(f"<b>{r['symbol']}</b> • {format_price(r['price'])} • {format_percent(r['pct'])}")
            if len(sell_stocks) > 10:
                lines.append(f"<i>... và {len(sell_stocks) - 10} mã khác</i>")
            lines.append("")
        
        # Nhóm ĐI NGANG (giới hạn ít hơn)
        if sideway_stocks:
            lines.append("↔️ <b>ĐI NGANG</b>")
            lines.append("─" * 20)
            display_stocks = sideway_stocks[:8]  # Chỉ hiển thị 8 mã sideway
            for r in display_stocks:
                lines.append(f"<b>{r['symbol']}</b> • {format_price(r['price'])} • {format_percent(r['pct'])}")
            if len(sideway_stocks) > 8:
                lines.append(f"<i>... và {len(sideway_stocks) - 8} mã khác</i>")
            lines.append("")
        
        # Nhóm KHÁC (giới hạn ít nhất)
        if other_stocks:
            lines.append("⚡ <b>TÍN HIỆU KHÁC</b>")
            lines.append("─" * 20)
            display_stocks = other_stocks[:5]  # Chỉ hiển thị 5 mã khác
            for r in display_stocks:
                signals = []
                if r["Short"]: signals.append("Bán Khống")
                if r["Cover"]: signals.append("Đóng Lệnh")
                signal_text = " • ".join(signals)
                lines.append(f"<b>{r['symbol']}</b> • {format_price(r['price'])} • {format_percent(r['pct'])}")
                lines.append(f"   <i>{signal_text}</i>")
            if len(other_stocks) > 5:
                lines.append(f"<i>... và {len(other_stocks) - 5} mã khác</i>")
            lines.append("")
        
        return "\n".join(lines)

    # Tạo message chính
    msg = build_grouped_format()
    
    # Thêm thống kê chi tiết
    buy_break_count = len(buy_break_stocks)
    buy_normal_count = len(buy_normal_stocks)
    sell_count = len(sell_stocks)
    other_count = len(other_stocks) + len(sideway_stocks)
    
    stats_msg = "\n<b>📊 THỐNG KÊ TÍN HIỆU</b>"
    stats_msg += f"\n🚀 Mua Break: <b>{buy_break_count}</b> mã"
    stats_msg += f"\n📈 Mua Thường: <b>{buy_normal_count}</b> mã"
    stats_msg += f"\n Bán: <b>{sell_count}</b> mã"
    stats_msg += f"\n⚡ Khác: <b>{other_count}</b> mã"
    stats_msg += f"\n🎯 Tổng có tín hiệu: <b>{len(filtered)}</b> mã"
    
    import datetime
    current_time = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    stats_msg += f"\n⏰ Quét lúc: <i>{current_time}</i>"
    stats_msg += "\n<i>📝 Chỉ mang tính chất tham khảo</i>"

    # Kiểm tra độ dài và chia nhỏ tin nhắn nếu cần
    chat_id = message_source.chat_id
    MAX_MESSAGE_LENGTH = 4000  # Giới hạn an toàn, dưới 4096 của Telegram
    
    full_msg = msg + stats_msg
    
    if len(full_msg) <= MAX_MESSAGE_LENGTH:
        # Tin nhắn đủ ngắn, gửi một lần
        await context.bot.send_message(
            chat_id=chat_id,
            text=full_msg,
            parse_mode="HTML"
        )
    else:
        # Tin nhắn quá dài, chia thành 2 phần
        await context.bot.send_message(
            chat_id=chat_id,
            text=msg,  # Gửi kết quả trước
            parse_mode="HTML"
        )
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=stats_msg,  # Gửi thống kê sau
            parse_mode="HTML"
        )

    # Gửi thông báo hoàn tất
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ Hoàn tất quét."
    )

# Quét với bộ lọc MUA SỊN
async def run_scan_sin_send_result(message_source, context: ContextTypes.DEFAULT_TYPE):
    try:
        syminfo = fetch_all_symbols()
        symbols = [s.code for s in syminfo]
    except Exception as e:
        await message_source.reply_text(f"❌ Lỗi tải danh sách mã: {e}")
        return

    # Gửi thông báo đang quét
    await message_source.reply_text(f"🔥 Đang quét {len(symbols)} mã với bộ lọc MUA SỊN… (song song {MAX_WORKERS} luồng)")
        
    try:
        rows = scan_symbols_sin(symbols)
        if not rows:
            await message_source.reply_text("⚠️ Quá trình quét bị gián đoạn hoặc không có dữ liệu.")
            return
    except KeyboardInterrupt:
        await message_source.reply_text("⚠️ Quá trình quét bị dừng bởi người dùng.")
        return
    except Exception as e:
        await message_source.reply_text(f"❌ Lỗi khi quét: {e}")
        return

    # Lọc ra những mã có tín hiệu Mua Sịn
    filtered = [r for r in rows if r["BuySin"]]

    if not filtered:
        # Thông báo khi không có tín hiệu
        total_scanned = len(rows)
        await message_source.reply_text(
            f"🔥 <b>KẾT QUẢ QUÉT MUA SỊN</b>\n"
            f"═══════════════════════════\n\n"
            f"🔍 Đã quét: <b>{total_scanned}</b> mã cổ phiếu\n"
            f"❌ Không tìm thấy mã nào có tín hiệu <b>MUA SỊN</b>\n\n"
            f"💡 <i>Gợi ý: Bộ lọc MUA SỊN hiện chưa được cấu hình điều kiện. "
            f"Vui lòng cấu hình điều kiện lọc để có kết quả.</i>",
            parse_mode="HTML"
        )
        return

    # Tạo message format cho Mua Sịn
    def format_price(price):
        return f"{price:,.1f}"
    
    def format_percent(pct):
        return f"<b>{pct:+.2f}%</b>"

    lines = []
    lines.append("🔥 <b>KẾT QUẢ QUÉT MUA SỊN</b>")
    lines.append("═" * 30)
    lines.append("")
    
    # Hiển thị tất cả mã có tín hiệu Mua Sịn
    for r in filtered:
        lines.append(f"🔥 <b>{r['symbol']}</b> • {format_price(r['price'])} • {format_percent(r['pct'])}")
    
    lines.append("")
    lines.append(f"📊 <b>THỐNG KÊ</b>")
    lines.append(f"🔥 Tổng mã Mua Sịn: <b>{len(filtered)}</b>")
    
    import datetime
    current_time = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    lines.append(f"⏰ Quét lúc: <i>{current_time}</i>")
    lines.append("📝 <i>Chỉ mang tính chất tham khảo</i>")

    msg = "\n".join(lines)
    
    # Gửi kết quả
    chat_id = message_source.chat_id
    await context.bot.send_message(
        chat_id=chat_id,
        text=msg,
        parse_mode="HTML"
    )
    
    # Gửi thông báo hoàn tất
    await context.bot.send_message(
        chat_id=chat_id,
        text="🔥 Hoàn tất quét Mua Sịn."
    )

async def run_scan_sin3_send_result(message_source, context: ContextTypes.DEFAULT_TYPE):
    """Chạy scan với bộ lọc MUA SỊN 3 và gửi kết quả"""
    try:
        syminfo = fetch_all_symbols()
        symbols = [s.code for s in syminfo]
    except Exception as e:
        await message_source.reply_text(f"❌ Lỗi tải danh sách mã: {e}")
        return

    # Gửi thông báo đang quét
    await message_source.reply_text(f"🚀 Đang quét {len(symbols)} mã với bộ lọc MUA SỊN 3… (song song {MAX_WORKERS} luồng)")
        
    try:
        rows = scan_symbols_sin3(symbols)
        if not rows:
            await message_source.reply_text("⚠️ Quá trình quét bị gián đoạn hoặc không có dữ liệu.")
            return
    except KeyboardInterrupt:
        await message_source.reply_text("⚠️ Quá trình quét bị dừng bởi người dùng.")
        return
    except Exception as e:
        await message_source.reply_text(f"❌ Lỗi khi quét: {e}")
        return

    # Lọc kết quả
    filtered = [r for r in rows if r.get("BuySin3", False)]
    
    if not filtered:
        await message_source.reply_text("🚀 Không có mã nào thỏa mãn bộ lọc MUA SỊN 3 hiện tại.")
        return

    # Format kết quả
    lines = ["🚀 <b>KẾT QUẢ MUA SỊN 3</b>"]
    lines.append("─" * 30)
    
    for r in filtered:
        sym = r["symbol"]
        price = r["price"]
        pct = r["pct"] if r["pct"] is not None else 0
        
        # Icon màu cho % thay đổi
        if pct > 2:
            pct_icon = "🟢"
        elif pct > 0:
            pct_icon = "🟡"
        elif pct > -2:
            pct_icon = "🟠"
        else:
            pct_icon = "🔴"
        
        # Format: Mã • Giá • % • Tín hiệu
        lines.append(f"🚀 <b>{sym}</b> • {price:,.0f}₫ • {pct_icon}<b>{pct:+.2f}%</b>")
    
    lines.append("")
    lines.append(f"📊 <b>THỐNG KÊ</b>")
    lines.append(f"🚀 Tổng mã Mua Sịn 3: <b>{len(filtered)}</b>")
    
    import datetime
    current_time = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    lines.append(f"⏰ Quét lúc: <i>{current_time}</i>")
    lines.append("📝 <i>Chỉ mang tính chất tham khảo</i>")

    msg = "\n".join(lines)
    
    # Gửi kết quả
    chat_id = message_source.chat_id
    await context.bot.send_message(
        chat_id=chat_id,
        text=msg,
        parse_mode="HTML"
    )
    
    # Gửi thông báo hoàn tất
    await context.bot.send_message(
        chat_id=chat_id,
        text="🚀 Hoàn tất quét Mua Sịn 3."
    )

# =====================
# Chart Functions for Web App
# =====================

def fetch_extended_history(symbol: str, max_days: int = 500) -> pd.DataFrame:
    """
    Fetch extended historical data for charting (up to max_days)
    Falls back to maximum available data if less than max_days
    """
    import datetime as dt
    
    now = int(time.time())
    # Tính từ max_days ngày trước (thêm buffer cho weekends/holidays)
    days_with_buffer = max_days + 50
    day_from = int((dt.datetime.utcnow() - dt.timedelta(days=days_with_buffer)).timestamp())
    
    try:
        # Fetch daily data
        daily = dchart_history(symbol, "D", day_from, now)
        
        if daily.empty:
            return pd.DataFrame()
        
        # Giới hạn về max_days nếu có quá nhiều data
        if len(daily) > max_days:
            daily = daily.tail(max_days)
            
        return daily
        
    except Exception as e:
        print(f"❌ Error fetching extended history for {symbol}: {e}")
        return pd.DataFrame()

def create_candlestick_chart(symbol: str, data: pd.DataFrame):
    """
    Create interactive candlestick chart with technical indicators
    - Candlestick + Volume
    - MA20, MA50, EMA34, EMA89
    - RSI subplot
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    if data.empty:
        return None
    
    # Clean data - xử lý mạnh mẽ hơn để tránh gaps
    data = data.dropna(subset=['O', 'H', 'L', 'C', 'V'])
    
    if data.empty:
        return None
    
    # Reindex để đảm bảo không có gaps trong index
    data = data.sort_index()
    
    # Tạo một DatetimeIndex liên tục (business days only)
    if len(data) > 1:
        start_date = data.index.min()
        end_date = data.index.max()
        
        # Tạo business day range (loại bỏ weekend)
        full_range = pd.date_range(start=start_date, end=end_date, freq='B')
        
        # Reindex với full range và interpolate
        data = data.reindex(full_range)
        
        # Interpolate để fill gaps - sử dụng linear interpolation
        data['O'] = data['O'].interpolate(method='linear').ffill().bfill()
        data['H'] = data['H'].interpolate(method='linear').ffill().bfill()
        data['L'] = data['L'].interpolate(method='linear').ffill().bfill()
        data['C'] = data['C'].interpolate(method='linear').ffill().bfill()
        data['V'] = data['V'].interpolate(method='linear').ffill().bfill()
        
        # Đảm bảo OHLC logic hợp lý sau interpolation
        data['H'] = data[['O', 'H', 'L', 'C']].max(axis=1)
        data['L'] = data[['O', 'H', 'L', 'C']].min(axis=1)
    
    # Drop NaN rows cuối cùng nếu còn
    data = data.dropna()
    
    if data.empty:
        return None
    
    # Tính các technical indicators
    C = data['C']
    H = data['H'] 
    L = data['L']
    O = data['O']
    V = data['V']
    
    # Moving Averages - với interpolation
    MA20 = sma(C, 20).interpolate().ffill().bfill()
    MA50 = sma(C, 50).interpolate().ffill().bfill()
    EMA34 = ema(C, 34).interpolate().ffill().bfill()
    EMA89 = ema(C, 89).interpolate().ffill().bfill()
    
    # RSI - với interpolation
    RSI14 = rsi(C, 14).interpolate().ffill().bfill()
    
    # Volume MA
    VOL_MA20 = sma(V, 20).interpolate().ffill().bfill()
    
    # Tạo subplots: [Candlestick + MA], [Volume], [RSI]
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(f'{symbol} - Candlestick Chart', 'Volume', 'RSI (14)'),
        row_heights=[0.6, 0.2, 0.2]
    )
    
    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=O,
            high=H,
            low=L,
            close=C,
            name=symbol,
            showlegend=False
        ),
        row=1, col=1
    )
    
    # Moving Averages - với connectgaps và mode lines
    fig.add_trace(
        go.Scatter(x=data.index, y=MA20, name='MA20', 
                  mode='lines',
                  line=dict(color='blue', width=2),
                  connectgaps=True),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=data.index, y=MA50, name='MA50', 
                  mode='lines',
                  line=dict(color='orange', width=2),
                  connectgaps=True),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=data.index, y=EMA34, name='EMA34', 
                  mode='lines',
                  line=dict(color='red', width=2),
                  connectgaps=True),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=data.index, y=EMA89, name='EMA89', 
                  mode='lines',
                  line=dict(color='purple', width=2),
                  connectgaps=True),
        row=1, col=1
    )
    
    # Volume
    fig.add_trace(
        go.Bar(x=data.index, y=V, name='Volume', 
               marker_color='lightblue', showlegend=False),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(x=data.index, y=VOL_MA20, name='Vol MA20', 
                  mode='lines',
                  line=dict(color='red', width=2),
                  connectgaps=True),
        row=2, col=1
    )
    
    # RSI - với connectgaps và mode lines
    fig.add_trace(
        go.Scatter(x=data.index, y=RSI14, name='RSI(14)', 
                  mode='lines',
                  line=dict(color='green', width=2), 
                  showlegend=False,
                  connectgaps=True),
        row=3, col=1
    )
    
    # RSI reference lines
    fig.add_hline(y=70, line_dash="dash", line_color="red", 
                  annotation_text="Overbought (70)", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="blue", 
                  annotation_text="Oversold (30)", row=3, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="gray", row=3, col=1)
    
    # Layout styling (Light theme)
    fig.update_layout(
        title=f"{symbol} - Technical Analysis ({len(data)} days)",
        height=800,
        template="plotly_white",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=50, r=50, t=100, b=50),
        # Thêm config để xử lý gaps tốt hơn
        xaxis=dict(
            type='date',
            rangeslider_visible=False,
            # Loại bỏ weekends và holidays
            rangebreaks=[
                dict(bounds=["sat", "mon"]),  # hide weekends
            ]
        )
    )
    
    # X-axis formatting - áp dụng cho tất cả subplots
    fig.update_xaxes(
        type='date',
        rangeslider_visible=False,
        # Loại bỏ weekends để chart liên tục hơn
        rangebreaks=[
            dict(bounds=["sat", "mon"]),  # hide weekends
        ],
        rangeselector=dict(
            buttons=list([
                dict(count=30, label="30D", step="day", stepmode="backward"),
                dict(count=60, label="60D", step="day", stepmode="backward"),
                dict(count=90, label="90D", step="day", stepmode="backward"),
                dict(step="all", label="All")
            ])
        )
    )
    
    # Y-axis RSI range
    fig.update_yaxes(range=[0, 100], row=3, col=1)
    
    return fig

if __name__ == "__main__":
    import sys
    import asyncio

    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN trong .env")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_text))

    print("🚀 Bot với Reply Keyboard đã sẵn sàng!")
    print("📱 Tính năng:")
    print("   - Nút '🔍 Quét Tín Hiệu MUA' cố định trên Telegram")
    print("   - Nút '🔥 Quét Mua Sịn' - Bộ lọc mới độc lập")
    print("   - Nút '❓ Hướng Dẫn' để xem cách sử dụng")
    print("   - Gõ /start để hiển thị keyboard")
    print(">>> Đang khởi động bot...")
    
    try:
        app.run_polling()
    except Exception as e:
        print(f"❌ Lỗi khởi động bot: {e}")
        if "Conflict" in str(e):
            print("💡 Giải pháp: Có bot instance khác đang chạy.")
            print("   Hãy dừng bot khác hoặc đợi 1-2 phút rồi thử lại.")
