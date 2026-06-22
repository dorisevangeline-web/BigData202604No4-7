# 1. 指定使用 Python 3.9 的精簡版
FROM python:3.9-slim

# 2. 安裝必要的系統套件 (這是爬蟲必備)
    #Chromium 及必要相依函式庫
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# 3. 設定工作目錄
WORKDIR /app

# 4. 把您 GitHub 上的所有程式碼複製進去
COPY . .

# 5. 安裝 Python 套件
RUN pip install --no-cache-dir -r requirements.txt

# 6. 啟動命令 
    # 改用 gunicorn 執行
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "120", "app:app"]