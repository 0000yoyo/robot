from flask import Flask, request, jsonify
import json
from flask_cors import CORS
import os
import random
import re
import glob
from deep_translator import GoogleTranslator

# 創建 Flask 應用實例
app = Flask(__name__)
CORS(app)  # 允許跨域請求

def load_data():
    """
    從與本程式同層的分割檔 (output_part*.json) 合併成完整 JSON 資料。
    假設分割檔名格式為：output_part1.json、output_part2.json...。
    """
    try:
        base_dir = os.path.dirname(__file__)
        pattern = os.path.join(base_dir, "output_part*.json")
        part_files = glob.glob(pattern)

        if not part_files:
            print("找不到任何分割的 JSON 檔案！")
            return []

        # 根據檔名中數字排序 (如 output_part1.json, output_part2.json, ...)
        def extract_number(filename):
            m = re.search(r'output_part(\d+)\.json', os.path.basename(filename))
            return int(m.group(1)) if m else 0

        part_files.sort(key=extract_number)

        # 依序讀取每個檔案內容並串接
        content_bytes = b""
        for file in part_files:
            with open(file, "rb") as f:
                content_bytes += f.read()

        # 轉成字串後用 json.loads() 解析
        content_str = content_bytes.decode("utf-8")
        data = json.loads(content_str)

        print(f"成功載入 {len(data)} 筆對話資料（合併自 {len(part_files)} 個分割檔案）")
        return data

    except Exception as e:
        print(f"載入分割檔案時出錯: {e}")
        return []

# 全局變數存放資料
chatbot_data = load_data()
print(f"已載入 {len(chatbot_data)} 筆對話資料")

# 統計各語言的數量並找出主要語言
language_stats = {}
for item in chatbot_data:
    lang = item.get('language', 'unknown').lower()
    language_stats[lang] = language_stats.get(lang, 0) + 1

# 找出資料集中占比最大的語言
dominant_language = max(language_stats.items(), key=lambda x: x[1])[0] if language_stats else "english"
print(f"主要語言: {dominant_language} (共 {language_stats.get(dominant_language, 0)} 項)")

@app.route('/')
def home():
    return "多語言聊天機器人 API 運行中"

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
    
    # 打印調試信息
    print(f"語言檢測統計: {lang_counts}")
    
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
            print("翻譯跳過：空文本或非字符串")
            return text
        
        source = source_lang.lower() if source_lang else 'auto'
        target = target_lang.lower() if target_lang else 'en'
        
        lang_map = {
            'chinese': 'zh-CN',
            'english': 'en',
            'japanese': 'ja',
            'korean': 'ko',
            'russian': 'ru',
            'zh': 'zh-CN',
            'en': 'en',
            'ja': 'ja',
            'ko': 'ko',
            'ru': 'ru',
            'unknown': 'en'
        }
        
        if source in lang_map:
            source = lang_map[source]
        if target in lang_map:
            target = lang_map[target]
        
        print(f"執行翻譯：從 {source} 到 {target}")
        print(f"原文本(前50字符)：{text[:50]}...")
        
        MAX_LENGTH = 5000
        if len(text) > MAX_LENGTH:
            print(f"文本太長({len(text)}字符)，分段翻譯")
            segments = []
            for i in range(0, len(text), MAX_LENGTH):
                segment = text[i:i+MAX_LENGTH]
                try:
                    translated_segment = GoogleTranslator(source=source, target=target).translate(segment)
                    segments.append(translated_segment)
                except Exception as e:
                    print(f"分段翻譯出錯: {e}")
                    segments.append(segment)
            translated = ''.join(segments)
        else:
            translated = GoogleTranslator(source=source, target=target).translate(text)
        
        print(f"翻譯後文本(前50字符)：{translated[:50]}...")
        return translated
    except Exception as e:
        print(f"翻譯出錯: {e}")
        print(f"返回原文本")
        return text

