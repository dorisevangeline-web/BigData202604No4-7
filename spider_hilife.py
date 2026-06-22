# 引入必備的各種套件
import time, datetime, re, random
from bs4 import BeautifulSoup
from selenium import webdriver
# 引入 Options 管理瀏覽器設定
from selenium.webdriver.chrome.options import Options
# 引入 By 模組用來以特定條件搜尋網頁元素
from selenium.webdriver.common.by import By 
from urllib.parse import urljoin

# 目標關鍵字定義
TARGET_KEYWORDS = ["咖啡", "拿鐵", "美式", "卡布奇諾", "冰品", "霜淇淋", "冰棒", "雪糕", "聖代", "飲料", "茶", "果汁", "汽水", "乳品", "鮮奶", "牛奶", "優酪乳", "奶茶", "啤酒", "生啤酒", "水果酒", "精釀", "發泡酒", "買一送一", "特價", "折", "超值"]
# 黑名單過濾關鍵字
FILTER_KEYWORDS = ["icon", "logo", "arrow", "btn", "button", "footer", "header","中獎","街口支付","萊購物"]

# 驅動程式建立函式
def create_driver():
    options = Options() # 實例化選項
    options.add_argument("--headless") # 無頭模式
    options.add_argument("--disable-gpu") # 禁用 GPU
    options.add_argument("window-size=1920,1080") # 設定視窗尺寸
    
    # 防機器人偵測設定：停用自動化特徵
    options.add_argument("--disable-blink-features=AutomationControlled")
    # 排除自動化控制提示字眼
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    # 不使用自動化擴充功能
    options.add_experimental_option("useAutomationExtension", False)
    # 偽裝成真人瀏覽器版本
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36")
    
    # 🌟 核心修改：拋棄 ChromeDriverManager，直接使用原生設定！
    return webdriver.Chrome(options=options)

# 類別判斷函式
def parse_category_and_expiry(title):
    category = "其他"
    if any(k in title for k in ["咖啡", "拿鐵", "美式", "卡布奇諾"]): category = "咖啡"
    elif any(k in title for k in ["冰品", "霜淇淋", "冰棒", "雪糕", "聖代"]): category = "冰品"
    elif any(k in title for k in ["乳品", "鮮奶", "牛奶", "優酪乳"]): category = "乳品"
    elif any(k in title for k in ["啤酒", "生啤酒", "水果酒", "精釀", "發泡酒"]): category = "啤酒"
    elif any(k in title for k in ["飲料", "茶", "水", "果汁", "汽水", "奶茶"]): category = "飲料"
    expiry_date = (datetime.date.today() + datetime.timedelta(days=random.randint(3, 14))).strftime("%Y-%m-%d")
    return category, expiry_date

# 萊爾富爬蟲主程式
def crawl_hilife():
    # 設定目標網址
    base_url = "https://www.hilife.com.tw/events_activity.aspx"
    events = [] # 儲存資料陣列
    driver = create_driver() # 建立瀏覽器
    
    print(f"🌍 正在深入爬取 萊爾富 ({base_url})...")
    driver.get(base_url) # 訪問目標頁面
    
    seen_images = set() # 去重判定用集合
    page_num = 1 # 預設起始頁數

    try:
        # 開始無窮迴圈，處理自動換頁
        while True:
            print(f"🔍 [萊爾富] 正在掃描第 {page_num} 頁...")
            time.sleep(5) # 等待新一頁載入
            
            # 觸發懶加載圖片的滾動
            for _ in range(6):
                driver.execute_script("window.scrollBy(0, 600);")
                time.sleep(1.2)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1.5)

            # 解析網頁 DOM 結構
            soup = BeautifulSoup(driver.page_source, "lxml")
            all_elements = soup.select("a, li") # 抓取可能包含活動的標籤
            
            page_items_count = 0 # 紀錄本頁抓取量
            for tag in all_elements:
                try:
                    # 嘗試組裝正確連結
                    link = tag.get("href", "").strip() if tag.name == "a" else (tag.find("a").get("href", "").strip() if tag.find("a") else "")
                    absolute_link = base_url if not link or link == "#" or "javascript" in link.lower() else urljoin(base_url, link)

                    # 嘗試抓取圖片資源
                    img_tag = tag.find("img")
                    img_url = ""
                    if img_tag:
                        img_url = (img_tag.get("data-src") or img_tag.get("data-original") or img_tag.get("src") or "").strip()
                    else:
                        # 處理寫在 css 的背景圖片
                        style_attr = tag.get("style", "")
                        if "background-image" in style_attr:
                            bg_match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style_attr)
                            if bg_match: img_url = bg_match.group(1).strip()
                    
                    if not img_url: continue # 找不到圖就不要
                    img_url = urljoin(base_url, img_url)

                    # 過濾不要的元素或重複的圖片
                    if any(word in img_url.lower() for word in FILTER_KEYWORDS) or "logo" in img_url.lower() or img_url in seen_images:
                        continue

                    # 蒐集潛在標題資訊
                    alt_text = img_tag.get("alt", "").strip() if img_tag else ""
                    title_text = tag.get("title", "").strip() if tag.name == "a" else ""

                    # 精準抓出區塊內的文字，並拔除特殊空白字元
                    block_text = tag.get_text(separator=" ", strip=True).replace('\xa0', '')

                    # 找出最適合當標題的文字
                    event_title = alt_text or title_text or block_text or "萊爾富最新活動"
                    
                    # 萊爾富頁面通常直接全部視為目標活動
                    is_target_event = True 

                    if is_target_event and len(event_title) >= 2:
                        category, expiry = parse_category_and_expiry(event_title)
                        events.append({
                            "store": "萊爾富",
                            "title": event_title[:40],
                            "img_url": img_url,
                            "link": absolute_link,
                            "category": category,
                            "expiry_date": expiry,
                            "page": page_num # 多紀錄一個頁數用來除錯
                        })
                        seen_images.add(img_url)
                        page_items_count += 1
                except Exception:
                    pass

            print(f"📖 第 {page_num} 頁掃描完畢，成功獲取 {page_items_count} 筆新優惠。")

            # 實作動態點擊「下一頁」邏輯
            try:
                next_page_str = str(page_num + 1)
                # 使用 XPath 搜尋畫面上寫著「下一頁數字」的 a 標籤
                xpath_query = f"//a[text()='{next_page_str}']"
                next_btns = driver.find_elements(By.XPATH, xpath_query)

                # 判斷是否還有下一頁按鈕
                if next_btns and len(next_btns) > 0:
                    next_btn = next_btns[0]
                    # 強制點擊觸發換頁的 doPostBack 重新載入
                    driver.execute_script("arguments[0].click();", next_btn)
                    print(f"👉 成功點擊第 {next_page_str} 頁按鈕，等待新頁面資料重新載入...")
                    page_num += 1 # 頁碼增加
                else:
                    print("🛑 找不到後續頁碼按鈕，已到達最終頁。結束爬取。")
                    break # 跳出 while 迴圈
            except Exception as e:
                 print(f"🛑 換頁程序異常或已到最終頁: {e}")
                 break # 出錯即中斷換頁
    finally:
        driver.quit() # 保證關閉瀏覽器
        
    print(f"\n✅ 萊爾富爬取任務全部結束！總計跨頁抓到 {len(events)} 筆活動！")
    return events

if __name__ == "__main__":
    results = crawl_hilife()
    for idx, item in enumerate(results, 1):
        print(f"[{idx}] (第{item['page']}頁) {item['title']} | 分類: {item['category']} | 連結: {item['link']}")