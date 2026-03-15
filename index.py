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
    제공된 뉴스 데이터를 바탕으로, 시독성이 뛰어난 HTML 리포트를 작성하세요.
    
    [데이터]
    {news_context}
    
    [작성 가이드라인 - 아래 순서를 반드시 엄수할 것]
    
    1. <종합 브리핑 (Executive Summary)>:
       - 최상단에 배치하고, 배경색이 연한 회색(#f8f9fa)인 <div> 태그로 강조하세요.
       - **[폰트 강조]** 경영진이 바로 읽을 수 있도록 본문보다 큰 폰트 크기(font-size: 1.1em; line-height: 1.8;)를 적용하세요.
       - **[핵심 내용]** 거시적인 표현 대신 **신한, 국민, 하나 등 구체적인 은행명과 사업 명칭**을 직접 언급하며 3~4문장으로 전략적 시사점을 도출하세요.
       - **[링크 배치]** 근거가 되는 원문 링크를 각 문장이 끝나는 마침표 바로 앞에 <a href='URL'>🔗</a> 형태로 삽입하세요. 

    2. <카테고리별 주요 기사 분류>:
       - 아래 4가지 카테고리로 기사를 분류하세요:
         ① 경영전략 ② 신상품 ③ IT(기술/보안) ④ 기타
       - **[레이아웃 변경]** 카테고리 제목(<h3>) 바로 옆에 해당 분야의 [핵심 트렌드]를 한 줄로 나란히 배치하세요. 
         (예: <h3>① 경영전략 <span style='font-size: 0.8em; color: #555; font-weight: normal;'>| 핵심 트렌드: 지역 거점 플랫폼 및 디지털 동맹 강화</span></h3>)
       - 기사가 없는 카테고리는 "해당 분야 주요 기사 없음"이라고 표시하세요.
       - **[데이터 보존]** 각 기사의 [기사내용desc]는 **원문을 절대 수정하거나 요약하지 말고 텍스트 그대로(As-is) 전체를 표시**하세요. 네이버 <br> 태그도 유지해야 합니다.
       - 각 기사는 <ul>과 <li>를 사용하며, 기사 제목에 원문 링크를 삽입하세요.
    
    3. 전문적인 어조를 유지하고, 섹션 구분이 명확하도록 HTML 스타일을 적절히 활용하세요.
    """
    
    # 모델 호출 부분
    response = model.generate_content(prompt)
    return response.text

def send_insight_mail(insight_html, news_list): # 1. news_list 인자 추가
    """최종 HTML 조립 및 발송"""
    list_html = "<h3>참고 뉴스 원문 리스트</h3><ul>"
    for item in news_list: # 2. 반복할 대상(news_list) 지정
        # HTML 태그 제거 및 제목 정리
        title = item['title'].replace('<b>', '').replace('</b>', '')
        list_html += f"<li><a href='{item['link']}'>{title}</a></li>"
    list_html += "</ul>"

    full_html = f"""
    <div style="font-family: 'Malgun Gothic', sans-serif; line-height: 1.6;">
        <div style="padding: 20px; border-radius: 10px;"> {insight_html}
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
