# 引入時間、隨機數、日期時間、正則表達式等標準函式庫
import time, random, datetime, re
# 引入 BeautifulSoup 來解析 HTML 結構
from bs4 import BeautifulSoup
# 引入 Selenium 的 webdriver 核心模組
from selenium import webdriver
# 引入 Options 模組來設定 Chrome 啟動參數
from selenium.webdriver.chrome.options import Options
# 引入 urljoin 來組合相對與絕對網址
from urllib.parse import urljoin

# 定義要抓取的目標關鍵字清單
TARGET_KEYWORDS = ["咖啡", "拿鐵", "美式", "卡布奇諾", "冰品", "霜淇淋", "冰棒", "雪糕", "聖代", "飲料", "茶", "果汁", "汽水", "乳品", "鮮奶", "牛奶", "優酪乳", "奶茶", "啤酒", "生啤酒", "水果酒", "精釀", "發泡酒", "買一送一", "特價", "折", "超值","摩卡","國際啤酒節","0604happybeer"]
# 定義要排除的黑名單關鍵字清單，用來過濾無效圖片或連結
FILTER_KEYWORDS = ["icon", "logo", "arrow", "btn", "button", "footer", "header", "facebook", "instagram", "循環杯", "中獎","頂級好米","the taste of home always with you","open!plaza", "開幕主題活動","op","提袋","循環杯","1212kid"]

# 定義解析分類與假造到期日的函式
def parse_category_and_expiry(title):
    # 預設分類為「其他」
    category = "其他"
    # 如果標題包含咖啡相關字眼，歸類為「咖啡」
    if any(k in title for k in ["咖啡", "拿鐵", "美式", "卡布奇諾"]): category = "咖啡"
    # 如果標題包含冰品相關字眼，歸類為「冰品」
    elif any(k in title for k in ["冰品", "霜淇淋", "冰棒", "雪糕", "聖代"]): category = "冰品"
    # 如果標題包含乳品相關字眼，歸類為「乳品」
    elif any(k in title for k in ["乳品", "鮮奶", "牛奶", "優酪乳"]): category = "乳品"
    # 如果標題包含啤酒相關字眼，歸類為「啤酒」
    elif any(k in title for k in ["啤酒", "生啤酒", "水果酒", "精釀", "發泡酒"]): category = "啤酒"
    # 如果標題包含飲料相關字眼，歸類為「飲料」
    elif any(k in title for k in ["飲料", "茶", "水", "果汁", "汽水", "奶茶"]): category = "飲料"
    
    # 隨機產生 3 到 14 天後的日期作為假造到期日
    expiry = (datetime.date.today() + datetime.timedelta(days=random.randint(3, 14))).strftime("%Y-%m-%d")
    # 回傳分類與到期日
    return category, expiry

