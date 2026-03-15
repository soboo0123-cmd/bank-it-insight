import os
import requests
import google.generativeai as genai
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# 1. 환경 변수 로드 (GitHub Secrets)
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MAIL_API_URL = os.getenv("MAIL_API_URL")

# 2. 네이버 뉴스 수집 함수 (24시간 엄격 필터링)
def get_naver_news(keywords):
    all_news = []
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    
    # 현재 시간 기준으로 24시간 전 시간 계산 (UTC 기준)
    now_utc = datetime.now(timezone.utc)
    threshold_time = now_utc - timedelta(hours=24)
    
    for query in keywords:
        # 넉넉하게 30개를 가져온 뒤 시간으로 잘라냄
        url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=30&sort=date"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            items = response.json().get('items', [])
            for item in items:
                # 네이버 pubDate를 datetime 객체로 변환하여 비교
                item_date = parsedate_to_datetime(item['pubDate'])
                if item_date > threshold_time:
                    all_news.append(item)
    
    # 중복 기사 제거 (링크 기준)
    unique_news = {item['link']: item for item in all_news}.values()
    return list(unique_news)

# 3. Gemini AI 분석 함수 (3.1 Flash-Lite 적용)
def analyze_with_gemini(news_list):
    genai.configure(api_key=GEMINI_API_KEY)
    # 최신 3.1 Flash-Lite 모델 지정
    model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
    
    # 뉴스 데이터를 텍스트로 변환 (태그 그대로 유지)
    news_context = "\n".join([f"제목: {n['title']}\n요약: {n['description']}" for n in news_list])
    
    prompt = f"""
    당신은 금융 IT 전문 분석가입니다. 아래 제공된 최근 24시간 동안의 뉴스 리스트를 보고 업계 현황을 분석해주세요.
    
    [뉴스 데이터]
    {news_context}
    
    [요구사항]
    1. 오늘 핵심 금융 IT 트렌드 3가지를 도출할 것.
    2. 단순 요약이 아닌 업계에 미치는 시사점 위주로 분석할 것.
    3. 메일 본문에 바로 들어갈 수 있도록 HTML 형식(불렛포인트 <ul>, <li> 등)으로 작성할 것.
    """
    
    response = model.generate_content(prompt)
    return response.text

# 4. 메일 발송 함수
def send_insight_mail(insight_html, news_list):
    news_html = "<h3>참고 뉴스 원문 (최근 24시간)</h3><ul>"
    for n in news_list:
        news_html += f"<li><a href='{n['link']}'>{n['title']}</a></li>"
    news_html += "</ul>"
    
    full_html = f"<h2>금융 IT 데일리 인사이트</h2>{insight_html}<hr>{news_html}"
    
    payload = {
        "to": ["soboo@daum.net"], 
        "subject": f"[{datetime.now(timezone(timedelta(hours=9))).date()}] 은행 IT & 신상품 데일리 리포트",
        "html": full_html
    }
    
    response = requests.post(MAIL_API_URL, json=payload)
    return response.status_code

# 5. 메인 실행 로직
if __name__ == "__main__":
    keywords = ["은행 도입", "은행 신상품", "은행 IT", "은행 AI"]
    
    print("1. 최근 24시간 뉴스 수집 중...")
    news = get_naver_news(keywords)
    
    if news:
        print(f"2. {len(news)}건의 뉴스 분석 중...")
        insight = analyze_with_gemini(news)
        
        print("3. 메일 발송 중...")
        status = send_insight_mail(insight, news)
        
        if status == 200:
            print("성공: 인사이트 메일이 발송되었습니다.")
        else:
            print(f"실패: 메일 API 응답 코드 {status}")
    else:
        print("최근 24시간 내에 수집된 뉴스가 없습니다. (메일 발송 생략)")
