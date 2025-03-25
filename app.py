from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
import json
import re
import random
import requests
import concurrent.futures
import itertools
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
        for share_link in SHARE_LINKS:
            try:
                file_id = extract_file_id(share_link)
                if file_id:
                    file_data = load_json_from_google_drive(file_id)
                    for item in file_data:
                        yield item
                        if max_items and max_items <= 0:
                            return
                    max_items -= len(file_data)
            except Exception as e:
                print(f"載入 {share_link} 時出錯: {e}")
    
    # 將生成器轉換為列表
    return list(itertools.islice(data_generator(), max_items))

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

# 其餘程式碼保持不變
def detect_language(text):
    """改進的語言檢測"""
    if not text or not isinstance(text, str) or text.strip() == "":
        return "unknown"
    
    text = text.strip()
    
    # 計算不同語言字符的數量
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    japanese_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text))
    korean_chars = len(re.findall(r'[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f\ua960-\ua97f\ud7b0-\ud7ff]', text))
    
    # 語言偵測邏輯
    lang_counts = {
        'chinese': chinese_chars,
        'japanese': japanese_chars,
        'korean': korean_chars
    }
    
    # 如果有非英文字符
    total_non_english = sum(lang_counts.values())
    if total_non_english > 0:
        max_lang = max(lang_counts.items(), key=lambda x: x[1])
        if max_lang[1] > 0:
            return max_lang[0]
    
    # 檢查拉丁字母
    latin_chars = len(re.findall(r'[a-zA-Z]', text))
    return 'english' if latin_chars > 0 else "unknown"

def translate_text(text, source_lang='auto', target_lang='en'):
    """使用 deep-translator 進行翻譯"""
    try:
        if not text or not isinstance(text, str) or text.strip() == "":
            return text
        
        # 語言映射
        lang_map = {
            'chinese': 'zh-CN', 'english': 'en', 
            'japanese': 'ja', 'korean': 'ko',
            'zh': 'zh-CN', 'en': 'en', 
            'ja': 'ja', 'ko': 'ko',
            'unknown': 'en'
        }
        
        # 標準化語言代碼
        source = lang_map.get(source_lang.lower(), 'auto')
        target = lang_map.get(target_lang.lower(), 'en')
        
        # 分段翻譯長文本
        MAX_LENGTH = 5000
        if len(text) > MAX_LENGTH:
            segments = []
            for i in range(0, len(text), MAX_LENGTH):
                segment = text[i:i+MAX_LENGTH]
                try:
                    translated_segment = GoogleTranslator(source=source, target=target).translate(segment)
                    segments.append(translated_segment)
                except Exception as e:
                    print(f"分段翻譯出錯: {e}")
                    segments.append(segment)
            return ''.join(segments)
        
        # 直接翻譯短文本
        return GoogleTranslator(source=source, target=target).translate(text)
    
    except Exception as e:
        print(f"翻譯出錯: {e}")
        return text

# 剩餘的路由和主程式部分保持不變
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/get_responses', methods=['POST'])
def get_responses():
    # 獲取用戶輸入
    data = request.json
    user_prompt = data.get('prompt', '').strip()
    language = data.get('language', '')
    
    # 偵測語言
    if language == "auto" or not language:
        detected_lang = detect_language(user_prompt)
    else:
        detected_lang = language.lower()
    
    # 找尋匹配
    matches = find_semantic_matches(user_prompt, detected_lang)
    
    if matches:
        best_match = matches[0]
        
        # 翻譯回應
        try:
            # 語言映射
            lang_map = {
                'chinese': 'zh-CN', 'english': 'en', 
                'japanese': 'ja', 'korean': 'ko'
            }
            
            source = lang_map.get(best_match['language'], 'en')
            target = lang_map.get(detected_lang, 'zh-CN')
            
            # 翻譯回應
            if best_match.get('response_a'):
                best_match['response_a'] = translate_text(
                    best_match['response_a'], 
                    source, 
                    target
                )
            
            if best_match.get('response_b'):
                best_match['response_b'] = translate_text(
                    best_match['response_b'], 
                    source, 
                    target
                )
            
            best_match['original_language'] = best_match['language']
            best_match['language'] = detected_lang
            
            return jsonify([best_match])
        
        except Exception as e:
            print(f"回應翻譯失敗: {e}")
            return jsonify([best_match])
    
    # 若無匹配，返回隨機回應
    try:
        random_response = random.choice(chatbot_data)
        
        # 翻譯隨機回應
        source = random_response.get('language', 'en')
        target = detected_lang
        
        if random_response.get('response_a'):
            random_response['response_a'] = translate_text(
                random_response['response_a'], 
                source, 
                target
            )
        
        if random_response.get('response_b'):
            random_response['response_b'] = translate_text(
                random_response['response_b'], 
                source, 
                target
            )
        
        random_response['original_language'] = source
        random_response['language'] = target
        
        return jsonify([random_response])
    
    except Exception as e:
        print(f"隨機回應選取失敗: {e}")
        return jsonify([])

@app.route('/api/languages', methods=['GET'])
def get_languages():
    """取得可用語言列表"""
    languages = set()
    for item in chatbot_data:
        if isinstance(item, dict) and 'language' in item and item['language']:
            languages.add(item['language'])
    languages.add("auto")
    return jsonify(sorted(list(languages)))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
