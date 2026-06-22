# 引入時間、日期、正則表達式、隨機數模組
import time, datetime, re, random
# 引入 BeautifulSoup 用來解析爬下來的網頁結構
from bs4 import BeautifulSoup
# 引入 Selenium 核心物件
from selenium import webdriver
# 引入 Chrome Options 用來客製化啟動參數
from selenium.webdriver.chrome.options import Options
# 引入 urljoin 用來處理網址拼接
from urllib.parse import urljoin

# 定義目標活動關鍵字
TARGET_KEYWORDS = ["咖啡", "拿鐵", "美式", "卡布奇諾", "冰品", "霜淇淋", "冰棒", "雪糕", "聖代", "飲料", "茶", "果汁", "汽水", "乳品", "鮮奶", "牛奶", "優酪乳", "奶茶", "啤酒", "生啤酒", "水果酒", "精釀", "發泡酒", "買一送一", "特價", "折", "超值"]
# 定義過濾黑名單，用來排除 UI 圖示等無關元素
FILTER_KEYWORDS = ["icon", "logo", "arrow", "btn", "button", "footer", "header", "svg", "facebook", "instagram", "line", "download", "店到店", "pdf", "限定門市", "便利生活", "juice", "beer", "蔬", "openpoint", "飲料杯", "提袋", "pass", "國泰", "ecoco", "購票", "洗衣", "地圖", "悠遊", "picard", "集章", "週期購", "寄物", "appstore", "wallet", "循環杯", "中獎", "錢包", "lbcweb", "plus", "gift", "creditcard", "famipoint", "智慧財產權", "familaundry","fm eshop","qrcode","全家你家都能取"]

# 建立並回傳 Chrome 驅動程式物件
def create_driver():
    # 建立啟動選項實例
    options = Options()
    # 開啟無頭模式，讓瀏覽器在背景執行
    options.add_argument("--headless")
    # 關閉 GPU 加速降低報錯機率
    options.add_argument("--disable-gpu")
    # 設定視窗解析度，確保響應式網站載入電腦版排版
    options.add_argument("window-size=1920,1080")
    # 關閉自動化標籤，降低被反爬蟲系統阻擋的機率
    options.add_argument("--disable-blink-features=AutomationControlled")
    # 偽裝成一般電腦使用者的 User-Agent
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36")
    
    # 🌟 核心修改：移除 ChromeDriverManager，直接把 options 餵給 Chrome
    return webdriver.Chrome(options=options)

# 定義類別與假到期日的產生函式
def parse_category_and_expiry(title):
    category = "其他" # 預設類別
    if any(k in title for k in ["咖啡", "拿鐵", "美式", "卡布奇諾"]): category = "咖啡"
    elif any(k in title for k in ["冰品", "霜淇淋", "冰棒", "雪糕", "聖代"]): category = "冰品"
    elif any(k in title for k in ["乳品", "鮮奶", "牛奶", "優酪乳"]): category = "乳品"
    elif any(k in title for k in ["啤酒", "生啤酒", "水果酒", "精釀", "發泡酒"]): category = "啤酒"
    elif any(k in title for k in ["飲料", "茶", "水", "果汁", "汽水", "奶茶"]): category = "飲料"
    # 生成 3 到 14 天內的隨機日期作為到期日
    expiry_date = (datetime.date.today() + datetime.timedelta(days=random.randint(3, 14))).strftime("%Y-%m-%d")
    return category, expiry_date

