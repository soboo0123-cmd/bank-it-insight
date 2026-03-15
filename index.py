import os
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta

# 1. 환경 변수 설정 (GitHub Secrets)
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
MAIL_API_URL = os.environ.get('MAIL_API_URL')

# Gemini 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

def get_naver_news(query):
    """네이버 뉴스 API를 통해 정교화된 키워드로 뉴스 수집"""
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {
        "query": query,
        "display": 30, # 각 키워드당 30개 수집
        "start": 1,
        "sort": "sim"  # 정확도 순으로 수집
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get('items', [])
    return []

def collect_all_news():
    """여러 키워드를 순회하며 뉴스를 수집하고 중복을 제거"""
    # 의사결정된 초집중형 키워드 리스트 (+ 연산자 활용)
    queries = ["은행 +AI", "은행 +디지털", "은행 +신상품", "은행 +IT"]
    all_items = []
    seen_urls = set()

    for q in queries:
        news_items = get_naver_news(q)
        for item in news_items:
            # 중복 URL 제거 로직
            if item['link'] not in seen_urls:
                all_items.append(item)
                seen_urls.add(item['link'])
    
    return all_items

def get_gemini_insight(news_list):
    """수집된 뉴스를 바탕으로 Gemini 분석 및 링크 포함 인사이트 생성"""
    if not news_list:
        return "분석할 뉴스 데이터가 없습니다."

    # 분석용 텍스트 구성 (제목과 요약 포함)
    news_context = ""
    for i, item in enumerate(news_list):
        # <b> 태그 등 HTML 태그 제거
        title = item['title'].replace('<b>', '').replace('</b>', '&')
        desc = item['description'].replace('<b>', '').replace('</b>', '&')
        news_context += f"[{i+1}] 제목: {title}\n요약: {desc}\n링크: {item['link']}\n\n"

    prompt = f"""
    당신은 금융 IT 전문 분석가입니다. 아래 제공된 최근 24시간 내의 은행권 뉴스 데이터를 분석하여 리포트를 작성하세요.

    [데이터]
    {news_context}

    [작성 가이드라인]
    1. 현재 은행권의 핵심 트렌드 3가지를 도출하고 상세히 설명하세요.
    2. 분석 내용 중 근거가 되는 문장이나 단락 끝에는 반드시 해당 기사의 링크를 🔗 아이콘으로 연결하세요.
       - 예시: "A은행은 최근 생성형 AI를 대출 심사에 도입했습니다. 🔗" (아이콘에 실제 기사 URL 매핑)
    3. 모든 문장에 링크를 걸 필요는 없으나, 구체적인 사실(신상품 출시, 특정 기술 도입 등)에는 반드시 링크를 포함하세요.
    4. 전문적이고 통찰력 있는 어조를 유지하세요.
    5. HTML 형식으로 작성하며, 링크는 <a href='URL'>🔗</a> 형태로 구현하세요.
    """
    
    response = model.generate_content(prompt)
    return response.text

def send_insight_mail(insight_html, news_list):
    """최종 HTML 조립 및 발송"""
    # 뉴스 리스트 (제목만 포함하는 최신순 리스트)
    list_html = "<h3>참고 뉴스 원문 리스트 (최신 수집순)</h3><ul>"
    for item in news_list:
        title = item['title'].replace('<b>', '').replace('</b>', '')
        list_html += f"<li><a href='{item['link']}'>{title}</a></li>"
    list_html += "</ul>"

    full_html = f"""
    <div style="font-family: 'Malgun Gothic', sans-serif; line-height: 1.6;">
        <h2 style="color: #2c3e50;">🏦 금융 IT & 은행 신상품 데일리 인사이트</h2>
        <p style="color: #7f8c8d;">{datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d')} 리포트</p>
        <hr>
        <div style="background-color: #f9f9f9; padding: 20px; border-radius: 10px;">
            {insight_html}
        </div>
        <br>
        {list_html}
    </div>
    """

    payload = {
        "to": ["soboo@daum.net"], # 수신자 주소 확인
        "subject": f"[{datetime.now(timezone(timedelta(hours=9))).date()}] 은행 IT & 신상품 데일리 인사이트",
        "html": full_html
    }

    try:
        response = requests.post(MAIL_API_URL, json=payload)
        if response.status_code == 200 or response.status_code == 201:
            print("메일 발송 성공!")
        else:
            print(f"실패: 메일 API 응답 코드 {response.status_code}")
            print(f"응답 내용: {response.text}")
    except Exception as e:
        print(f"메일 발송 중 오류 발생: {e}")

if __name__ == "__main__":
    print("1. 뉴스 수집 중 (초집중형 키워드)...")
    news_items = collect_all_news()
    print(f"총 {len(news_items)}건의 고품질 뉴스 확보.")

    print("2. Gemini AI 분석 및 링크 생성 중...")
    insights = get_gemini_insight(news_items)

    print("3. 메일 발송 중...")
    send_insight_mail(insights, news_items)
