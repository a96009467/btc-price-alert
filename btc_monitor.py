import os
import json
import math
import requests
from datetime import datetime, timezone, timedelta

# ============ 配置 ============
BARK_KEY = os.environ.get("BARK_KEY", "")
BARK_SERVER = os.environ.get("BARK_SERVER", "https://api.day.app")

SYMBOL = "BTCUSDT"

# 短時間窗口警報配置（單位：美元）
WINDOW_3MIN_UP = float(os.environ.get("WINDOW_3MIN_UP", "200"))    # 3分鐘內上漲超過$200
WINDOW_5MIN_CHG = float(os.environ.get("WINDOW_5MIN_CHG", "300"))  # 5分鐘內漲跌超過$300
WINDOW_10MIN_CHG = float(os.environ.get("WINDOW_10MIN_CHG", "500")) # 10分鐘內漲跌超過$500

# 一般監控配置
PRICE_CHANGE_THRESHOLD = float(os.environ.get("THRESHOLD_PERCENT", "1.0"))
LEVEL_BREAKPOINT = int(os.environ.get("LEVEL_BREAKPOINT", "1000"))
DAILY_REPORT_HOUR = int(os.environ.get("DAILY_REPORT_HOUR", "9"))
STRONG_ALERT_PCT = float(os.environ.get("STRONG_ALERT_PCT", "3.0"))

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
TZ = timezone(timedelta(hours=8))
MAX_HISTORY_MINUTES = 15  # 保留15分鐘的價格歷史


def get_btc_price():
    url = "https://api.binance.com/api/v3/ticker/price"
    params = {"symbol": SYMBOL}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return float(resp.json()["price"])
    except Exception as e:
        print(f"[錯誤] 取得價格失敗: {e}")
        return None


def get_24hr_stats():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    params = {"symbol": SYMBOL}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {
            "price_change_pct": float(data["priceChangePercent"]),
            "high": float(data["highPrice"]),
            "low": float(data["lowPrice"]),
        }
    except Exception as e:
        print(f"[警告] 取得24hr統計失敗: {e}")
        return None


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[警告] 讀取狀態失敗: {e}")
        return {}


