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
    # 1. 검색어 설정
    queries = ["은행 AI", "은행 IT", "은행 신상품", "은행 디지털"]
    all_items = []
    seen_urls = set()

    # 2. 시간 기준 설정 (현재로부터 24시간 전)
    kst = timezone(timedelta(hours=9))
    limit_time = datetime.now(kst) - timedelta(days=1)
    
    # 3. 허용할 언론사 도메인 리스트 (요청하신 리스트 기반 주요 도메인)
    allowed_domains = [
        # 일간지/방송/통신
        "khan.co.kr", "kmib.co.kr", "naeil.com", "donga.com", "m-i.kr", "munhwa.com", "seoul.co.kr", 
        "segye.com", "shinailbo.co.kr", "asiatoday.co.kr", "jeonmae.co.kr", "chosun.com", "joongang.co.kr", 
        "newscj.com", "hani.co.kr", "hankookilbo.com", "yna.co.kr", "news1.kr", "newsis.com", "kbs.co.kr", 
        "imbc.com", "sbs.co.kr", "ytn.co.kr", "jtbc.co.kr", "mbn.co.kr", "tvchosun.com", "ichannela.com",
        # 경제/IT/전문지
        "mk.co.kr", "hankyung.com", "sedaily.com", "edaily.co.kr", "asiae.co.kr", "fnnews.com", "heraldcorp.com", 
        "etnews.com", "dt.co.kr", "zdnet.co.kr", "mt.co.kr", "bizwatch.co.kr", "etoday.co.kr", "ddaily.co.kr", 
        "itdaily.kr", "datanet.co.kr", "bloter.net", "joseilbo.com", "ajunews.com", "viva100.com", "lawissue.co.kr",
        "ebn.co.kr", "dailyimpact.kr", "digitaltoday.co.kr", "byline.network", "betanews.net", "venturesquare.net",
        "boannews.com", "bizhankook.com", "seoulfn.com", "itworld.co.kr", "ciokorea.com", "itbiznews.com"
    ]

    for q in queries:
        news_items = get_naver_news(q)
        for item in news_items:
            link = item.get('link', '')
            org_link = item.get('originallink', '') # 언론사 원본 주소 활용
            
            if not link or link in seen_urls:
                continue
            
            # [조건 1] 허용할 언론사 URL(도메인)이 포함되어 있는지 확인
            # 기사의 원본 링크(org_link)나 네이버 링크(link)에 허용 도메인이 있는지 대조
            is_allowed_url = any(domain in org_link for domain in allowed_domains) or \
                             any(domain in link for domain in allowed_domains) or \
                             ("n.news.naver.com" in link) # 네이버 뉴스 플랫폼은 기본 허용
            
            # [조건 2] 시간 체크 (24시간 이내)
            try:
                pub_date = datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S +0900').replace(tzinfo=kst)
                is_recent = pub_date >= limit_time
            except:
                is_recent = False

            # 최종 필터링: (허용 언론사) AND (최신성)
            if is_allowed_url and is_recent:
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
