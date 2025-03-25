import os
import json
import re
import random
import requests
import itertools
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
from deep_translator import GoogleTranslator

app = Flask(__name__)
CORS(app)

# 所有 Google Drive 分享連結
SHARE_LINKS = [
    "https://drive.google.com/file/d/1pMrKzEoZaUDTBMYhhQOmyTPvfLgrtjEc/view?usp=sharing",
    "https://drive.google.com/file/d/12jzL0eZEPsLvEkDJ8HCNcs8msSFGmRdO/view?usp=sharing",
    "https://drive.google.com/file/d/1IUf514vw0IZ_x73lIhPAfwObHaLIjv2M/view?usp=sharing",
    "https://drive.google.com/file/d/1eUijIPsv3bCQy4kyg1rLJh4QkHoKIqGV/view?usp=sharing",
    "https://drive.google.com/file/d/1sgLCgCsI5gff0U_1ltilTLTMyRHbwxzL/view?usp=sharing",
    "https://drive.google.com/file/d/1bKB7RF_yYMTLvSLFpOLuSkiFJp771BuO/view?usp=sharing",
    "https://drive.google.com/file/d/1nCFX78vHXUeAqSK5GP2ys1G0OcUeqaaZ/view?usp=sharing",
    "https://drive.google.com/file/d/1RuDeRC-9cKjVBi5Rd8KX486Nu0j4sXtf/view?usp=sharing",
    "https://drive.google.com/file/d/1UANJMZZI958NSVLXiqICv1kqQHQ7wWmP/view?usp=sharing",
    "https://drive.google.com/file/d/1dSuEA9Y5uEaSygKFJMsghVcWtEcPqvNZ/view?usp=sharing",
    "https://drive.google.com/file/d/1YxGr8p4GFRN-ajDyGbYOP3VOzbswW9iZ/view?usp=sharing",
    "https://drive.google.com/file/d/194I_v6JUUg5nr5WMGTKIXSb765MT_NtL/view?usp=sharing"
]

def extract_file_id(share_link):
    """從 Google Drive 分享連結中提取檔案 ID"""
    match = re.search(r'/d/([a-zA-Z0-9_-]+)/', share_link)
    return match.group(1) if match else None

def load_json_from_google_drive(file_id):
    """從 Google Drive 下載並解析 JSON 檔案"""
    download_url = f"https://drive.google.com/uc?id={file_id}"
    
    try:
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        
        # 直接解碼內容
        content = response.content.decode('utf-8', errors='ignore')
        
        # 清理和解析 JSON
        try:
            # 移除可能導致解析問題的異常字元
            cleaned_content = re.sub(r'[^\x20-\x7E\u4E00-\u9FFF]+', '', content)
            
            # 確保是陣列
            if not cleaned_content.strip().startswith('['):
                cleaned_content = f'[{cleaned_content}]'
            
            # 解析 JSON
            data = json.loads(cleaned_content)
        except json.JSONDecodeError:
            # 嘗試更寬鬆的解析
            cleaned_content = re.sub(r',\s*}', '}', content)
            cleaned_content = re.sub(r',\s*\]', ']', cleaned_content)
            data = json.loads(cleaned_content)
        
        # 篩選有效資料
        valid_data = [
            item for item in data 
            if isinstance(item, dict) and 'prompt' in item
        ]
        
        print(f"成功載入檔案 {file_id}: {len(valid_data)} 筆有效資料")
        return valid_data
    
    except Exception as e:
        print(f"載入檔案 {file_id} 時出錯: {e}")
        return []

def load_json_with_generator(max_items=5000):
    """使用生成器載入資料，控制記憶體使用"""
    def data_generator():
        remaining_items = max_items
        for share_link in SHARE_LINKS:
            try:
                file_id = extract_file_id(share_link)
                if file_id:
                    file_data = load_json_from_google_drive(file_id)
                    for item in file_data:
                        if remaining_items > 0:
                            yield item
                            remaining_items -= 1
                        else:
                            return
            except Exception as e:
                print(f"載入 {share_link} 時出錯: {e}")
    
    # 將生成器轉換為列表
    return list(data_generator())

# 載入資料
try:
    chatbot_data = load_json_with_generator()
    if not chatbot_data:
        raise ValueError("未載入任何有效資料")
except Exception as e:
    print(f"載入資料時發生critical錯誤: {e}")
    # 提供一個預設的空資料集
    chatbot_data = [
        {
            "prompt": "Hello",
            "response_a": "Hi there, how can I help you?",
            "response_b": "Welcome! What would you like to chat about?",
            "language": "english"
        }
    ]

# 其餘函數保持不變（detect_language, translate_text 等）

# 路由部分也保持不變

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
