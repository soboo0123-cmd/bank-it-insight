import os
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta

# 1. 환경 변수 설정
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
MAIL_API_URL = os.environ.get('MAIL_API_URL')
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL')

# Gemini 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash') # 안정적인 flash 모델 권장

def get_naver_news(query):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {
        "query": query,
        "display": 50,
        "start": 1,
        "sort": "date"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get('items', [])
    return []

def collect_all_news():
    # 검색어 최적화 (불필요한 '+' 제거하여 검색 결과 확장)
    queries = ["은행 AI", "은행 IT", "은행 신상품", "은행 디지털"]
    all_items = []
    seen_urls = set()

    # 기준 시간 설정 (현재로부터 24시간 전)
    kst = timezone(timedelta(hours=9))
    limit_time = datetime.now(kst) - timedelta(days=1)
    
    # 핵심 은행 키워드 (직링크 기사 필터링용)
    bank_keywords = ["은행", "금융", "하나", "신한", "국민", "우리", "농협", "기업은행", "카카오뱅크", "토스"]

    for q in queries:
        news_items = get_naver_news(q)
        for item in news_items:
            link = item.get('link', '')
            title = item.get('title', '').replace('<b>', '').replace('</b>', '')
            
            if not link or link in seen_urls:
                continue
            
            # 1. 네이버 뉴스 서비스 기사인지 확인
            is_naver_news = "n.news.naver.com" in link
            
            # 2. 직링크 기사일 경우 제목에 은행 키워드가 포함되었는지 확인
            has_bank_keyword = any(kw in title for kw in bank_keywords)
            
            # 3. 시간 체크
            try:
                pub_date = datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S +0900').replace(tzinfo=kst)
                is_recent = pub_date >= limit_time
            except:
                is_recent = False

            # 필터링 로직: (네이버 뉴스이거나 핵심 키워드 포함 기사) AND 최신 기사
            if (is_naver_news or has_bank_keyword) and is_recent:
                all_items.append(item)
                seen_urls.add(link)
                
    return all_items

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
    제공된 뉴스 데이터를 바탕으로, 전체를 관통하는 하나의 전략적 맥락(Context)을 도출하여 유기적으로 연결된 HTML 리포트를 작성하세요.

    [데이터]
    {news_context}

    [작성 가이드라인 - 유기적 구성 중심]

    1. <종합 브리핑> (Executive Summary):
       - 최상단에 배치하고 배경색(#f8f9fa)이 적용된 <div> 태그로 강조하세요.
       - **[유기적 연결]** 하단 카테고리별로 추출될 '핵심 트렌드'들을 아우르는 거시적인 전략 흐름을 3~4문장으로 서술하세요.
       - 거시적 표현 대신 구체적인 은행명(농협, 신한 등)과 사업 명칭을 직접 언급하며, 파급력이 가장 큰 '전략적 이슈'를 최우선으로 배치하세요.
       - 문장 끝(마침표 바로 앞)에 해당 기사의 근거 링크를 <a href='URL'>🔗</a> 형태로 삽입하여 하단 상세 내용과 연결성을 확보하세요.

    2. <카테고리별 주요 기사 분류> (Detailed Analysis):
       - 아래 4가지 카테고리로 이슈를 분류하세요. 한 이슈는 가장 적합한 하나의 카테고리에만 할당합니다:
         ① 경영전략 ② 신상품 ③ IT/AI ④ 기타(규제/지표)
       - **[핵심 트렌드 동기화]** 각 카테고리 제목(<h3>) 옆에 해당 분야를 관통하는 [핵심 트렌드]를 한 줄로 표기하세요. 이 트렌드는 위 <종합 브리핑>에서 언급된 맥락과 유기적으로 완벽히 일치해야 합니다.
       - 이슈 추출(Clustering): 유사한 맥락의 기사는 하나의 이슈로 묶고, 단순 기사 개수가 아닌 전략적 가치가 높은 순으로 배치하세요.
       - 기사가 없는 카테고리는 "해당 분야 주요 이슈 없음"으로 표시하세요.
       - **[주의]** 인사 동정 기사는 '기타' 섹션을 포함해 전체 리포트에서 엄격히 제외하고, 기타 섹션은 규제 변화나 시장 지표 위주로 구성하세요.
       - 각 기사를 <ul>과 <li>를 사용해 나열하되, 기사 제목에 원문 링크를 삽입하세요.
       - **[중요]** 각 기사의 요약(description)은 데이터를 임의로 요약·가공하지 말고, 원본 텍스트(HTML 서식 포함)를 그대로(As-is) 노출하세요.

    3. 문체 및 형식:
       - "~로 분석됨", "~이 요망됨"과 같은 전문적인 보고서 어조를 유지하세요.
       - 통계 수치(기사 개수 등)는 언급하지 마세요.
    """
    
    response = model.generate_content(prompt)
    return response.text

def send_insight_mail(insight_html, news_list):
    """최종 HTML 조립 및 발송"""
    list_html = "<h3>참고 뉴스 원문 리스트</h3><ul>"
    for item in news_list:
        title = item['title'].replace('<b>', '').replace('</b>', '')
        list_html += f"<li><a href='{item['link']}'>{title}</a></li>"
    list_html += "</ul>"

    full_html = f"""
    <div style="font-family: 'Malgun Gothic', sans-serif; line-height: 1.6;">
        <div style="padding: 20px;">
            {insight_html}
        </div>
        <hr>
        {list_html}
    </div>
    """

    payload = {
        "to": [RECIPIENT_EMAIL],
        "subject": f"[{datetime.now(timezone(timedelta(hours=9))).date()}] 은행 IT & 신상품 데일리 인사이트",
        "html": full_html
    }

    try:
        response = requests.post(MAIL_API_URL, json=payload)
        if response.status_code in [200, 201]:
            print(f"메일 발송 성공! (수집된 뉴스: {len(news_list)}건)")
        else:
            print(f"실패: 코드 {response.status_code}")
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    news_items = collect_all_news()
    print(f"필터링 후 최종 수집: {len(news_items)}건")
    insights = get_gemini_insight(news_items)
    insights = insights.replace('```html', '').replace('```', '').strip()
    send_insight_mail(insights, news_items)
