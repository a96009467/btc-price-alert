# BTC 價格漲跌即時監控 + Bark 推送

部署在 **GitHub Actions** 上的免費自動化腳本，定時監控 BTC 價格，當漲跌幅超過你設定的閾值時，自動推送到你的 iPhone Bark。

---

## 功能特色

- ✅ **免費運行**：使用 GitHub Actions 免費額度，不需要自己租伺服器
- ✅ **即時推送**：價格波動超過閾值立刻發 Bark 通知
- ✅ **狀態持久化**：自動記錄上次價格，下次比對基準
- ✅ **彈性設定**：可調整監控頻率、漲跌幅閾值
- ✅ **首次啟動通知**：第一次執行會發一則啟動訊息確認推送正常

---

## 部署步驟（5 分鐘完成）

### 第一步：建立 GitHub 倉庫

1. 登入你的 GitHub 帳號
2. 點右上角 **「+」→「New repository」**
3. 倉庫名稱隨便取，例如 `btc-price-alert`
4. **設定為 Private（私有）** ← 重要！因為你的 Bark Key 存在這裡
5. 不要勾選「Add a README file」，直接建立空倉庫

### 第二步：上傳專案檔案

把以下三個檔案上傳到你的新倉庫：

```
你的倉庫/
├── .github/
│   └── workflows/
│       └── btc-monitor.yml    ← GitHub Actions 工作流
├── btc_monitor.py             ← 主要監控腳本
└── README.md                  ← 說明文件
```

**上傳方式**：在 GitHub 倉庫頁面點「uploading an existing file」，把檔案拖進去即可。
記得 `.github/workflows/btc-monitor.yml` 的路徑要完全正確。

### 第三步：設定 Bark 金鑰（Secret）

1. 進入倉庫的 **Settings → Secrets and variables → Actions**
2. 點 **「New repository secret」**
3. 新增以下 Secret：

| Name | Value | 說明 |
|------|-------|------|
| `BARK_KEY` | `你的Bark金鑰` | 從你的 Bark App 裡複製那串 Key |

> 你也可以新增選項的 Secret：
> - `BARK_SERVER`：如果你有自架 Bark 伺服器才需要填，預設是 `https://api.day.app`

### 第四步：設定漲跌幅閾值（可選）

1. 進入倉庫的 **Settings → Secrets and variables → Actions → Variables** 分頁
2. 點 **「New repository variable」**
3. 新增：

| Name | Value | 說明 |
|------|-------|------|
| `THRESHOLD_PERCENT` | `1.0` | 漲跌幅超過 1% 才推送，依你需求調整 |

> 不設定的話預設就是 1%。想更敏感可以設 0.5，想安靜一點可以設 2 或 3。

### 第五步：啟用 GitHub Actions

1. 進入倉庫的 **Actions** 分頁
2. 如果看到「Workflows aren't being run on this forked repository」之類的提示，點 **「I understand my workflows, go ahead and enable them」**
3. 左側選到「BTC 價格監控」→ 點 **「Run workflow」** 手動測試一次
4. 確認 iPhone 有收到 Bark 通知 🎉

---

## 客製化調整

### 調整監控頻率

編輯 `.github/workflows/btc-monitor.yml`，修改 `cron` 那一行：

```yaml
schedule:
  - cron: "*/15 * * * *"   # 每 15 分鐘
  # - cron: "*/30 * * * *"  # 每 30 分鐘
  # - cron: "0 * * * *"     # 每小時整點
  # - cron: "*/5 * * * *"   # 每 5 分鐘（注意：GitHub Actions 免費額度限制）
```

> ⚠️ GitHub Actions 免費方案限制：私有倉庫每月 2000 分鐘執行額度。
> 每 15 分鐘跑一次 = 每天約 96 次 ≈ 每月 2880 次，可能會超過。
> 建議用每 30 分鐘或每小時一次比較保險。

### 改監控其他幣種

編輯 `btc_monitor.py`，修改 `SYMBOL`：

```python
SYMBOL = "BTCUSDT"   # 比特幣
# SYMBOL = "ETHUSDT"  # 乙太坊
# SYMBOL = "SOLUSDT"  # Solana
```

---

## 運作原理

```
每 15 分鐘觸發
    ↓
呼叫 Binance API 取得 BTC 即時價格
    ↓
讀取倉庫裡 state.json 存的上次價格
    ↓
計算漲跌幅 (%)
    ↓
超過閾值？
  ├─ 是 → 發送 Bark 通知到你的 iPhone
  └─ 否 → 跳過推送
    ↓
把目前價格寫回 state.json，推回 GitHub 倉庫
```

---

## 常見問題

**Q: 為什麼都沒收到通知？**
- 先到 Actions 分頁看這次執行有沒有紅色叉叉
- 確認 BARK_KEY Secret 有設對
- 第一次執行只會發「監控啟動」通知，之後要等真的超過閾值才會推

**Q: 會不會很吵？**
- 預設 1% 閾值，BTC 一天波動幾次很正常
- 嫌吵就把 `THRESHOLD_PERCENT` 調高到 2 或 3

**Q: GitHub Actions 免費額度夠用嗎？**
- 公開倉庫：無限執行時間
- 私有倉庫：每月 2000 分鐘，每 30 分鐘跑一次大約每月 1440 分鐘，剛好夠
- 建議設成 Public 倉庫就完全不用擔心額度（Bark Key 存在 Secret 裡不會外洩）

**Q: state.json 是什麼？**
- 就是記錄「上次 BTC 價格是多少」的小檔案
- 沒有它的話每次都不知道漲跌了多少
- 腳本會自動更新這個檔案，不用手動動它

---

## 檔案總覽

| 檔案 | 用途 |
|------|------|
| `btc_monitor.py` | 主要邏輯：抓價格、比對、發推送 |
| `.github/workflows/btc-monitor.yml` | GitHub Actions 排程設定 |
| `state.json` | 自動產生，記錄上次價格（不用手動建） |
