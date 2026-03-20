import os
import requests
import json
from datetime import datetime, timezone, timedelta
import html
import re
from collections import defaultdict
from google import genai

# 1. 환경 변수 설정
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
MAIL_API_URL = os.environ.get('MAIL_API_URL')
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL')

# Gemini 설정
client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 2. article.py 로직 이식 (상수 및 유틸리티 함수)
# ==========================================
ALLOWED_DOMAINS = [
    "khan.co.kr", "kmib.co.kr", "naeil.com", "donga.com", "m-i.kr", "munhwa.com", "seoul.co.kr",
    "segye.com", "shinailbo.co.kr", "asiatoday.co.kr", "chosun.com", "joongang.co.kr",
    "hani.co.kr", "hankookilbo.com", "yna.co.kr", "news1.kr", "newsis.com", "kbs.co.kr",
    "imbc.com", "sbs.co.kr", "ytn.co.kr", "jtbc.co.kr", "mbn.co.kr", "mk.co.kr", "hankyung.com", 
    "sedaily.com", "edaily.co.kr", "asiae.co.kr", "fnnews.com", "heraldcorp.com",
    "etnews.com", "dt.co.kr", "zdnet.co.kr", "mt.co.kr", "bizwatch.co.kr", "etoday.co.kr",
    "ddaily.co.kr", "dailian.co.kr", "joseilbo.com", "inews24.com", "bloter.net", "fntimes.com"
]

# 1회 출연만으로 통과 가능한 핵심 키워드
CORE_KEYWORDS = ["은행", "카카오", "토스", "뱅크", "뱅킹", "금융"]

def clean_text_to_list(text):
    text = html.unescape(text.replace('<b>', '').replace('</b>', ''))
    text = re.sub(r'[^\w\s-]', ' ', text)
    
    # 유사도 분석 시 제외할 일반 단어 (사건의 본질만 남김)
    black_list = {
        'AI', 'IT', '디지털', '신상품', '금융', '은행', '기업', '기관', '서비스', '업무',
        '지원', '확대', '강화', '구축', '출범', '추진', '본격', '협약', '체결', '방문', '실시',
        '개최', '선정', '도입', '진행', '마련', '대응'
    }
    stop_words = {'은', '는', '이', '가', '을', '를', '의', '와', '과', '에', '도', '등', '로', '으로'}
    
    words = text.split()
    processed_keywords = []
    for i, w in enumerate(words):
        if w in stop_words or w in black_list or len(w) < 2: continue
        weight = 1.2 if i == 0 else 1.0
        if len(w) >= 4 or re.search(r'[a-zA-Z0-9]', w): weight *= 1.5
        processed_keywords.append({'word': w, 'weight': weight})
    return processed_keywords

def get_hybrid_similarity(list1, list2):
    if not list1 or not list2: return 0.0
    match_score = 0.0
    total_weight1 = sum(item['weight'] for item in list1)
    total_weight2 = sum(item['weight'] for item in list2)
    min_total_weight = min(total_weight1, total_weight2)

    for item1 in list1:
        for item2 in list2:
            if item1['word'][:2] == item2['word'][:2]:
                match_score += max(item1['weight'], item2['weight'])
                break 
    return match_score / min_total_weight if min_total_weight > 0 else 0

