from flask import Flask, request, jsonify
import json
from flask_cors import CORS
import os
import random
from deep_translator import GoogleTranslator

# 創建 Flask 應用實例
app = Flask(__name__)
CORS(app)  # 允許跨域請求

# 修改 JSON 檔案路徑為環境變數或相對路徑
JSON_FILE_PATH = os.environ.get('JSON_FILE_PATH', 'output.json')

# 載入 JSON 資料的優化版本
def load_data():
    try:
        # 使用更安全的檔案讀取方式
        if not os.path.exists(JSON_FILE_PATH):
            print(f"警告：JSON 檔案 {JSON_FILE_PATH} 不存在")
            return []
        
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # 數據驗證
            if not isinstance(data, list):
                print("警告：JSON 檔案內容不是列表")
                return []
            
            return data
    except json.JSONDecodeError:
        print(f"JSON 解析錯誤：檔案 {JSON_FILE_PATH} 可能格式不正確")
        return []
    except Exception as e:
        print(f"載入 JSON 檔案時出錯: {e}")
        return []

# 全局變數存放資料
chatbot_data = load_data()
print(f"已載入 {len(chatbot_data)} 筆對話資料")

# 統計各語言的數量並找出主要語言
def analyze_language_stats(data):
    language_stats = {}
    for item in data:
        lang = item.get('language', 'unknown').lower()
        language_stats[lang] = language_stats.get(lang, 0) + 1
    
    # 找出資料集中占比最大的語言
    dominant_language = max(language_stats.items(), key=lambda x: x[1])[0] if language_stats else "english"
    print(f"主要語言: {dominant_language} (共 {language_stats.get(dominant_language, 0)} 項)")
    return dominant_language

dominant_language = analyze_language_stats(chatbot_data)

@app.route('/')
def home():
    return "多語言聊天機器人 API 運行中"

def detect_language(text):
    """改進的語言檢測，更可靠且細化"""
    if not text or not isinstance(text, str) or text.strip() == "":
        return "unknown"
        
    import re
    
    # 清理和準備文本
    text = text.strip()
    
    # 計算不同語言字符的數量
    lang_chars = {
        'chinese': len(re.findall(r'[\u4e00-\u9fff]', text)),
        'japanese': len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text)),
        'korean': len(re.findall(r'[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f\ua960-\ua97f\ud7b0-\ud7ff]', text)),
        'russian': len(re.findall(r'[\u0400-\u04ff]', text))
    }
    
    # 打印調試信息
    print(f"語言檢測統計: {lang_chars}")
    
    # 找出出現最多的非英文字符
    max_lang = max(lang_chars.items(), key=lambda x: x[1])
    
    # 如果有明顯的非英文字符占比，確定語言
    if max_lang[1] > 0:
        return max_lang[0]
    
    # 檢查是否包含拉丁字母字符
    latin_chars = len(re.findall(r'[a-zA-Z]', text))
    
    if latin_chars > 0:
        # 包含拉丁字母，可能是英文或其他拉丁文字語言
        return 'english'
    
    # 如果以上都不符合，返回未知
    return "unknown"

def translate_text(text, source_lang='auto', target_lang='en'):
    """使用deep-translator進行翻譯，增強穩健性"""
    try:
        # 輸入驗證
        if not text or not isinstance(text, str) or text.strip() == "":
            print("翻譯跳過：空文本或非字符串")
            return text
        
        # 標準化語言代碼
        lang_map = {
            'chinese': 'zh-CN', 'english': 'en', 'japanese': 'ja', 
            'korean': 'ko', 'russian': 'ru',
            'zh': 'zh-CN', 'en': 'en', 'ja': 'ja', 'ko': 'ko', 'ru': 'ru',
            'unknown': 'en'  # 如果語言未知，假設為英文
        }
        
        source = lang_map.get(source_lang.lower(), 'auto')
        target = lang_map.get(target_lang.lower(), 'en')
        
        print(f"執行翻譯：從 {source} 到 {target}")
        print(f"原文本(前50字符)：{text[:50]}...")
        
        # 處理長文本 - 大多數API有字符長度限制
        MAX_LENGTH = 5000
        
        if len(text) > MAX_LENGTH:
            print(f"文本太長({len(text)}字符)，分段翻譯")
            
            # 分段處理長文本
            segments = []
            for i in range(0, len(text), MAX_LENGTH):
                segment = text[i:i+MAX_LENGTH]
                try:
                    translated_segment = GoogleTranslator(source=source, target=target).translate(segment)
                    segments.append(translated_segment)
                except Exception as e:
                    print(f"分段翻譯出錯: {e}")
                    segments.append(segment)  # 出錯時保留原文
            
            translated = ''.join(segments)
        else:
            # 標準翻譯
            translated = GoogleTranslator(source=source, target=target).translate(text)
        
        print(f"翻譯後文本(前50字符)：{translated[:50]}...")
        return translated
    except Exception as e:
        print(f"翻譯出錯: {e}")
        return text  # 出錯時返回原文