# 定義 7-11 爬蟲主函式
def crawl_711():
    # 設定要爬取的目標網址清單
    urls = ["https://www.7-11.com.tw/special/newsList.aspx", "https://www.citycafe.com.tw/notice.aspx"]
    # 建立一個空列表來儲存爬到的活動資料
    events = []
    
    # 建立 Options 物件來設定 Chrome 參數
    options = Options()
    # 設定無頭模式（背景執行不開視窗）
    options.add_argument("--headless")
    # 停用 GPU 加速以減少錯誤
    options.add_argument("--disable-gpu")
    # 設定虛擬視窗大小
    options.add_argument("window-size=1920,1080")
    
    # 🌟 核心修改：直接呼叫 webdriver.Chrome，不再使用 ChromeDriverManager！
    # Selenium 4.6+ 會自動在底層幫你處理驅動程式的下載與配對
    driver = webdriver.Chrome(options=options)
    
    try:
        # 逐一造訪目標網址清單中的網址
        for base_url in urls:
            # 印出目前正在爬取的網址提示
            print(f"🌍 正在深入爬取 7-11 ({base_url})...")
            # 讓瀏覽器前往該網址
            driver.get(base_url)
            # 暫停 5 秒等待頁面載入
            time.sleep(5)
            # 迴圈執行 6 次滾動指令，觸發懶加載圖片
            for _ in range(6): 
                # 執行 JavaScript 向下滾動 600 像素
                driver.execute_script("window.scrollBy(0, 600);")
                # 暫停 1.5 秒讓圖片載入
                time.sleep(1.5)
            
            # 使用 BeautifulSoup 解析網頁原始碼
            soup = BeautifulSoup(driver.page_source, "html.parser")
            # 建立一個集合來記錄已經看過的圖片網址，避免重複
            seen_images = set()
            
            # 選取所有 a (連結) 和 div 標籤進行巡覽
            for tag in soup.select("a, div"):
                try:
                    # 1. 如果是 a 標籤則直接取 href，若是 div 則往下找 a 取 href
                    link = tag.get("href", "").strip() if tag.name == "a" else (tag.find("a").get("href", "").strip() if tag.find("a") else "")
                    
                    # 2. 針對 7-11 特定活動頁面進行 JavaScript 語法過濾與解析
                    if base_url == "https://www.7-11.com.tw/special/newsList.aspx":
                        # 擷取以 javascript 開頭的彈出視窗參數
                        if "javascript:galogopenwin" in link.lower():
                            matches = re.findall(r"'([^']+)'", link)
                            if len(matches) >= 3:
                                link = matches[2]  # 將連結替換為擷取到的真實網址參數
                        
                        # 組裝成絕對連結，防呆處理空連結或井號
                        absolute_link = base_url if not link or link == "#" or link.lower().startswith("javascript") else urljoin(base_url, link)
                    else:
                        # City Cafe 等其他頁面的預設網址處理方式
                        absolute_link = base_url if not link or link == "#" or "javascript" in link.lower() else urljoin(base_url, link)
                    
                    # 尋找底下的 img 圖片標籤
                    img_tag = tag.find("img")
                    # 優先抓 data-src，沒有才抓 src
                    img_url = (img_tag.get("data-src") or img_tag.get("src") or "").strip() if img_tag else ""
                    # 如果沒有圖片網址就跳過這回合
                    if not img_url: continue
                    # 將相對圖片網址補齊為絕對網址
                    img_url = "https:" + img_url if img_url.startswith("//") else urljoin(base_url, img_url)

                    # 過濾包含黑名單字眼或已經看過的圖片網址
                    if any(w in img_url.lower() for w in FILTER_KEYWORDS) or img_url in seen_images: continue

                    # 嘗試取得 title 或 alt 屬性當作活動標題
                    title_text = tag.get("title", "").strip() if tag.name == "a" else ""
                    alt_text = img_tag.get("alt", "").strip() if img_tag else ""
                    # 綜合以上資訊當作標題，若無則給預設值
                    event_title = alt_text or title_text or tag.get_text(strip=True).strip() or "7-11 最新活動"
                    # 將所有文字串聯轉為小寫，準備比對
                    combined_text = (alt_text + " " + title_text + " " + tag.get_text(strip=True).strip()).lower()

                    # 判定是否為目標活動：若中黑名單則否，中白名單則是，最後透過網址內是否包含 event 等字眼判定
                    if any(k in combined_text for k in FILTER_KEYWORDS): is_target = False
                    elif any(k in combined_text for k in TARGET_KEYWORDS): is_target = True
                    else: is_target = any(k in (absolute_link + img_url).lower() for k in ["event", "activity", "promo"])

                    # 若為目標活動且標題長度合理
                    if is_target and len(event_title) >= 2:
                        # 呼叫函式取得分類與到期日
                        cat, exp = parse_category_and_expiry(event_title)
                        # 將此筆資料存入結果清單中
                        events.append({"store": "7-11", "title": event_title[:40], "img_url": img_url, "link": absolute_link, "category": cat, "expiry_date": exp})
                        # 將圖片加入已看過清單避免重複抓取
                        seen_images.add(img_url)
                except: 
                    # 發生錯誤時直接略過，不中斷迴圈
                    pass
    finally:
        # 確保最後一定要關閉瀏覽器，釋放資源
        driver.quit()
    # 印出最終抓取總數
    print(f"✅ 7-11 爬取完成！共抓到 {len(events)} 筆。")
    # 回傳抓取結果清單
    return events

# 若此腳本作為主程式執行時，印出結果
if __name__ == "__main__":
    result_data = crawl_711()
    for item in result_data:
        print(item)