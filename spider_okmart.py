# 引入基礎時間操作模組
import time
import random
import datetime

# 引入網頁解析工具
from bs4 import BeautifulSoup

# 引入 Selenium 相關模組
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# 引入網址組合工具
from urllib.parse import urljoin

# ==========================================
# 定義過濾條件清單
# ==========================================

# 圖片 URL 黑名單
FILTER_KEYWORDS = [
    "icon", "logo", "arrow", "btn", "button", "footer", "header", 
    "facebook", "instagram", "youtube", "line", "svg",
]

# 標題內容黑名單
TITLE_FILTERS = [
    "facebook", "instagram", "youtube", "line", "logo", "icon",
    "更多", "查看更多", "了解更多", "立即前往", "回首頁", "首頁",
    "下載app", "下載APP", "會員登入", "會員中心", "登入", "註冊",
    "客服", "聯絡我們", "關於我們", "代收房屋稅", "代收房屋稅",
    "共享", "客製車牌號碼悠遊卡", "週五會員日最高5%回饋",
    "台灣PAY筆筆20%回饋", "台鐵", "繳交電信費", "涼一夏"
]

# ==========================================
# 定義分類函式
# ==========================================

def parse_category_and_expiry(title):
    category = "其他" # 初始化為其他

    # 針對標題內含文字進行粗略分類
    if any(x in title for x in ["咖啡", "拿鐵", "美式", "CITY"]): category = "咖啡"
    elif any(x in title for x in ["霜淇淋", "冰品", "雪糕"]): category = "冰品"
    elif any(x in title for x in ["飲料", "茶", "奶茶"]): category = "飲料"
    elif any(x in title for x in ["便當", "飯糰", "鮮食"]): category = "鮮食"
    elif any(x in title for x in ["集點", "會員"]): category = "會員活動"

    # 生成假想到期日字串
    expiry = (datetime.date.today() + datetime.timedelta(days=random.randint(3, 14))).strftime("%Y-%m-%d")

    return category, expiry

# ==========================================
# OK 超商主要爬蟲邏輯
# ==========================================

def crawl_okmart():
    # OK 超商的活動列表頁面
    base_url = "https://www.okmart.com.tw/promotion_reference"
    events = [] # 資料收集列表

    # 初始化配置
    options = Options()
    options.add_argument("--headless=new") # 新版無頭模式語法
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox") # 避開沙盒環境限制
    options.add_argument("--disable-dev-shm-usage") # 克服記憶體不足的報錯
    options.add_argument("window-size=1920,1080")

    # 🌟 核心修改：徹底移除 ChromeDriverManager 與 Service，直接將 options 交給 Chrome！
    driver = webdriver.Chrome(options=options)

    try:
        print(f"🌍 開始爬取 OK超商：{base_url}")
        driver.get(base_url) # 發送造訪請求
        time.sleep(5) # 稍作等待

        # 模擬真人往下拉動頁面 10 次
        for _ in range(10):
            # 一次直接滑動到 body 最底下
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)

        # 把渲染好的頁面丟給 BS4
        soup = BeautifulSoup(driver.page_source, "lxml")

        # 建立防重集合
        seen_images = set()
        seen_titles = set()

        # 廣泛收集可能包藏活動的網頁標籤
        candidates = soup.select("a, div, dl, article, section, li")
        print(f"找到 {len(candidates)} 個候選區塊")

        # 針對每一塊開始解析
        for tag in candidates:
            try:
                # ====== 處理圖片 ======
                img_tag = tag.find("img")
                if not img_tag: continue # 沒圖片就過濾

                # 取出圖片位置
                img_url = (img_tag.get("src", "") or img_tag.get("data-src", "")).strip()
                if not img_url: continue # 取不到字串也過濾
                
                # 轉絕對路徑
                img_url = urljoin(base_url, img_url)

                # 套用黑名單判斷是否為無關圖片
                if any(x.lower() in img_url.lower() for x in FILTER_KEYWORDS): continue
                if img_url in seen_images: continue # 重複也濾掉

                # ====== 處理標題 ======
                # 使用 separator 確保文字斷開乾淨
                title = tag.get_text(separator=" ", strip=True)
                title = " ".join(title.split()) # 將多餘連續空白縮減為單個空白

                if not title: continue # 沒標題就跳過
                if len(title) < 8: continue # 標題太短可能只是按鈕或分類名稱
                
                # 若中黑名單字眼就跳過
                if any(x.lower() in title.lower() for x in TITLE_FILTERS): continue
                if title in seen_titles: continue

                # ====== 處理連結 ======
                link = ""
                # 如果本身是 a 標籤就直接取 href
                if tag.name == "a":
                    link = tag.get("href", "").strip()
                else:
                    # 不然就往下找找看有沒有包著 a
                    a_tag = tag.find("a")
                    if not a_tag:
                        # 往下找不到，往老爸那一層找
                        parent_a = tag.find_parent("a")
                        if parent_a: a_tag = parent_a
                    
                    if a_tag: link = a_tag.get("href", "").strip()

                # 如果連結有問題，直接帶回基底頁面；反之組合絕對連結
                if not link or link == "#" or "javascript" in link.lower():
                    abs_link = base_url
                else:
                    abs_link = urljoin(base_url, link)

                # ====== 產生最終資料 ======
                category, expiry = parse_category_and_expiry(title)

                events.append({
                    "store": "OK超商",
                    "title": title[:120], # 限制標題長度最多 120 字
                    "img_url": img_url,
                    "link": abs_link,
                    "category": category,
                    "expiry_date": expiry,
                })

                # 將此筆資料註冊進集合中避免下一輪又抓到
                seen_images.add(img_url)
                seen_titles.add(title)

            except Exception:
                continue # 解析有錯就看下一個區塊

    except Exception as e:
        print("❌ OK超商爬取失敗：", e)
    finally:
        driver.quit() # 清除連線與資源

    print(f"✅ OK超商完成，共 {len(events)} 筆")
    return events

# 執行測試段落
if __name__ == "__main__":
    data = crawl_okmart()
    print("-" * 100)
    for i, item in enumerate(data[:20], start=1):
        print(f"[{i}] {item['title']}")
        print("圖片 :", item["img_url"])
        print("連結 :", item["link"])
        print("分類 :", item["category"])
        print("-" * 100)