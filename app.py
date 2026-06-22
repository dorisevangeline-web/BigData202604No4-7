import os
import time
import sqlite3
import random
import json
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from datetime import datetime, timedelta
import google.generativeai as genai

# 1. 載入環境變數
load_dotenv()

# 2. 匯入爬蟲模組
from spider_711 import crawl_711
from spider_family import crawl_family
from spider_hilife import crawl_hilife
from spider_okmart import crawl_okmart
from spider_pxmart import crawl_pxmart

app = Flask(__name__)
DB_FILE = 'events.db'

# 3. 資料庫初始化 (放在這，確保 Gunicorn 啟動時會執行)
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS promotions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, store TEXT, title TEXT, 
                        img_url TEXT, link TEXT, category TEXT, expiry_date TEXT)''')
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

# 在載入應用時立即初始化
init_db()

# 4. 初始化 Gemini API
API_KEY = os.environ.get("GEMINI_API_KEY")
HAS_AI = False
if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash') # 建議改用 1.5-flash
    HAS_AI = True

last_run_time = datetime(2000, 1, 1)

def log_behavior(action_type, target_title):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO user_behavior_logs (action_type, target_title) VALUES (?, ?)", (action_type, target_title))
        conn.commit()

def fetch_all_events():
    events_data = []
    spiders = [crawl_711, crawl_family, crawl_hilife, crawl_okmart, crawl_pxmart]
    for spider in spiders:
        try:
            data = spider()
            events_data.extend(data)
        except Exception as e:
            print(f"❌ {spider.__name__} 執行發生錯誤: {e}")
    return events_data

# ==========================================
# API 路由
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/update')
def update_events():
    global last_run_time
    if datetime.now() - last_run_time < timedelta(hours=20):
        return jsonify({"status": "skipped", "message": "尚未達到更新間隔"}), 200
    
    data = fetch_all_events()
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM promotions")
        for item in data:
            c.execute("INSERT INTO promotions (store, title, img_url, link, category, expiry_date) VALUES (?, ?, ?, ?, ?, ?)",
                      (item.get('store'), item.get('title'), item.get('img_url'), 
                       item.get('link'), item.get('category'), item.get('expiry_date')))
        conn.commit()
    
    log_behavior("update_spiders", "ALL")
    last_run_time = datetime.now()
    return jsonify({"status": "success", "count": len(data)})

@app.route('/api/promotions')
def get_promotions():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('''SELECT p.*, CASE WHEN f.id IS NOT NULL THEN 1 ELSE 0 END as is_favorite 
                     FROM promotions p 
                     LEFT JOIN favorites f ON p.store = f.store AND p.title = f.title''')
        return jsonify([dict(row) for row in c.fetchall()])

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
    if not store or not title: return jsonify({"status": "error"}), 400
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        if request.method == 'POST':
            c.execute("INSERT OR IGNORE INTO favorites (store, title) VALUES (?, ?)", (store, title))
        else:
            c.execute("DELETE FROM favorites WHERE store = ? AND title = ?", (store, title))
        conn.commit()
    return jsonify({"status": "success"})

@app.route('/api/analyze', methods=['POST'])
def ai_analyze():
    data = request.json or {}
    title = data.get('title', '未知商品')
    store = data.get('store', '')
    if not HAS_AI: return jsonify({"analysis": "⚠️ AI未設定"})
    prompt = f"分析優惠：{store} {title}。請輸出 HTML 格式。"
    try:
        response = model.generate_content(prompt)
        return jsonify({"analysis": response.text.replace("```html", "").replace("```", "").strip()})
    except Exception as e:
        return jsonify({"analysis": f"AI錯誤: {str(e)}"})

@app.route('/api/optimize-cart', methods=['POST'])
def ai_optimize_cart():
    user_query = request.json.get('query', '')
    if not HAS_AI: return jsonify({"result": "⚠️ AI未設定"})
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT store, title, category FROM promotions')
        all_promos = [dict(row) for row in c.fetchall()]
    
    prompt = f"購物清單：{user_query}，優惠列表：{json.dumps(all_promos, ensure_ascii=False)}。請規劃最省錢策略並輸出 HTML。"
    try:
        response = model.generate_content(prompt)
        return jsonify({"result": response.text.replace("```html", "").replace("```", "").strip()})
    except Exception as e:
        return jsonify({"result": f"AI錯誤: {str(e)}"})

# Render 使用 Gunicorn 執行，不需要 if __name__ == '__main__':