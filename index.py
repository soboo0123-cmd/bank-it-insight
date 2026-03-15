import os
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta

# 1. 환경 변수 설정
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
MAIL_API_URL = os.environ.get('MAIL_API_URL')

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
        title = item['title'].replace('<b>', '').replace('</b>', '')
        desc = item['description'].replace('<b>', '').replace('</b>', '')
        news_context += f"[{i+1}] 제목: {title}\n요약: {desc}\n링크: {item['link']}\n\n"

    prompt = f"""
    당신은 금융 IT 전문 분석가입니다. 아래 제공된 뉴스 데이터를 분석하여 리포트를 작성하세요.

    [데이터]
    {news_context}

    [작성 가이드라인]
    1. 현재 은행권의 핵심 트렌드 3가지를 도출하고 설명하세요.
    2. 분석 내용 중 근거가 되는 문장 뒤에는 해당 기사의 링크를 🔗 아이콘으로 연결하세요.
       - 형식: <a href='URL'>🔗</a>
    3. 전문적인 어조를 유지하며 HTML 형식으로 작성하세요.
    """
    
    # 모델 호출 부분
    response = model.generate_content(prompt)
    return response.text

def send_insight_mail(insight_html, news_list):
    list_html = "<h3>참고 뉴스 원문 리스트</h3><ul>"
    for item in news_list:
        title = item['title'].replace('<b>', '').replace('</b>', '')
        list_html += f"<li><a href='{item['link']}'>{title}</a></li>"
    list_html += "</ul>"

    full_html = f"""
    <div style="font-family: 'Malgun Gothic', sans-serif; line-height: 1.6;">
        <h2 style="color: #2c3e50;">🏦 금융 IT & 은행 신상품 데일리 인사이트</h2>
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
        "to": ["soboo@daum.net"],
        "subject": f"[{datetime.now(timezone(timedelta(hours=9))).date()}] 은행 IT 인사이트",
        "html": full_html
    }

    try:
        response = requests.post(MAIL_API_URL, json=payload)
        if response.status_code in [200, 201]:
            print("메일 발송 성공!")
        else:
            print(f"메일 발송 실패: {response.status_code}")
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    news_items = collect_all_news()
    print(f"수집된 뉴스: {len(news_items)}건")
    insights = get_gemini_insight(news_items)
    send_insight_mail(insights, news_items)
