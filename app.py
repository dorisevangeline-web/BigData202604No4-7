import os
import time
import sqlite3
import random
import json
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from datetime import datetime, timedelta
import os
import google.generativeai as genai



# 載入環境變數
load_dotenv()

# 🌟 從外部獨立爬蟲模組中匯入
from spider_711 import crawl_711
from spider_family import crawl_family
from spider_hilife import crawl_hilife
from spider_okmart import crawl_okmart
from spider_pxmart import crawl_pxmart

app = Flask(__name__)
DB_FILE = 'events.db'

# 初始化 Gemini API
API_KEY = os.environ.get("GEMINI_API_KEY")
HAS_AI = False
if API_KEY:
    genai.configure(api_key=API_KEY)
    # 推薦使用穩定且免費額度充足的 1.5-flash，避免 2.5 版頻繁出現 429 限制
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    HAS_AI = True

# ==========================================
# 0. 
# 初始化全域變數，紀錄上次成功爬蟲的時間
# 設為過去的時間，確保第一次請求時會觸發
# ==========================================

last_run_time = datetime(2000, 1, 1)

@app.route('/api/update')
def update_events():
    global last_run_time
    
    # 邏輯：檢查距離上次更新是否已超過 20 小時 (約一天一次&報告前更新的時間差)
    # 不設 24 小時是為了給予彈性空間
    if datetime.now() - last_run_time < timedelta(hours=20):
        return jsonify({"status": "skipped", "message": "尚未達到更新間隔"}), 200
    
    # 執行您的爬蟲與資料庫更新邏輯
    data = fetch_all_events() # 您原本的爬蟲函數
    
    # ... (資料庫寫入邏輯) ...
    #跳最後接last_run_time = datetime.now()
    
    



# ==========================================
# 1. 資料庫初始化 (升級收藏夾架構)
# ==========================================
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS promotions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, store TEXT, title TEXT, 
                        img_url TEXT, link TEXT, category TEXT, expiry_date TEXT)''')
        
        # 🌟 修正：收藏夾改用 store + title 複合式唯一鍵，爬蟲更新後不丟失
        c.execute('''CREATE TABLE IF NOT EXISTS favorites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        store TEXT, 
                        title TEXT,
                        UNIQUE(store, title))''')
                        
        c.execute('''CREATE TABLE IF NOT EXISTS user_behavior_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        action_type TEXT, 
                        target_title TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

def log_behavior(action_type, target_title):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO user_behavior_logs (action_type, target_title) VALUES (?, ?)", (action_type, target_title))
        conn.commit()

# ==========================================
# 2. 爬蟲總調度
# ==========================================
def fetch_all_events():
    events_data = []
    print("\n🚀 啟動全通路 AI 優惠爬蟲系統")
    spiders = [crawl_711, crawl_family, crawl_hilife, crawl_okmart, crawl_pxmart]
    for spider in spiders:
        try:
            data = spider()
            events_data.extend(data)
        except Exception as e:
            print(f"❌ {spider.__name__} 執行發生錯誤: {e}")
    return events_data

# ==========================================
# 3. 基礎 API 路由
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/update')
def update_events():
    data = fetch_all_events()
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM promotions")
        for item in data:
            c.execute("INSERT INTO promotions (store, title, img_url, link, category, expiry_date) VALUES (?, ?, ?, ?, ?, ?)",
                      (item.get('store'), item.get('title'), item.get('img_url'), item.get('link'), item.get('category'), item.get('expiry_date')))
        conn.commit()
    log_behavior("update_spiders", "ALL")
    return jsonify({"status": "success", "count": len(data)})

@app.route('/api/promotions')
def get_promotions():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # 🌟 修正：透過 store 與 title 比對收藏狀態
        c.execute('''SELECT p.*, CASE WHEN f.id IS NOT NULL THEN 1 ELSE 0 END as is_favorite 
                     FROM promotions p 
                     LEFT JOIN favorites f ON p.store = f.store AND p.title = f.title''')
        return jsonify([dict(row) for row in c.fetchall()])

# 🌟 新增/修復：專門處理 /api/favorites/list 路由，防止前端 404 崩潰
@app.route('/api/favorites/list')
def get_favorites_list():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('''SELECT p.*, 1 as is_favorite 
                     FROM promotions p 
                     JOIN favorites f ON p.store = f.store AND p.title = f.title''')
        return jsonify([dict(row) for row in c.fetchall()])