def save_state(state):
    state["updated_at"] = datetime.now(TZ).isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_bark(title, body, group="BTC行情", sound="default", level="active"):
    if not BARK_KEY:
        print("[錯誤] 未設定 BARK_KEY")
        return False
    url = f"{BARK_SERVER}/{BARK_KEY}/{title}/{body}"
    params = {
        "group": group,
        "sound": sound,
        "level": level,
        "ttl": 600,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        result = resp.json()
        if result.get("code") == 200:
            print(f"[推送成功] {title}")
            return True
        print(f"[推送失敗] {result}")
        return False
    except Exception as e:
        print(f"[推送錯誤] {e}")
        return False


def find_price_n_minutes_ago(history, minutes):
    """從價格歷史中找到 N 分鐘前最接近的價格"""
    if not history:
        return None
    now = datetime.now(TZ)
    target_time = now - timedelta(minutes=minutes)
    # 找到最接近目標時間的那筆
    best = None
    best_diff = timedelta(hours=999)
    for entry in history:
        entry_time = datetime.fromisoformat(entry["time"])
        diff = abs(entry_time - target_time)
        if diff < best_diff:
            best_diff = diff
            best = entry["price"]
    # 如果超過 1.5 倍誤差（例如要求3分鐘前但找到的是5分鐘前），就不採用
    if best_diff > timedelta(minutes=minutes * 0.6 + 1):
        return None
    return best


def check_window_alerts(current_price, history):
    """檢查各時間窗口的短線波動警報"""
    alerts = []

    # 3分鐘窗口：只偵測上漲超過 $200
    price_3min = find_price_n_minutes_ago(history, 3)
    if price_3min is not None:
        chg_3min = current_price - price_3min
        if chg_3min >= WINDOW_3MIN_UP:
            alerts.append({
                "title": f"⚡ 3分鐘急漲 +${chg_3min:,.0f}",
                "body": f"3分鐘前: ${price_3min:,.2f}\n現在: ${current_price:,.2f}\n漲幅: +${chg_3min:,.2f}",
                "sound": "alarm",
                "level": "timeSensitive",
                "group": "短線急漲"
            })

    # 5分鐘窗口：漲跌超過 $300
    price_5min = find_price_n_minutes_ago(history, 5)
    if price_5min is not None:
        chg_5min = current_price - price_5min
        if abs(chg_5min) >= WINDOW_5MIN_CHG:
            arrow = "📈" if chg_5min >= 0 else "📉"
            direction = "急漲" if chg_5min >= 0 else "急跌"
            alerts.append({
                "title": f"{arrow} 5分鐘{direction} ${abs(chg_5min):,.0f}",
                "body": f"5分鐘前: ${price_5min:,.2f}\n現在: ${current_price:,.2f}\n變動: {chg_5min:+,.2f}",
                "sound": "glass",
                "level": "active",
                "group": "5分鐘波動"
            })

    # 10分鐘窗口：漲跌超過 $500
    price_10min = find_price_n_minutes_ago(history, 10)
    if price_10min is not None:
        chg_10min = current_price - price_10min
        if abs(chg_10min) >= WINDOW_10MIN_CHG:
            arrow = "🚀" if chg_10min >= 0 else "🔻"
            direction = "大漲" if chg_10min >= 0 else "大跌"
            alerts.append({
                "title": f"{arrow} 10分鐘{direction} ${abs(chg_10min):,.0f}",
                "body": f"10分鐘前: ${price_10min:,.2f}\n現在: ${current_price:,.2f}\n變動: {chg_10min:+,.2f}",
                "sound": "horn",
                "level": "timeSensitive",
                "group": "10分鐘波動"
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


def check_daily_report(state, current_price):
    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")
    last_report_date = state.get("last_daily_report_date", "")
    if now.hour >= DAILY_REPORT_HOUR and last_report_date != today:
        stats = get_24hr_stats()
        if stats:
            arrow = "📈" if stats["price_change_pct"] >= 0 else "📉"
            title = f"{arrow} BTC 日報 {today}"
            body = (
                f"目前價格: ${current_price:,.2f}\n"
                f"24h 漲跌: {stats['price_change_pct']:+.2f}%\n"
                f"24h 最高: ${stats['high']:,.2f}\n"
                f"24h 最低: ${stats['low']:,.2f}"
            )
            send_bark(title, body, group="BTC日報", sound="calendar")
            return today
    return last_report_date


def main():
    now = datetime.now(TZ)
    print("=" * 50)
    print(f"BTC 監控啟動 - {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    current_price = get_btc_price()
    if current_price is None:
        return
    print(f"[目前價格] ${current_price:,.2f}")

    state = load_state()
    history = state.get("price_history", [])

    # === 短線窗口警報 ===
    alerts = check_window_alerts(current_price, history)
    for alert in alerts:
        send_bark(
            title=alert["title"],
            body=alert["body"],
            group=alert["group"],
            sound=alert["sound"],
            level=alert["level"]
        )

    # === 更新價格歷史（保留最近15分鐘）===
    history.append({"price": current_price, "time": now.isoformat()})
    cutoff = now - timedelta(minutes=MAX_HISTORY_MINUTES)
    history = [h for h in history if datetime.fromisoformat(h["time"]) > cutoff]
    state["price_history"] = history

    # === 首次執行 ===
    last_price = state.get("last_price")
    if last_price is None:
        current_level = math.floor(current_price / LEVEL_BREAKPOINT) * LEVEL_BREAKPOINT
        state["last_price"] = current_price
        state["last_level"] = current_level
        save_state(state)
        send_bark(
            title="✅ BTC監控已啟動",
            body=f"目前價格: ${current_price:,.2f}\n"
                 f"3分鐘急漲門檻: +${WINDOW_3MIN_UP:.0f}\n"
                 f"5分鐘波動門檻: ±${WINDOW_5MIN_CHG:.0f}\n"
                 f"10分鐘波動門檻: ±${WINDOW_10MIN_CHG:.0f}"
        )
        return

    # === 一般漲跌幅告警 ===
    change_pct = ((current_price - last_price) / last_price) * 100
    abs_change = abs(change_pct)
    direction = "上漲" if change_pct >= 0 else "下跌"

    if abs_change >= PRICE_CHANGE_THRESHOLD:
        arrow = "🚀" if change_pct >= 0 else "🔻"
        if abs_change >= STRONG_ALERT_PCT:
            title = f"{arrow} BTC 大行情！{direction} {abs_change:.2f}%"
            sound = "alarm"
            level = "timeSensitive"
        else:
            title = f"📊 BTC {direction} {abs_change:.2f}%"
            sound = "glass"
            level = "active"
        body = f"目前: ${current_price:,.2f}\n前次: ${last_price:,.2f}\n變動: {change_pct:+.2f}%"
        send_bark(title, body, sound=sound, level=level)

    # === 整數關卡突破 ===
    last_level = state.get("last_level")
    level_msg, new_level = check_level_break(current_price, last_level)
    if level_msg:
        send_bark(
            title=f"🎯 {level_msg}",
            body=f"目前 BTC 價格: ${current_price:,.2f}",
            group="關卡突破",
            sound="horn"
        )
    state["last_level"] = new_level

    # === 每日簡報 ===
    state["last_daily_report_date"] = check_daily_report(state, current_price)

    # === 儲存狀態 ===
    state["last_price"] = current_price
    save_state(state)
    print(f"[完成] 歷史記錄 {len(history)} 筆")


if __name__ == "__main__":
    main()