# ==========================================
# 3. 메인 로직 (뉴스 수집 및 필터링)
# ==========================================
def collect_all_news():
    queries = ["은행 +AI", "은행 +IT", "은행 +신상품", "은행 +디지털"]
    kst = timezone(timedelta(hours=9))
    limit_time = datetime.now(kst) - timedelta(days=1)
    
    url_map = {}
    url_to_queries = defaultdict(set)

    print(f"--- 1단계: 날짜/매체 필터링 수집 시작 ---")
    for q in queries:
        items = []
        for start in range(1, 301, 100): # 300개 수집
            res = requests.get(
                "https://openapi.naver.com/v1/search/news.json",
                headers={"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET},
                params={"query": q, "display": 100, "start": start, "sort": "date"}
            ).json().get('items', [])
            if not res: break
            items.extend(res)

        for item in items:
            main_url = item.get('originallink') or item.get('link')
            naver_url = item.get('link', '')

            # [필터 1] 날짜 및 매체
            try:
                pub_date = datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S +0900').replace(tzinfo=kst)
                if pub_date < limit_time: continue
            except: continue

            is_allowed = any(dom in main_url for dom in ALLOWED_DOMAINS) or ("n.news.naver.com" in naver_url)
            if not is_allowed: continue

            if main_url not in url_map:
                url_map[main_url] = item
            url_to_queries[main_url].add(q)
    
    print(f"[DEBUG] 1차 필터링(날짜/매체) 후 기사 수: {len(url_map)}건")

    # [필터 2] 교집합(2회 이상) OR 핵심 키워드 포함 기사 선별
    candidate_items = []
    for url, q_set in url_to_queries.items():
        item = url_map[url]
        clean_title = html.unescape(item['title'].replace('<b>', '').replace('</b>', ''))
        
        is_intersected = len(q_set) >= 2
        has_core_word = any(word in clean_title for word in CORE_KEYWORDS)

        if is_intersected or has_core_word:
            item['match_count'] = len(q_set)
            candidate_items.append(item)
    
    print(f"[DEBUG] 2차 필터링(교집합/핵심어) 후 기사 수: {len(candidate_items)}건")

    # [필터 3] 제목 유사도 분석 (요약문 긴 것 선택)
    unique_news = []
    threshold = 0.45
    
    candidate_items.sort(key=lambda x: x['match_count'], reverse=True)

    for current in candidate_items:
        current_keywords = clean_text_to_list(current['title'])
        is_duplicate = False
        
        for i, existing in enumerate(unique_news):
            existing_keywords = clean_text_to_list(existing['title'])
            similarity = get_hybrid_similarity(current_keywords, existing_keywords)
            
            if similarity >= threshold:
                is_duplicate = True
                if len(current.get('description', '')) > len(existing.get('description', '')):
                    unique_news[i] = current
                break
        
        if not is_duplicate:
            unique_news.append(current)

    return unique_news

def get_gemini_insight(news_list):
    if not news_list:
        return "<div style='padding:20px; background:#f0f7ff; border-radius:10px;'><h2>🤖 AI 전략 인사이트</h2>최근 24시간 이내의 조건을 만족하는 필터링된 뉴스가 없습니다.</div>"


    news_context = ""
    for i, item in enumerate(news_list):
        title = item['title'].replace('<b>', '').replace('</b>', '')
        desc = item['description'].replace('<b>', '').replace('</b>', '')
        news_context += f"[{i+1}] 제목: {title}\n요약: {desc}\n링크: {item['link']}\n\n"

    prompt = f"""
    당신은 금융기관 경영진에게 보고하는 '금융 IT 전략 분석가'입니다. 
    제공된 뉴스 데이터를 바탕으로, 전략적 통찰이 담긴 HTML 리포트를 작성하세요.
    
    [데이터]
    {news_context}
    
    [작성 가이드라인 - 아래 순서를 반드시 엄수할 것]
    
    1. <종합 브리핑>:
       - 최상단에 배치하고, 배경색이 연한 회색(#f8f9fa)인 <div> 태그로 강조하세요. '<div style='padding:10px; background:#f8f9fa; border-radius:10px;'>'
       - **[핵심 지침]** 거시적인 표현(예: 금융권은~, 가속화하고 있다~)을 지양하고, **구체적인 은행명과 사업 명칭을 직접 언급**하며 서술하세요.
       - 오늘 뉴스 중 가장 중요한 **경쟁사들의 실질적인 액션(신상품 출시, 조직 개편, 파트너십 등)**을 중심으로 3~4문장의 전략적 통찰을 제공하세요.
       - (예: "단순히 기술 협력을 합니다" (X) -> "하나금융이 SC그룹과 디지털 자산 동맹을 맺고 글로벌 시장 선점에 나섰습니다" (O))
      - **[링크 배치]** 각 문장의 근거가 되는 원문 링크를 문장 끝 마침표 바로 앞에 <a href='URL'>🔗</a> 형태로 삽입하세요.

    2. <카테고리별 주요 기사 분류>:
       - 아래 4가지 카테고리로 기사를 분류하여 배치하세요:
         ① 경영전략 ② 신상품 ③ IT(기술/보안) ④ 기타
       - **[레이아웃 변경]** 카테고리 제목(<h3>) 바로 옆에 해당 분야의 [핵심 트렌드]를 한 줄로 나란히 배치하세요. '<div style='background:#f8f9fa;'>'
       - 기사가 없는 카테고리는 "해당 분야 주요 기사 없음"이라고 표시하세요.
       - 카테고리별로 각 기사를 관통하는 핵심 트렌드를 한 줄로 요약하여 제시하세요.
       - **[중요]** 각 기사의 [기사내용desc]는 **데이터로 제공된 원문을 임의로 요약하거나 수정하지 말고 텍스트 그대로(As-is) 전체를 표시**하세요. 네이버에서 전달받은 <br> 태그 등 HTML 서식도 그대로 유지해야 합니다.
       - 각 기사는 <ul>과 <li>를 사용하며, 기사 제목에 원문 링크를 삽입하세요.
    
    3. 전문적인 어조(예: ~로 분석됨, ~이 요망됨)를 유지하고, <h3> 태그로 섹션을 명확히 구분하여 가독성을 극대화하세요.
    """

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )

    result = response.text

    # 🔍 DEBUG: Gemini 응답 길이
    print(f"[DEBUG] Gemini 응답 길이: {len(result)}")

    return result


def send_insight_mail(insight_html):
    full_html = f"""
    <div style="font-family: 'Malgun Gothic', sans-serif; line-height: 1.6;">
        <div style="padding: 20px;">
            {insight_html}
        </div>
    </div>
    """

    # 🔍 DEBUG: HTML 길이
    print(f"[DEBUG] HTML 길이: {len(full_html)}")

    payload = {
        "to": [email.strip() for email in RECIPIENT_EMAIL.split(",")],
        "subject": f"[{datetime.now(timezone(timedelta(hours=9))).date()}] 은행 IT & 신상품 데일리 인사이트",
        "html": full_html
    }

    # 🔍 DEBUG: Payload 크기
    payload_size = len(json.dumps(payload))
    print(f"[DEBUG] Payload JSON 크기: {payload_size}")

    try:
        response = requests.post(MAIL_API_URL, json=payload)

        if response.status_code in [200, 201]:
            print(f"메일 발송 성공!")
        else:
            print(f"실패: 코드 {response.status_code}")
            print(f"[DEBUG] 응답 내용: {response.text}")

    except Exception as e:
        print(f"오류 발생: {e}")


if __name__ == "__main__":
    news_items = collect_all_news()
    print(f"[DEBUG] 최종 필터링 후 뉴스 개수: {len(news_items)}건")

    insights = get_gemini_insight(news_items)

    insights = insights.replace('```html', '').replace('```', '').strip()

    send_insight_mail(insights)
