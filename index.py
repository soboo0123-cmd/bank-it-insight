import os
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta

# 1. 환경 변수 설정
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
MAIL_API_URL = os.environ.get('MAIL_API_URL')
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL') # 추가된 부분

# Gemini 설정 (최신 모델명 gemini-1.5-flash 권장)
genai.configure(api_key=GEMINI_API_KEY)
# 'gemini-pro' 대신 'gemini-1.5-flash'를 사용하면 속도도 빠르고 에러가 없습니다.
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

def get_naver_news(query):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {
        "query": query,
        "display": 30,
        "start": 1,
        "sort": "sim"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get('items', [])
    return []

def collect_all_news():
    queries = ["은행 +AI", "은행 +디지털", "은행 +신상품", "은행 +IT"]
    all_items = []
    seen_urls = set()

    for q in queries:
        news_items = get_naver_news(q)
        for item in news_items:
            if item['link'] not in seen_urls:
                all_items.append(item)
                seen_urls.add(item['link'])
    return all_items

def get_gemini_insight(news_list):
    if not news_list:
        return "분석할 뉴스 데이터가 없습니다."

    news_context = ""
    for i, item in enumerate(news_list):
        title = item['title']
        desc = item['description']
        news_context += f"[{i+1}] 제목: {title}\n요약: {desc}\n링크: {item['link']}\n\n"

    prompt = f"""
    당신은 금융기관 경영진에게 보고하는 '금융 IT 전략 분석가'입니다. 
    제공된 뉴스 데이터를 바탕으로, 전략적 통찰이 담긴 HTML 리포트를 작성하세요.
    
    [데이터]
    {news_context}
    
    [작성 가이드라인 - 아래 순서를 반드시 엄수할 것]
    
    1. <종합 브리핑 (Executive Summary)>:
       - 최상단에 배치하세요. 오늘 수집된 뉴스들을 종합하여 현재의 거시적 흐름과 '전략적 시사점'을 3~4문장으로 서술하세요.
       - 배경색이 연한 회색(#f8f9fa)이고 테두리가 있는 <div> 태그 안에 넣어 경영진이 가장 먼저 주목하게 하세요.
       - 근거가 되는 원문 링크를 문장 끝에 <a href='URL'>🔗</a> 형태로 삽입하세요.
    
    2. <카테고리별 주요 기사 분류>:
       - 아래 4가지 카테고리로 기사를 분류하여 배치하세요:
         ① 경영전략 ② 신상품 ③ IT(기술/보안) ④ 기타
       - 기사가 없는 카테고리는 "해당 분야 주요 기사 없음"이라고 표시하세요.
       - 카테고리별로 각 기사를 관통하는 핵심 트렌드를 제시하세요 
       - 각 기사는 <ul>과 <li>를 사용하며, [기사 제목]과 [기사내용desc]을 함께 표시하세요.
       - 기사 제목에 원문 링크를 삽입하세요.
    
    4. 전문적인 어조(예: ~로 분석됨, ~이 요망됨)를 유지하고, <h3> 태그로 섹션을 명확히 구분하여 가독성을 극대화하세요.
       - 특히 네이버에서 전달받은 <br>태그는 기사 추출의 근거가 되므로 꼭 유지해 주세요
    """
    
    # 모델 호출 부분
    response = model.generate_content(prompt)
    return response.text

def send_insight_mail(insight_html, news_list):
    """최종 HTML 조립 및 발송"""
    list_html = "<h3>참고 뉴스 원문 리스트</h3><ul>"
    for item in news_list:
        title = item['title']
        list_html += f"<li><a href='{item['link']}'>{title}</a></li>"
    list_html += "</ul>"

    full_html = f"""
    <div style="font-family: 'Malgun Gothic', sans-serif; line-height: 1.6;">
        <h2 style="color: #2c3e50;">🏦 은행 IT & 신상품 데일리 인사이트</h2>
        <p>{datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d')}</p>
        <hr>
        <div style="background-color: #f9f9f9; padding: 20px; border-radius: 10px;">
            {insight_html}
        </div>
        <br>
        {list_html}
    </div>
    """

    payload = {
        "to": [RECIPIENT_EMAIL], # 하드코딩된 메일 주소를 변수로 교체
        "subject": f"[{datetime.now(timezone(timedelta(hours=9))).date()}] 은행 IT & 신상품 데일리 인사이트",
        "html": full_html
    }

    try:
        response = requests.post(MAIL_API_URL, json=payload)
        if response.status_code in [200, 201]:
            print("메일 발송 성공!")
        else:
            print(f"실패: 메일 API 응답 코드 {response.status_code}")
    except Exception as e:
        print(f"메일 발송 중 오류 발생: {e}")

if __name__ == "__main__":
    news_items = collect_all_news()
    print(f"수집된 뉴스: {len(news_items)}건")
    insights = get_gemini_insight(news_items)
    send_insight_mail(insights, news_items)
