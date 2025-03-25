from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
import json
import os
import glob
import re
import random
from deep_translator import GoogleTranslator

app = Flask(__name__)
CORS(app)

def load_json_data():
    """載入分割的 JSON 檔案"""
    base_dir = os.path.dirname(__file__)
    
    # 使用字母排序模式
    part_files = glob.glob(os.path.join(base_dir, "output_part[a-m].json"))
    
    # 依字母順序排序
    part_files.sort()
    
    # 合併 JSON 資料
    combined_data = []
    for file in part_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                combined_data.extend(data)
        except Exception as e:
            print(f"載入 {file} 時出錯: {e}")
    
    print(f"成功載入 {len(combined_data)} 筆對話資料")
    return combined_data

# 載入資料
chatbot_data = load_json_data()

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

def find_semantic_matches(query, language=None, top_n=3):
    """語意匹配查詢"""
    original_query = query.strip()
    query_lower = original_query.lower()
    
    # 偵測查詢語言
    if language == "auto" or not language:
        detected_lang = detect_language(query_lower)
    else:
        detected_lang = language.lower()
    
    # 語意關鍵詞類別
    semantic_categories = {
        'greeting': ['你好', '哈囉', 'hello', 'hi', '嗨', '早安', '午安', '晚安'],
        'mood_negative': ['難過', '傷心', '心情不好', '沮喪'],
        'mood_positive': ['開心', '快樂', '高興', '興奮'],
        'question': ['為什麼', '如何', '怎麼', '是否', '什麼'],
        'technology': ['電腦', '手機', '網路', 'AI', '科技']
    }
    
    # 找出查詢的語意類別
    query_categories = set()
    for category, keywords in semantic_categories.items():
        if any(keyword in query_lower for keyword in keywords):
            query_categories.add(category)
    
    # 評分和匹配邏輯
    scored_items = []
    for item in chatbot_data:
        # 語言過濾
        if language and language != "auto" and item.get('language', '').lower() != language.lower():
            continue
        
        item_prompt = item['prompt'].lower()
        score = 0
        
        # 直接匹配
        if query_lower == item_prompt:
            item_copy = item.copy()
            item_copy['score'] = 100
            return [item_copy]
        
        # 類別匹配
        item_categories = set()
        for category, keywords in semantic_categories.items():
            if any(keyword in item_prompt for keyword in keywords):
                item_categories.add(category)
        
        # 類別重疊得分
        common_categories = query_categories.intersection(item_categories)
        score += len(common_categories) * 30
        
        # 詞彙重疊得分
        item_words = set(item_prompt.split())
        query_words = set(query_lower.split())
        common_words = query_words.intersection(item_words)
        score += len(common_words) * 5
        
        # 子字串匹配
        if query_lower in item_prompt or item_prompt in query_lower:
            score += 20
        
        # 長度相似度
        length_ratio = min(len(query_lower), len(item_prompt)) / max(len(query_lower), len(item_prompt))
        score += length_ratio * 15
        
        # 最低分數門檻
        if score > 10:
            item_copy = item.copy()
            item_copy['score'] = score
            scored_items.append(item_copy)
    
    # 排序和返回
    scored_items.sort(key=lambda x: x.get('score', 0), reverse=True)
    return scored_items[:top_n]

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
        if 'language' in item and item['language']:
            languages.add(item['language'])
    languages.add("auto")
    return jsonify(sorted(list(languages)))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