# 全家爬蟲主邏輯
def crawl_family():
    # 設定全家活動頁面網址
    base_url = "https://www.family.com.tw/Marketing/zh/Event"
    events = [] # 建立存放結果的空清單
    driver = create_driver() # 呼叫函式建立瀏覽器物件
    
    try:
        # 印出狀態提示
        print(f"🌍 正在深入爬取 全家超商 ({base_url})...")
        # 前往全家活動頁
        driver.get(base_url)
        # 等待 5 秒讓 JavaScript 載入初始畫面
        time.sleep(5)
        
        # 模擬往下滑動的動作，用來載入延遲圖片
        for _ in range(6):
            driver.execute_script("window.scrollBy(0, 600);") # 向下滾動
            time.sleep(1.5) # 暫停等待載入
        # 滾動完畢後將視窗拉回最頂端
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)

        # 使用 lxml 解析器處理抓下來的原始碼
        soup = BeautifulSoup(driver.page_source, "lxml")
        seen_images = set() # 用於防重複圖片的集合
        # 取得所有 <a> 連結標籤與 <div> 區塊標籤
        all_elements = soup.select("a, div")
        
        # 逐一檢驗找到的標籤
        for tag in all_elements:
            try:
                # 取得連結，沒有則為空字串
                link = tag.get("href", "").strip() if tag.name == "a" else (tag.find("a").get("href", "").strip() if tag.find("a") else "")
                # 防呆處理，將不完整連結轉為絕對連結
                absolute_link = base_url if not link or link == "#" or "javascript" in link.lower() else urljoin(base_url, link)
                
                img_tag = tag.find("img") # 尋找圖片標籤
                img_url = ""
                if img_tag:
                    # 優先抓取資料屬性，避免只抓到懶加載的預留圖示
                    img_url = (img_tag.get("data-src") or img_tag.get("data-original") or img_tag.get("src") or "").strip()
                
                # 如果找不到 img 標籤，改往 style 裡面的 background-image 找圖片網址
                if not img_url and "background-image" in tag.get("style", ""):
                    match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', tag.get("style", ""))
                    if match: img_url = match.group(1).strip()
                    
                if not img_url: continue # 沒有圖片直接略過這筆
                img_url = urljoin(base_url, img_url) # 處理成絕對路徑

                # 如果圖片包含黑名單字眼或已經看過了，則略過
                if any(word in img_url.lower() for word in FILTER_KEYWORDS) or "logo" in img_url.lower() or img_url in seen_images:
                    continue

                # 嘗試抓取各種文字作為標題來源
                alt_text = img_tag.get("alt", "").strip() if img_tag else ""
                title_text = tag.get("title", "").strip() if tag.name == "a" else ""
                block_text = tag.get_text(strip=True).strip()
                
                # 組裝最終活動標題
                event_title = alt_text or title_text or block_text or "全家最新活動"
                combined_text = (alt_text + " " + title_text + " " + block_text).lower()

                # 先驗證是否在目標白名單內
                if any(key.lower() in combined_text for key in TARGET_KEYWORDS):
                    is_target_event = True
                # 再驗證是否包含黑名單
                elif any(key.lower() in combined_text for key in FILTER_KEYWORDS):
                    is_target_event = False  
                else:
                    # 最後檢查網址本身有沒有活動特徵字眼
                    url_text = (absolute_link + img_url).lower()
                    is_target_event = any(k in url_text for k in ["event", "activity", "campaign", "promo", "banner"])

                # 如果判定是活動，且標題長度合理
                if is_target_event and len(event_title) >= 2:
                    category, expiry = parse_category_and_expiry(event_title) # 解析類別與期限
                    events.append({ # 塞入結果清單
                        "store": "全家",
                        "title": event_title[:40],
                        "img_url": img_url,
                        "link": absolute_link,
                        "category": category,
                        "expiry_date": expiry
                    })
                    seen_images.add(img_url) # 加入已看過清單
            except Exception:
                pass # 出錯不中斷
    finally:
        driver.quit() # 保證關閉瀏覽器
        
    print(f"✅ 全家 爬取完成！共抓到 {len(events)} 筆活動。") # 結束提示
    return events # 傳回資料

# 若為直接執行則印出爬取內容
if __name__ == "__main__":
    results = crawl_family()
    for idx, item in enumerate(results, 1):
        print(f"[{idx}] {item['title']} | 分類: {item['category']} | 連結: {item['link']}")