def find_semantic_matches(query, language=None, top_n=3):
    """使用增強的語意分析來尋找匹配項"""
    original_query = query.strip()
    query_lower = original_query.lower()
    
    if language == "auto" or not language:
        detected_lang = detect_language(query_lower)
    else:
        detected_lang = language.lower()
    
    print(f"檢測到的語言: {detected_lang}")
    
    translated_query = None
    if detected_lang != 'english' and detected_lang != dominant_language:
        translated_query = translate_text(original_query, detected_lang, 'english')
        print(f"查詢已翻譯為英文: '{translated_query}'")
    
    semantic_categories = {
        'greeting': ['你好', '哈囉', 'hello', 'hi', '嗨', '早安', '午安', '晚安', '問候', '見到', '嘿', '安'],
        'mood_negative': ['心情不好', '難過', '傷心', '哭', '痛苦', '悲傷', '悲痛', '沮喪', '憂鬱', '絕望', '生氣', '憤怒', '煩惱', '不開心', '不爽', '糟糕'],
        'mood_positive': ['開心', '快樂', '高興', '興奮', '愉快', '幸福', '喜悅', '興高采烈', '好心情', '好心境', '舒暢'],
        'question': ['為什麼', '如何', '怎麼', '是否', '能不能', '可以嗎', '嗎', '呢', '?', '？', '什麼', '誰', '哪裡', '何時'],
        'weather': ['天氣', '下雨', '晴天', '氣溫', '冷', '熱', '雨', '雪', '風', '陰天', '颱風'],
        'time': ['今天', '明天', '昨天', '時間', '日期', '現在', '未來', '過去', '早上', '中午', '晚上', '凌晨'],
        'help': ['幫助', '協助', '解決', '需要', '請求', '求助', '幫忙', '支援', '援助'],
        'thanks': ['謝謝', '感謝', '感激', '謝意', '多謝', '感恩'],
        'technology': ['電腦', '手機', '網路', '程式', '軟體', '硬體', '科技', '技術', '系統', '人工智能', 'AI', '機器學習'],
        'personal': ['我', '我的', '我想', '我要', '自己', '個人', '我覺得', '我認為', '我希望'],
        'travel': ['旅遊', '旅行', '遊玩', '觀光', '景點', '日本', '東京', '大阪', '京都', '飯店', '機票', 'travel', 'japan', 'tokyo']
    }
    
    query_categories = set()
    translated_categories = set()
    
    for category, keywords in semantic_categories.items():
        if any(keyword in query_lower for keyword in keywords):
            query_categories.add(category)
    
    if translated_query:
        translated_lower = translated_query.lower()
        for category, keywords in semantic_categories.items():
            if any(keyword in translated_lower for keyword in keywords):
                translated_categories.add(category)
    
    all_categories = query_categories.union(translated_categories)
    print(f"查詢語意類別: {all_categories}")
    
    scored_items = []
    query_words = set(query_lower.split())
    translated_words = set(translated_query.lower().split()) if translated_query else set()
    
    for item in chatbot_data:
        if language and language != "auto" and item.get('language', '').lower() != language.lower():
            continue
        
        item_prompt = item['prompt'].lower()
        
        # 1. 直接匹配 (最高優先級)
        if query_lower == item_prompt or (translated_query and translated_query.lower() == item_prompt):
            item_copy = item.copy()
            item_copy['score'] = 100
            return [item_copy]
        
        score = 0
        item_categories = set()
        for category, keywords in semantic_categories.items():
            if any(keyword in item_prompt for keyword in keywords):
                item_categories.add(category)
        
        common_categories = all_categories.intersection(item_categories)
        category_score = len(common_categories) * 30
        score += category_score
        
        if ('mood_negative' in all_categories and 'mood_negative' in item_categories) or \
           ('mood_positive' in all_categories and 'mood_positive' in item_categories):
            score += 20
        
        if 'travel' in all_categories and 'travel' in item_categories:
            travel_terms = ['日本', 'japan', 'tokyo', '東京', 'osaka', '大阪', 'kyoto', '京都']
            query_travel = [term for term in travel_terms if term in query_lower or (translated_query and term in translated_query.lower())]
            item_travel = [term for term in travel_terms if term in item_prompt]
            if any(term in query_travel and term in item_travel for term in travel_terms):
                score += 25
        
        item_words = set(item_prompt.split())
        common_words = query_words.intersection(item_words)
        
        if translated_query:
            common_translated = translated_words.intersection(item_words)
            if len(common_translated) > len(common_words):
                common_words = common_translated
        
        word_overlap_score = len(common_words) * 5
        score += word_overlap_score
        
        substring_score = 0
        if query_lower in item_prompt or (translated_query and translated_query.lower() in item_prompt):
            substring_score = 20
        elif item_prompt in query_lower or (translated_query and item_prompt in translated_query.lower()):
            substring_score = 15
        score += substring_score
        
        length_ratio = min(len(query_lower), len(item_prompt)) / max(len(query_lower), len(item_prompt))
        length_score = length_ratio * 15
        score += length_score
        
        min_score_threshold = 10
        if score >= min_score_threshold:
            item_copy = item.copy()
            item_copy['score'] = score
            scored_items.append(item_copy)
    
    scored_items.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    for i, item in enumerate(scored_items[:min(top_n, len(scored_items))]):
        print(f"匹配 {i+1}: '{item['prompt']}' (相似度分數: {item.get('score', 0)})")
    
    return scored_items[:top_n]