@app.route('/api/favorites', methods=['POST', 'DELETE'])
def manage_favorites():
    data = request.json or {}
    store = data.get('store')
    title = data.get('title')
    
    if not store or not title: 
        return jsonify({"status": "error", "message": "缺少 store 或 title"}), 400

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        if request.method == 'POST':
            c.execute("INSERT OR IGNORE INTO favorites (store, title) VALUES (?, ?)", (store, title))
            conn.commit()
            log_behavior("add_favorite", f"{store} - {title}")
            return jsonify({"status": "success"})
        elif request.method == 'DELETE':
            c.execute("DELETE FROM favorites WHERE store = ? AND title = ?", (store, title))
            conn.commit()
            log_behavior("remove_favorite", f"{store} - {title}")
            return jsonify({"status": "success"})

# ==========================================
# 4. 真．AI 功能：單一商品語意深度分析
# ==========================================
@app.route('/api/analyze', methods=['POST'])
def ai_analyze():
    data = request.json or {}
    title = data.get('title', '未知商品')
    store = data.get('store', '')
    
    log_behavior("ai_analyze", title)

    if not HAS_AI:
        return jsonify({"analysis": f"<div style='color:#d35400;'>⚠️ 未偵測到 GEMINI_API_KEY，使用基礎模式。<br>商品：{title}<br>通路：{store}</div>"})

    prompt = f"""
    你是一個精打細算的超商優惠分析專家。
    請分析以下商品優惠，並用流暢、生動、接地氣的台灣用語回覆。
    通路：{store}
    商品與活動標題：{title}

    請直接輸出 HTML 格式（不需要 Markdown 標記，不要有 ```html），包含以下結構：
    1. <strong>🔥 優惠解碼：</strong> 說明這個折扣到底等於打幾折，划不划算。
    2. <strong>💡 採購建議：</strong> 給出具體的建議。
    3. <strong>⚠️ 溫馨提醒：</strong> 根據商品特性給予一句健康的幽默提醒。
    """
    try:
        response = model.generate_content(prompt)
        html_content = response.text.replace("```html", "").replace("```", "").strip()
        return jsonify({"analysis": html_content})
    except Exception as e:
        return jsonify({"analysis": f"AI 模型暫時無法連線：{str(e)}"})

# ==========================================
# 5. 真．AI 功能：跨通路購物車總價最佳化
# ==========================================
@app.route('/api/optimize-cart', methods=['POST'])
def ai_optimize_cart():
    user_query = request.json.get('query', '')
    log_behavior("optimize_cart", user_query)

    if not HAS_AI:
        return jsonify({"result": "<div style='color:#d35400;'>⚠️ 請先設定 GEMINI_API_KEY 才能啟動！</div>"})

    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT store, title, category FROM promotions')
        all_promos = [dict(row) for row in c.fetchall()]

    promo_context = json.dumps(all_promos, ensure_ascii=False)

    prompt = f"""
    你是一個超級省錢大師。使用者想要買以下的商品清單：
    「{user_query}」

    目前市面上有以下優惠活動（JSON格式）：
    {promo_context}

    請幫使用者配對資料庫中的優惠，規劃出「最省錢的跨通路購買策略」。
    請直接輸出 HTML 格式（不需要 Markdown 標記），結構如下：
    <div style="background: #e8f8f5; padding: 15px; border-radius: 8px;">
        <h4 style="color: #16a085; margin-top:0;">🛒 您的專屬省錢攻略</h4>
        <ul>
            <li><strong>[某通路]</strong> 買 [商品] (因為有 [活動])</li>
        </ul>
        <p style="margin-bottom:0; color:#2c3e50;"><strong>總結建議：</strong> [給予使用者的路線或採買建議]</p>
    </div>
    """
    try:
        response = model.generate_content(prompt)
        html_content = response.text.replace("```html", "").replace("```", "").strip()
        return jsonify({"result": html_content})
    except Exception as e:
        return jsonify({"result": f"AI 運算失敗：{str(e)}"})

if __name__ == '__main__':
    print("⚙️ 正在初始化系統與資料庫...")
    init_db()
    print("✅ 系統啟動成功！請開啟瀏覽器訪問: [http://127.0.0.1:8080](http://127.0.0.1:8080)")
    app.run(host='0.0.0.0', port=8080, debug=False)

last_run_time = datetime.now()
    return jsonify({"status": "success", "count": len(data)})