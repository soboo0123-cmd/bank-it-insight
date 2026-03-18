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
    제공된 뉴스 데이터를 바탕으로, 전략적 통찰이 담긴 HTML 리포트를 작성하세요.
    
    [데이터]
    {news_context}
    
    [작성 가이드라인]
    1. <종합 브리핑>: 최상단에 배경색(#f8f9fa) <div>로 강조. 구체적인 은행명과 사업 명칭 언급. 
    2. <카테고리별 주요 기사 분류>: ① 경영전략 ② 신상품 ③ IT(기술/보안) ④ 기타. 
       - 기사 제목에 링크 삽입. 
       - [중요] 각 기사의 요약(description)은 데이터로 제공된 원문을 수정하지 말고 그대로(As-is) 표시할 것.
    3. 전문적인 어조(~로 분석됨, ~이 요망됨) 유지.
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
