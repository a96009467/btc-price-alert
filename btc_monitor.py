import os
import json
import requests
from datetime import datetime, timezone, timedelta

# ============ 配置 ============
# Bark 推送相關
BARK_KEY = os.environ.get("BARK_KEY", "")
BARK_SERVER = os.environ.get("BARK_SERVER", "https://api.day.app")

# 監控配置
SYMBOL = "BTCUSDT"
PRICE_CHANGE_THRESHOLD = float(os.environ.get("THRESHOLD_PERCENT", "1.0"))  # 漲跌幅閾值(%)
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

# 時區 (台北 UTC+8)
TZ = timezone(timedelta(hours=8))


def get_btc_price():
    """從 Binance 公開 API 取得 BTC 最新價格"""
    url = "https://api.binance.com/api/v3/ticker/price"
    params = {"symbol": SYMBOL}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return float(data["price"])
    except Exception as e:
        print(f"[錯誤] 取得 BTC 價格失敗: {e}")
        return None


def load_last_price():
    """讀取上次記錄的價格"""
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("last_price")
    except Exception as e:
        print(f"[警告] 讀取狀態檔失敗: {e}")
        return None


def save_current_price(price):
    """儲存目前價格作為下次比對基準"""
    now = datetime.now(TZ).isoformat()
    data = {"last_price": price, "updated_at": now}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[資訊] 已更新狀態: BTC=${price:,.2f} @ {now}")


def send_bark(title, body, group="BTC行情", sound="alarm"):
    """透過 Bark 推送通知"""
    if not BARK_KEY:
        print("[錯誤] 未設定 BARK_KEY 環境變數")
        return False

    url = f"{BARK_SERVER}/{BARK_KEY}/{title}/{body}"
    params = {
        "group": group,
        "sound": sound,
        "ttl": 600,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 200:
            print(f"[推送成功] {title} - {body}")
            return True
        else:
            print(f"[推送失敗] {result}")
            return False
    except Exception as e:
        print(f"[推送錯誤] {e}")
        return False


def main():
    print("=" * 50)
    print(f"BTC 價格監控啟動 - {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # 1. 取得目前價格
    current_price = get_btc_price()
    if current_price is None:
        print("[結束] 無法取得價格，退出")
        return

    print(f"[目前價格] BTC = ${current_price:,.2f}")

    # 2. 讀取上次價格
    last_price = load_last_price()
    if last_price is None:
        print("[首次執行] 無歷史價格，僅記錄目前價格，不推送通知")
        save_current_price(current_price)
        send_bark(
            title="BTC監控啟動",
            body=f"目前BTC價格: ${current_price:,.2f}\n閾值: ±{PRICE_CHANGE_THRESHOLD}%"
        )
        return

    print(f"[上次價格] BTC = ${last_price:,.2f}")

    # 3. 計算漲跌幅
    change_pct = ((current_price - last_price) / last_price) * 100
    direction = "上漲" if change_pct >= 0 else "下跌"
    abs_change = abs(change_pct)

    print(f"[漲跌幅] {direction} {abs_change:.2f}%")

    # 4. 判斷是否超過閾值
    if abs_change >= PRICE_CHANGE_THRESHOLD:
        arrow = "📈" if change_pct >= 0 else "📉"
        title = f"{arrow} BTC {direction} {abs_change:.2f}%"
        body = (
            f"目前價格: ${current_price:,.2f}\n"
            f"上次價格: ${last_price:,.2f}\n"
            f"變動金額: ${current_price - last_price:+,.2f}\n"
            f"漲跌幅: {change_pct:+.2f}%\n"
            f"時間: {datetime.now(TZ).strftime('%m-%d %H:%M')}"
        )
        send_bark(title, body)
    else:
        print(f"[未達閾值] 漲跌幅 {abs_change:.2f}% < {PRICE_CHANGE_THRESHOLD}%，不推送")

    # 5. 更新狀態
    save_current_price(current_price)


if __name__ == "__main__":
    main()