# 詳細的語意匹配函數 - 保持原有邏輯
def find_semantic_matches(query, language=None, top_n=3):
    # 這裡保留您原有的複雜邏輯 - 已經非常完善
    # ... [原有的 find_semantic_matches 函數內容] ...
    pass  # 實際代碼與原檔相同，此處省略

@app.route('/api/get_responses', methods=['POST'])
def get_responses():
    data = request.json
    user_prompt = data.get('prompt', '').strip()
    language = data.get('language', '')
    
    print(f"收到請求 - 提示: '{user_prompt}', 語言: '{language}'")
    
    # 檢測用戶語言
    if language == "auto" or not language:
        detected_lang = detect_language(user_prompt)
    else:
        detected_lang = language.lower()
    
    # 確保有效的語言標識
    detected_lang = detected_lang if detected_lang != 'unknown' else 'chinese'
    
    print(f"用戶語言: {detected_lang}")
    
    # 使用語意匹配
    matches = find_semantic_matches(user_prompt, None)
    
    if matches:
        best_match = matches[0]
        match_lang = best_match.get('language', '').lower() or 'english'
        
        # 移除內部評分字段
        if 'score' in best_match:
            del best_match['score']
        
        # 創建翻譯回應
        translated_response = best_match.copy()
        
        try:
            lang_map = {
                'chinese': 'zh-CN', 'english': 'en', 
                'japanese': 'ja', 'korean': 'ko', 'russian': 'ru'
            }
            
            source = lang_map.get(match_lang, 'en')
            target = lang_map.get(detected_lang, 'zh-CN')
            
            # 翻譯回應A和B
            for response_key in ['response_a', 'response_b']:
                if response_key in best_match and best_match[response_key]:
                    translated_response[response_key] = translate_text(
                        best_match[response_key], 
                        source, 
                        target
                    )
            
            translated_response['original_language'] = match_lang
            translated_response['language'] = detected_lang
            
            return jsonify([translated_response])
        
        except Exception as e:
            print(f"翻譯失敗: {e}")
            return jsonify([best_match])
    
    else:
        # 如果找不到匹配，隨機選擇一個回應
        try:
            random_response = random.choice(chatbot_data)
            
            # 翻譯隨機回應
            random_lang = random_response.get('language', '').lower() or 'english'
            
            translated_random = random_response.copy()
            
            lang_map = {
                'chinese': 'zh-CN', 'english': 'en', 
                'japanese': 'ja', 'korean': 'ko', 'russian': 'ru'
            }
            
            source = lang_map.get(random_lang, 'en')
            target = lang_map.get(detected_lang, 'zh-CN')
            
            # 翻譯回應A和B
            for response_key in ['response_a', 'response_b']:
                if response_key in random_response and random_response[response_key]:
                    translated_random[response_key] = translate_text(
                        random_response[response_key], 
                        source, 
                        target
                    )
            
            translated_random['original_language'] = random_lang
            translated_random['language'] = detected_lang
            
            return jsonify([translated_random])
        
        except Exception as e:
            print(f"隨機選擇回應失敗: {e}")
            return jsonify([])

@app.route('/api/languages', methods=['GET'])
def get_languages():
    # 獲取所有可用的語言
    languages = set()
    for item in chatbot_data:
        if 'language' in item and item['language']:
            languages.add(item['language'])
    
    # 確保"自動檢測"選項可用
    languages.add("auto")
    
    return jsonify(sorted(list(languages)))

@app.route('/api/search_diagnostic', methods=['GET'])
def search_diagnostic():
    query = request.args.get('query', 'hello').lower()
    limit = int(request.args.get('limit', 10))
    
    # 翻譯查詢
    detected_lang = detect_language(query)
    translated_query = None
    if detected_lang != 'english':
        translated_query = translate_text(query, detected_lang, 'english')
    
    # 基於語意匹配的診斷
    semantic_matches = find_semantic_matches(query, None, limit)
    
    return jsonify({
        'query': query,
        'detected_language': detected_lang,
        'translated_query': translated_query,
        'semantic_matches': [
            {
                'prompt': item['prompt'], 
                'language': item.get('language', ''), 
                'score': item.get('score', 0)
            } for item in semantic_matches
        ]
    })

if __name__ == '__main__':
    # 配置環境變量
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False') == 'True')
