# 引入相關標準套件
import time, random, datetime, re
from bs4 import BeautifulSoup
from selenium import webdriver
# 引入設定選項套件
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin

# 定義過濾字眼，包含一些不代表活動的裝飾性或說明文字
FILTER_KEYWORDS = ["icon", "logo", "arrow", "btn", "button", "footer", "header", "svg", "facebook", "了解更多", "瞭解更多", "詳細資訊", "馬上看", "中獎", "最新消息","活動日期"]

# 定義一個獨立的標題清洗函式
def get_clean_title(tag):
    """精準提取與清洗標題的函式"""
    # 1. 優先掃描標籤內有沒有標準的 HTML 標題格式 (h2~h5) 或是加粗標籤
    heading = tag.find(["h2", "h3", "h4", "h5", "strong"])
    # 找到的話就拿出來，同時取代掉特殊網頁空白
    if heading and heading.get_text(strip=True):
        return heading.get_text(strip=True).replace('\xa0', '')
    
    # 2. 如果沒標題標籤，就把區塊內所有字印出來，使用換行符號隔開
    raw_text = tag.get_text(separator="\n", strip=True).replace('\xa0', '')
    # 切割字串並剔除長度太短的廢字元
    lines = [line.strip() for line in raw_text.split('\n') if len(line.strip()) > 2]
    
    # 3. 把看起來像是日期的句子以及帶有黑名單字眼的句子給過濾掉
    valid_lines = [l for l in lines if not re.search(r'\d{2,4}[/.-]\d{1,2}', l) and not any(kw in l for kw in FILTER_KEYWORDS)]
    
    # 回傳清洗後殘存的第一句當標題，沒東西就回傳空字串
    return valid_lines[0] if valid_lines else ""

# 判定分類與假到期日的邏輯
def parse_category_and_expiry(title):
    category = "其他"
    if any(k in title for k in ["咖啡", "拿鐵", "美式"]): category = "咖啡"
    elif any(k in title for k in ["冰品", "霜淇淋"]): category = "冰品"
    elif any(k in title for k in ["飲料", "茶"]): category = "飲料"
    
    expiry = (datetime.date.today() + datetime.timedelta(days=random.randint(3, 14))).strftime("%Y-%m-%d")
    return category, expiry

# 全聯爬蟲主程式
def crawl_pxmart():
    # 全聯最新好物推薦頁面
    base_url = "https://www.pxmart.com.tw/campaign/life-will/best-buy/recommend"
    events = [] # 建立清單
    
    options = Options()
    options.add_argument("--headless") # 背景運行
    options.add_argument("window-size=1920,1080")
    
    # 增強的反爬蟲參數，避免全聯阻擋我們
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36")
    
    # 🌟 核心修改：移除 webdriver_manager，直接用 webdriver.Chrome 包覆 options 即可！
    driver = webdriver.Chrome(options=options)
    
    try:
        print(f"🌍 正在深入爬取 全聯 ({base_url})...")
        driver.get(base_url)
        time.sleep(5) # 確保 SPA (單頁應用) 的首頁內容已由 JS 渲染完畢
        
        # 執行 6 次滾動來強迫頁面載入隱藏圖片
        for _ in range(6): 
            driver.execute_script("window.scrollBy(0, 600);")
            time.sleep(1.5)
        
        # 解析 DOM
        soup = BeautifulSoup(driver.page_source, "lxml")
        seen_images = set()
        
        # 搜尋 a, div 以及 li 標籤，因為全聯排版可能用到 list 元素
        for tag in soup.select("a, div, li"):
            try:
                # 🛠️ 防呆過濾邏輯：若該區塊內部包含了超過一個連結或超過一張圖，
                # 代表這是「大外框 (container)」，要直接跳過避免資訊全黏在一起
                if len(tag.find_all("a")) > 1 or len(tag.find_all("img")) > 1:
                    continue

                # 找尋唯一那張圖片
                img_tag = tag.find("img")
                img_url = img_tag.get("src", "").strip() if img_tag else ""
                
                # 如果 img 找不到網址，試試看有沒有寫在 CSS background-image
                if not img_url and "background-image" in tag.get("style", ""):
                    match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', tag.get("style", ""))
                    if match: img_url = match.group(1).strip()
                    
                if not img_url: continue # 依然沒圖片就忽略此輪
                img_url = urljoin(base_url, img_url)

                # 黑名單過濾與重複判定
                if any(w in img_url.lower() for w in FILTER_KEYWORDS) or img_url in seen_images: 
                    continue

                # 🛠️ 運用自訂函式取得乾淨的標題
                title = get_clean_title(tag)
                
                # 標題品質控管：少於兩個字或夾帶黑名單說明文，直接拋棄不收
                if len(title) < 2 or any(k in title for k in FILTER_KEYWORDS):
                    continue
                
                # 嘗試組合跳轉連結
                link = tag.get("href", "") if tag.name == "a" else (tag.find("a").get("href", "") if tag.find("a") else "")
                abs_link = urljoin(base_url, link) if link else base_url
                
                # 取得類別以及設定好的到期日
                cat, exp = parse_category_and_expiry(title)
                
                # 組成 Dictionary 放進列表中
                events.append({
                    "store": "全聯", 
                    "title": title[:40], # 確保標題不至於超長
                    "img_url": img_url, 
                    "link": abs_link, 
                    "category": cat, 
                    "expiry_date": exp
                })
                seen_images.add(img_url) # 加進歷史紀錄
            except Exception: 
                pass # 有例外就跳過此標籤
                
    finally:
        driver.quit() # 最後一定要斷線
        
    print(f"✅ 全聯 爬取完成！共抓到 {len(events)} 筆。")
    return events

# 獨立測試運行時使用的啟動碼
if __name__ == "__main__":
    results = crawl_pxmart()
    for idx, item in enumerate(results, 1):
        print(f"[{idx}] {item['title']} | 分類: {item['category']} | 連結: {item['link']}")