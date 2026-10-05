import os
import json
import math
import requests
from urllib.parse import quote
from datetime import datetime, timezone, timedelta

# ============ 配置 ============
BARK_KEY = os.environ.get("BARK_KEY", "")
BARK_SERVER = os.environ.get("BARK_SERVER", "https://api.day.app")

# 短時間窗口警報（單位：美元）
WINDOW_3MIN_UP = float(os.environ.get("WINDOW_3MIN_UP", "200"))
WINDOW_5MIN_CHG = float(os.environ.get("WINDOW_5MIN_CHG", "300"))
WINDOW_10MIN_CHG = float(os.environ.get("WINDOW_10MIN_CHG", "500"))

# 一般監控配置
LEVEL_BREAKPOINT = int(os.environ.get("LEVEL_BREAKPOINT", "1000"))
DAILY_REPORT_HOUR = int(os.environ.get("DAILY_REPORT_HOUR", "9"))

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
TZ = timezone(timedelta(hours=8))
MAX_HISTORY_MINUTES = 15


def get_btc_data():
    """取得 BTC 即時價格，自動備援：幣安 → CoinGecko"""
    # 第一順位：幣安公共行情端點
    try:
        url = "https://data-api.binance.vision/api/v3/ticker/24hr"
        resp = requests.get(url, params={"symbol": "BTCUSDT"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {
            "price": float(data["lastPrice"]),
            "change_24h": float(data["priceChangePercent"]),
            "high_24h": float(data["highPrice"]),
            "low_24h": float(data["lowPrice"]),
            "source": "幣安"
        }
    except Exception as e:
        print(f"[警告] 幣安接口失敗，切換 CoinGecko: {e}")

    # 第二順位：歐易 OKX 備援
    try:
        url = "https://www.okx.com/api/v5/market/ticker"
        params = {"instId": "BTC-USDT"}
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()["data"][0]
        open_price = float(data["open24h"])
        current = float(data["last"])
        return {
            "price": current,
            "change_24h": ((current - open_price) / open_price) * 100,
            "high_24h": float(data["high24h"]),
            "low_24h": float(data["low24h"]),
            "source": "歐易OKX"
        }
    except Exception as e:
        print(f"[錯誤] 歐易也失敗: {e}")
        return None


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_state(state):
    state["updated_at"] = datetime.now(TZ).isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_bark(title, body, group="BTC行情", sound="default", level="active", url=""):
    if not BARK_KEY:
        print("[警告] 未設定 BARK_KEY，跳過推送")
        return False
    url_path = f"{BARK_SERVER}/{BARK_KEY}/{quote(title)}/{quote(body)}"
    params = {
        "group": group,
        "sound": sound,
        "level": level,
        "ttl": 600,
    }
    if url:
        params["url"] = url
    try:
        resp = requests.get(url_path, params=params, timeout=10)
        result = resp.json()
        if result.get("code") == 200:
            print(f"[推送成功] {title}")
            return True
        print(f"[推送失敗] {result}")
        return False
    except Exception as e:
        print(f"[推送錯誤] {e}")
        return False


def find_price_ago(history, minutes):
    """從歷史中找 N 分鐘前最接近的價格"""
    if not history:
        return None
    now = datetime.now(TZ)
    target = now - timedelta(minutes=minutes)
    best_price = None
    best_diff = timedelta(hours=999)
    for h in history:
        t = datetime.fromisoformat(h["time"])
        d = abs(t - target)
        if d < best_diff:
            best_diff = d
            best_price = h["price"]
    if best_diff > timedelta(minutes=minutes * 0.6 + 1):
        return None
    return best_price


def check_window_alerts(current_price, history, okx_price=None):
    """短線窗口波動警報"""
    alerts = []
    kline_url = "https://www.binance.com/zh-TC/trade/BTC_USDT"
    price_line = f"幣安: ${current_price:,.2f}"
    if okx_price:
        price_line += f"\n歐易: ${okx_price:,.2f}"

    # 3分鐘：漲跌 $200
    p3 = find_price_ago(history, 3)
    if p3 is not None:
        chg = current_price - p3
        if abs(chg) >= WINDOW_3MIN_UP:
            arrow = "⚡" if chg >= 0 else "🔻"
            direction = "急漲" if chg >= 0 else "急跌"
            alerts.append({
                "title": f"{arrow} 3分鐘{direction} ${abs(chg):,.0f}",
                "body": f"3分鐘前: ${p3:,.2f}\n{price_line}\n變動: {chg:+,.2f}",
                "sound": "alarm", "level": "timeSensitive", "group": "3分鐘波動",
                "url": kline_url
            })

    # 5分鐘：漲跌 $300
    p5 = find_price_ago(history, 5)
    if p5 is not None:
        chg = current_price - p5
        if abs(chg) >= WINDOW_5MIN_CHG:
            arrow = "📈" if chg >= 0 else "📉"
            direction = "急漲" if chg >= 0 else "急跌"
            alerts.append({
                "title": f"{arrow} 5分鐘{direction} ${abs(chg):,.0f}",
                "body": f"5分鐘前: ${p5:,.2f}\n{price_line}\n變動: {chg:+,.2f}",
                "sound": "glass", "level": "active", "group": "5分鐘波動",
                "url": kline_url
            })

    # 10分鐘：漲跌 $500
    p10 = find_price_ago(history, 10)
    if p10 is not None:
        chg = current_price - p10
        if abs(chg) >= WINDOW_10MIN_CHG:
            arrow = "🚀" if chg >= 0 else "🔻"
            direction = "大漲" if chg >= 0 else "大跌"
            alerts.append({
                "title": f"{arrow} 10分鐘{direction} ${abs(chg):,.0f}",
                "body": f"10分鐘前: ${p10:,.2f}\n{price_line}\n變動: {chg:+,.2f}",
                "sound": "horn", "level": "timeSensitive", "group": "10分鐘波動",
                "url": kline_url
            })

    return alerts


def check_level_break(current_price, last_level):
    current_level = math.floor(current_price / LEVEL_BREAKPOINT) * LEVEL_BREAKPOINT
    if last_level is None:
        return None, current_level
    if current_level != last_level:
        direction = "突破" if current_level > last_level else "跌破"
        return f"{direction} ${current_level:,} 大關", current_level
    return None, current_level


def get_okx_price():
    """額外取得歐易價格，供通知對比用"""
    try:
        url = "https://www.okx.com/api/v5/market/ticker"
        resp = requests.get(url, params={"instId": "BTC-USDT"}, timeout=8)
        resp.raise_for_status()
        return float(resp.json()["data"][0]["last"])
    except:
        return None


def main():
    now = datetime.now(TZ)
    print("=" * 40)
    print(f"BTC 監控 - {now.strftime('%m-%d %H:%M:%S')}")

    data = get_btc_data()
    if data is None:
        return
    current_price = data["price"]
    print(f"[目前] ${current_price:,.2f} ({data.get('source', '')})")

    # 額外取歐易價格做對比
    okx_price = get_okx_price()
    if okx_price:
        print(f"[歐易] ${okx_price:,.2f}")

    state = load_state()
    history = state.get("price_history", [])

    # 短線窗口警報
    kline_url = "https://www.binance.com/zh-TC/trade/BTC_USDT"
    for alert in check_window_alerts(current_price, history, okx_price):
        send_bark(alert["title"], alert["body"],
                  group=alert["group"], sound=alert["sound"], level=alert["level"],
                  url=alert.get("url", kline_url))

    # 更新歷史
    history.append({"price": current_price, "time": now.isoformat()})
    cutoff = now - timedelta(minutes=MAX_HISTORY_MINUTES)
    history = [h for h in history if datetime.fromisoformat(h["time"]) > cutoff]
    state["price_history"] = history

    # 首次執行
    last_price = state.get("last_price")
    if last_price is None:
        state["last_price"] = current_price
        state["last_level"] = math.floor(current_price / LEVEL_BREAKPOINT) * LEVEL_BREAKPOINT
        save_state(state)
        send_bark(
            "✅ BTC監控已啟動",
            f"目前價格: ${current_price:,.2f}\n"
            f"數據來源: {data.get('source', '幣安')}\n"
            f"3分鐘波動門檻: ±${WINDOW_3MIN_UP:.0f}\n"
            f"5分鐘波動門檻: ±${WINDOW_5MIN_CHG:.0f}\n"
            f"10分鐘波動門檻: ±${WINDOW_10MIN_CHG:.0f}",
            url=kline_url
        )
        return

    # 整數關卡
    last_level = state.get("last_level")
    level_msg, new_level = check_level_break(current_price, last_level)
    if level_msg:
        send_bark(f"🎯 {level_msg}", f"目前: ${current_price:,.2f}",
                  group="關卡突破", sound="horn", url=kline_url)
    state["last_level"] = new_level

    # 每日簡報
    today = now.strftime("%Y-%m-%d")
    if now.hour >= DAILY_REPORT_HOUR and state.get("last_report_date") != today:
        arrow = "📈" if data["change_24h"] >= 0 else "📉"
        send_bark(
            f"{arrow} BTC 日報 {today}",
            f"目前: ${current_price:,.2f}\n"
            f"24h 漲跌: {data['change_24h']:+.2f}%\n"
            f"24h 最高: ${data['high_24h']:,.2f}\n"
            f"24h 最低: ${data['low_24h']:,.2f}",
            group="BTC日報", sound="calendar"
        )
        state["last_report_date"] = today

    # 儲存
    state["last_price"] = current_price
    save_state(state)
    print(f"[完成] 歷史 {len(history)} 筆")


if __name__ == "__main__":
    main()
