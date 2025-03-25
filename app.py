from flask import Flask, request, jsonify
import json
from flask_cors import CORS
import os
import random
import re
import glob
import sqlite3
from deep_translator import GoogleTranslator

# 創建 Flask 應用實例
app = Flask(__name__)
CORS(app)  # 允許跨域請求

def init_database():
    """初始化資料庫並載入數據"""
    conn = sqlite3.connect('chatbot_data.db')
    cursor = conn.cursor()
    
    # 創建表格
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chatbot_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt TEXT,
        response_a TEXT,
        response_b TEXT,
        language TEXT,
        category TEXT
    )
    ''')
    
    # 檢查是否已有數據
    cursor.execute('SELECT COUNT(*) FROM chatbot_responses')
    if cursor.fetchone()[0] == 0:
        # 載入 JSON 檔案
        base_dir = os.path.dirname(__file__)
        pattern = os.path.join(base_dir, "output_part*.json")
        part_files = glob.glob(pattern)
        
        if not part_files:
            print("找不到任何分割的 JSON 檔案！")
            conn.close()
            return
        
        # 根據檔名中數字排序
        def extract_number(filename):
            m = re.search(r'output_part(\d+)\.json', os.path.basename(filename))
            return int(m.group(1)) if m else 0
        
        part_files.sort(key=extract_number)
        
        # 依序讀取每個檔案內容並插入資料庫
        inserted_count = 0
        for file in part_files:
            with open(file, "r", encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    cursor.execute('''
                    INSERT INTO chatbot_responses 
                    (prompt, response_a, response_b, language, category) 
                    VALUES (?, ?, ?, ?, ?)
                    ''', (
                        item.get('prompt', ''),
                        item.get('response_a', ''),
                        item.get('response_b', ''),
                        item.get('language', 'unknown'),
                        item.get('category', 'general')
                    ))
                    inserted_count += 1
        
        conn.commit()
        print(f"成功載入 {inserted_count} 筆對話資料到資料庫")
    
    conn.close()

# 初始化資料庫
init_database()

def detect_language(text):
    """改進的語言檢測，更可靠且細化"""
    if not text or not isinstance(text, str) or text.strip() == "":
        return "unknown"
    
    # 清理和準備文本
    text = text.strip()
    
    # 計算不同語言字符的數量
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    japanese_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text))
    korean_chars = len(re.findall(r'[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f\ua960-\ua97f\ud7b0-\ud7ff]', text))
    russian_chars = len(re.findall(r'[\u0400-\u04ff]', text))
    
    # 統計出現最多的字符類型
    lang_counts = {
        'chinese': chinese_chars,
        'japanese': japanese_chars,
        'korean': korean_chars,
        'russian': russian_chars
    }
    
    # 如果有明顯的非英文字符占比，確定語言
    total_non_english = sum(lang_counts.values())
    if total_non_english > 0:
        max_lang = max(lang_counts.items(), key=lambda x: x[1])
        if max_lang[1] > 0:
            return max_lang[0]
    
    # 檢查是否包含拉丁字母字符
    latin_chars = len(re.findall(r'[a-zA-Z]', text))
    if latin_chars > 0:
        return 'english'
    
    return "unknown"

def translate_text(text, source_lang='auto', target_lang='en'):
    """使用 deep-translator 進行翻譯，增強穩健性"""
    try:
        if not text or not isinstance(text, str) or text.strip() == "":
            return text
        
        # 語言映射
        lang_map = {
            'chinese': 'zh-CN', 'english': 'en', 
            'japanese': 'ja', 'korean': 'ko', 
            'russian': 'ru', 'zh': 'zh-CN', 
            'en': 'en', 'ja': 'ja', 
            'ko': 'ko', 'ru': 'ru',
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
    """使用資料庫進行語意匹配查詢"""
    conn = sqlite3.connect('chatbot_data.db')
    cursor = conn.cursor()
    
    # 偵測查詢語言
    original_query = query.strip()
    query_lower = original_query.lower()
    
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
    
    # 準備查詢
    base_query = """
    SELECT prompt, response_a, response_b, language, 
    (
        CASE WHEN ? LIKE '%' || prompt || '%' THEN 50 ELSE 0 END +
        (SELECT COUNT(*) FROM (
            SELECT value FROM (
                VALUES ('greeting'), ('mood_negative'), ('mood_positive'), 
                       ('question'), ('technology')
            ) AS categories(value)
            WHERE value IN (
                SELECT category FROM chatbot_responses 
                WHERE prompt = base.prompt
            )
        )) * 20
    ) AS score
    FROM chatbot_responses AS base
    WHERE language = ? OR language = 'unknown'
    ORDER BY score DESC
    LIMIT ?
    """
    
    try:
        # 執行查詢
        cursor.execute(base_query, (query_lower, detected_lang, top_n))
        results = cursor.fetchall()
        
        # 格式化結果
        matches = []
        for row in results:
            match = {
                'prompt': row[0],
                'response_a': row[1],
                'response_b': row[2],
                'language': row[3],
                'score': row[4]
            }
            matches.append(match)
        
        return matches
    
    except Exception as e:
        print(f"查詢出錯: {e}")
        return []
    finally:
        conn.close()

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
                'japanese': 'ja', 'korean': 'ko', 
                'russian': 'ru'
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
    return get_random_response(detected_lang)

def get_random_response(detected_lang):
    """取得隨機回應並翻譯"""
    conn = sqlite3.connect('chatbot_data.db')
    cursor = conn.cursor()
    
    try:
        # 隨機選取一筆回應
        cursor.execute("""
            SELECT prompt, response_a, response_b, language 
            FROM chatbot_responses 
            ORDER BY RANDOM() 
            LIMIT 1
        """)
        row = cursor.fetchone()
        
        if not row:
            return jsonify([])
        
        # 建立回應字典
        random_response = {
            'prompt': row[0],
            'response_a': row[1],
            'response_b': row[2],
            'language': row[3]
        }
        
        # 語言映射
        lang_map = {
            'chinese': 'zh-CN', 'english': 'en', 
            'japanese': 'ja', 'korean': 'ko', 
            'russian': 'ru'
        }
        
        source = lang_map.get(random_response['language'], 'en')
        target = lang_map.get(detected_lang, 'zh-CN')
        
        # 翻譯回應
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
        
        random_response['original_language'] = random_response['language']
        random_response['language'] = detected_lang
        
        return jsonify([random_response])
    
    except Exception as e:
        print(f"隨機回應選取失敗: {e}")
        return jsonify([])
    finally:
        conn.close()

@app.route('/api/languages', methods=['GET'])
def get_languages():
    """取得可用語言列表"""
    conn = sqlite3.connect('chatbot_data.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT DISTINCT language FROM chatbot_responses")
        languages = [row[0] for row in cursor.fetchall() if row[0]]
        languages.append("auto")
        return jsonify(sorted(set(languages)))
    
    except Exception as e:
        print(f"取得語言列表失敗: {e}")
        return jsonify(["auto", "chinese", "english", "japanese", "korean"])
    finally:
        conn.close()

@app.route('/api/search_diagnostic', methods=['GET'])
def search_diagnostic():
    """搜尋診斷接口"""
    query = request.args.get('query', 'hello').lower()
    limit = int(request.args.get('limit', 10))
    
    detected_lang = detect_language(query)
    translated_query = None
    if detected_lang != 'english':
        translated_query = translate_text(query, detected_lang, 'english')
    
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
    app.run(debug=True, port=5000)