@app.route('/api/get_responses', methods=['POST'])
def get_responses():
    data = request.json
    user_prompt = data.get('prompt', '').strip()
    language = data.get('language', '')
    
    print(f"收到請求 - 提示: '{user_prompt}', 語言: '{language}'")
    
    if language == "auto" or not language:
        detected_lang = detect_language(user_prompt)
    else:
        detected_lang = language.lower()
    
    if not detected_lang or detected_lang == 'unknown':
        detected_lang = 'chinese'
    
    print(f"用戶語言: {detected_lang}")
    
    matches = find_semantic_matches(user_prompt, None)
    
    if matches:
        best_match = matches[0]
        match_lang = best_match.get('language', '').lower()
        
        if 'score' in best_match:
            del best_match['score']
        
        if not match_lang:
            match_lang = 'english'
        
        print(f"匹配項語言: {match_lang}, 用戶語言: {detected_lang}")
        
        translated_response = best_match.copy()
        
        try:
            lang_map = {
                'chinese': 'zh-CN',
                'english': 'en',
                'japanese': 'ja',
                'korean': 'ko',
                'russian': 'ru',
                'zh': 'zh-CN',
                'en': 'en',
                'ja': 'ja',
                'ko': 'ko',
                'ru': 'ru'
            }
            
            source = lang_map.get(match_lang, 'en')
            target = lang_map.get(detected_lang, 'zh-CN')
            
            MAX_LENGTH = 5000
            
            if 'response_a' in best_match and best_match['response_a']:
                original_text = best_match['response_a']
                print(f"翻譯模型A回應從 {match_lang} 到 {detected_lang}")
                print(f"原始回應A: {original_text[:50]}...")
                
                if len(original_text) > MAX_LENGTH:
                    segments = []
                    for i in range(0, len(original_text), MAX_LENGTH):
                        segment = original_text[i:i+MAX_LENGTH]
                        try:
                            translated_segment = GoogleTranslator(source=source, target=target).translate(segment)
                            segments.append(translated_segment)
                        except Exception as e:
                            print(f"分段翻譯出錯: {e}")
                            segments.append(segment)
                    translated_response['response_a'] = ''.join(segments)
                else:
                    translated_response['response_a'] = GoogleTranslator(source=source, target=target).translate(original_text)
                print(f"翻譯後回應A: {translated_response['response_a'][:50]}...")
            
            if 'response_b' in best_match and best_match['response_b']:
                original_text = best_match['response_b']
                print(f"翻譯模型B回應從 {match_lang} 到 {detected_lang}")
                print(f"原始回應B: {original_text[:50]}...")
                
                if len(original_text) > MAX_LENGTH:
                    segments = []
                    for i in range(0, len(original_text), MAX_LENGTH):
                        segment = original_text[i:i+MAX_LENGTH]
                        try:
                            translated_segment = GoogleTranslator(source=source, target=target).translate(segment)
                            segments.append(translated_segment)
                        except Exception as e:
                            print(f"分段翻譯出錯: {e}")
                            segments.append(segment)
                    translated_response['response_b'] = ''.join(segments)
                else:
                    translated_response['response_b'] = GoogleTranslator(source=source, target=target).translate(original_text)
                print(f"翻譯後回應B: {translated_response['response_b'][:50]}...")
            
        except Exception as e:
            print(f"翻譯失敗: {e}")
            translated_response = best_match
        
        translated_response['original_language'] = match_lang
        translated_response['language'] = detected_lang
        
        return jsonify([translated_response])
    else:
        try:
            random_response = random.choice(chatbot_data)
            random_lang = random_response.get('language', '').lower()
            if not random_lang:
                random_lang = 'english'
            
            translated_random = random_response.copy()
            
            try:
                lang_map = {
                    'chinese': 'zh-CN',
                    'english': 'en',
                    'japanese': 'ja',
                    'korean': 'ko',
                    'russian': 'ru',
                    'zh': 'zh-CN',
                    'en': 'en',
                    'ja': 'ja',
                    'ko': 'ko',
                    'ru': 'ru'
                }
                
                source = lang_map.get(random_lang, 'en')
                target = lang_map.get(detected_lang, 'zh-CN')
                
                if 'response_a' in random_response:
                    translated_random['response_a'] = GoogleTranslator(source=source, target=target).translate(random_response['response_a'])
                
                if 'response_b' in random_response:
                    translated_random['response_b'] = GoogleTranslator(source=source, target=target).translate(random_response['response_b'])
                
                translated_random['original_language'] = random_lang
                translated_random['language'] = detected_lang
                
                return jsonify([translated_random])
            except Exception as e:
                print(f"隨機回應翻譯失敗: {e}")
                return jsonify([random_response])
                
        except Exception as e:
            print(f"隨機選擇回應失敗: {e}")
            return jsonify([])

@app.route('/api/languages', methods=['GET'])
def get_languages():
    languages = set()
    for item in chatbot_data:
        if 'language' in item and item['language']:
            languages.add(item['language'])
    languages.add("auto")
    return jsonify(sorted(list(languages)))

@app.route('/api/search_diagnostic', methods=['GET'])
def search_diagnostic():
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
