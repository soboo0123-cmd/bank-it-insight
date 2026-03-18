import os
import re
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta

# 1. 환경 변수 설정
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
MAIL_API_URL = os.environ.get('MAIL_API_URL')
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL')

# 모델 설정
MODEL_NAME = 'gemini-1.5-flash' # 안정성을 위해 flash 모델 사용 권장
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

# 언론사 화이트리스트 (기존 리스트 유지)
WHITELIST_PRESS_IDS = {
    "1032", "1005", "2312", "1020", "2385", "1021", "1081", "1022", "2364", "2268", "2844", "1023", "1025", "2041", "1028", "1469",
    "1001", "1421", "1003", "1422", "1056", "1214", "1055", "1052", "1437", "1019", "1448", "1449", "1374", "1004", "2151", "2656", "2802", "2108", "2155", "2233", "2099", "2916", "2741", "2251", "2221", "2807", "2713", "2423",
    "1009", "1015", "1011", "1018", "1277", "1014", "1016", "1030", "1029", "1092", "1008", "1648", "1366", "2003", "1138", "2046", "2096", "1293", "1123", "2090", "2274", "2366", "2810", "2141", "2499", "2119", "2138", "2282", "2898", "2254", "2792", "2213", "2137", "2214", "2704", "2017", "2506", "2016", "2394", "2374", "2480", "2001", "2528", "2405", "2492", "2609", "2716", "2133", "2015", "2298", "2038", "2524", "2118", "2839", "2296", "2804", "2256", "2036", "2676", "2048", "2752", "2404", "2300", "2781", "2585", "2325", "2201", "2829", "2206", "2140", "2785", "2243", "2177", "2110", "2795",
    "2291", "2525", "2002", "2025", "2515", "2383", "2421", "2735", "2538", "2318", "2745", "2541", "2743", "2742", "2662", "2477", "2805", "2490", "2402", "2847", "2167", "2375", "2451", "2794", "2708", "2915", "2698", "2556"
}

def get_naver_news(query):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    params = {"query": query, "display": 50, "sort": "date"}
    response = requests.get(url, headers=headers, params=params)
    return response.json().get('items', []) if response.status_code == 200 else []

def extract_press_id(url):
    match = re.search(r'article/(\d+)/', url)
    return match.group(1) if match else None

def collect_news_with_log():
    # 1. 쿼리 수정: '+' 연산자 제거 (검색 결과 극대화)
    queries = ["은행 AI", "은행 IT", "은행 신상품", "은행 디지털"]
    
    all_searched = [] # 검색된 모든 기사
    filtered_for_ai = [] # AI 분석에 넘길 기사
    execution_log = [] # 필터링 로그
    
    seen_urls = set()
    kst = timezone(timedelta(hours=9))
    limit_time = datetime.now(kst) - timedelta(days=1)

    for q in queries:
        items = get_naver_news(q)
        for item in items:
            link = item.get('link', '')
            title = item.get('title', '').replace('<b>', '').replace('</b>', '')
            
            if link in seen_urls: continue
            seen_urls.add(link)
            
            # 모든 검색 결과에 추가
            all_searched.append(item)
            
            # 필터링 로직 및 로그 기록
            is_naver_news = "n.news.naver.com" in link
            press_id = extract_press_id(link)
            is_whitelisted = press_id in WHITELIST_PRESS_IDS if press_id else False
            
            try:
                pub_date = datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S +0900').replace(tzinfo=kst)
                is_recent = pub_date >= limit_time
            except:
                is_recent = False

            # 필터링 통과 여부 결정
            if is_naver_news and is_whitelisted and is_recent:
                filtered_for_ai.append(item)
                execution_log.append(f"✅ [통과] {title} (ID: {press_id})")
            else:
                reason = []
                if not is_naver_news: reason.append("네이버뉴스 아님")
                if not is_whitelisted: reason.append(f"화이트리스트 미포함(ID:{press_id})")
                if not is_recent: reason.append("24시간 초과")
                execution_log.append(f"❌ [제외] {title} | 사유: {', '.join(reason)}")

    return all_searched, filtered_for_ai, execution_log

def get_gemini_insight(news_list):
    if not news_list:
        return "최근 24시간 이내의 조건을 만족하는 필터링된 뉴스가 없습니다."

    news_context = ""
    for i, item in enumerate(news_list):
        news_context += f"[{i+1}] 제목: {item['title']}\n요약: {item['description']}\n링크: {item['link']}\n\n"

    prompt = f"금융 IT 전략 분석가로서 다음 뉴스들의 핵심 트렌드를 HTML 리포트로 요약하세요. 구체적인 은행명 위주로 서술하세요.\n\n[데이터]\n{news_context}"
    response = model.generate_content(prompt)
    return response.text

def send_combined_mail(insight_html, filtered_news, all_news, logs):
    # 1. AI 분석 결과 섹션
    main_content = f"<div style='background:#f0f7ff; padding:15px; border-radius:10px;'><h2>🤖 AI 전략 인사이트</h2>{insight_html}</div>"
    
    # 2. 필터링 로그 섹션
    log_html = "<h3>📋 수집 및 필터링 로그 (디버깅용)</h3><ul style='font-size:12px; color:#666;'>"
    log_html += "".join([f"<li>{log}</li>" for log in logs])
    log_html += "</ul>"
    
    # 3. 전체 검색 결과 (AI 안거친 것 포함)
    total_list_html = "<h3>🔍 전체 검색 결과 (필터링 전)</h3><ul>"
    for item in all_news:
        total_list_html += f"<li><a href='{item['link']}'>{item['title']}</a></li>"
    total_list_html += "</ul>"

    full_html = f"""
    <div style="font-family: sans-serif; line-height: 1.6;">
        {main_content}
        <hr>
        {log_html}
        <hr>
        {total_list_html}
    </div>
    """

    payload = {
        "to": [RECIPIENT_EMAIL],
        "subject": f"[{datetime.now().date()}] 뉴스 수집 로직 점검 리포트",
        "html": full_html
    }
    requests.post(MAIL_API_URL, json=payload)

if __name__ == "__main__":
    all_news, ai_news, logs = collect_news_with_log()
    print(f"전체 검색: {len(all_news)}건 / AI 전달: {len(ai_news)}건")
    
    insights = get_gemini_insight(ai_news)
    insights = insights.replace('```html', '').replace('```', '').strip()
    
    send_combined_mail(insights, ai_news, all_news, logs)
