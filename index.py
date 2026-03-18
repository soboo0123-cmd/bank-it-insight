import os
import requests
from google import genai # import 방식 변경
from datetime import datetime, timezone, timedelta

# 1. 환경 변수 설정
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
MAIL_API_URL = os.environ.get('MAIL_API_URL')
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL')

# Gemini 설정
client = genai.Client(api_key=GEMINI_API_KEY)
# model = genai.GenerativeModel('gemini-3.1-pro-preview')
# model = genai.GenerativeModel('gemini-2.5-flash') # 안정적인 flash 모델 권장

def get_naver_news(query):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {
        "query": query,
        "display": 100,
        "start": 1,
        "sort": "date"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get('items', [])
    return []

def collect_all_news():
    # 1. 검색어 설정 (은행 키워드 강화를 위해 + 기호 포함)
    queries = ["은행 +AI", "은행 +IT", "은행 +신상품", "은행 +디지털"]
    all_items = []
    seen_urls = set()

    # 2. 시간 기준 설정 (현재로부터 24시간 전)
    kst = timezone(timedelta(hours=9))
    limit_time = datetime.now(kst) - timedelta(days=1)
    
    # 3. 허용할 언론사 도메인 리스트
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
            org_link = item.get('originallink', '')
            
            # [필터 1] URL이 동일한 것은 제외 (중복 제거)
            if not link or link in seen_urls:
                continue
            
            # [필터 2] 1일(24시간) 초과 제외
            try:
                # 네이버 pubDate 포맷: 'Mon, 26 Sep 2016 07:50:00 +0900'
                pub_date = datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S +0900').replace(tzinfo=kst)
                is_recent = pub_date >= limit_time
            except:
                is_recent = False
            
            if not is_recent:
                continue

            # [필터 3] allowed_domains에 있는 기사들만 남기기
            # 원본 링크(org_link)나 변환 링크(link)에 허용 도메인이 포함되어 있는지 확인
            is_allowed_url = any(domain in org_link for domain in allowed_domains) or \
                             any(domain in link for domain in allowed_domains) or \
                             ("n.news.naver.com" in link) # 네이버 뉴스 플랫폼 링크 허용
            
            if is_allowed_url:
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
    
    [작성 가이드라인 - 아래 순서를 반드시 엄수할 것]
    
    1. <종합 브리핑>:
       - 최상단에 배치하고, 배경색이 연한 회색(#f8f9fa)인 <div> 태그로 강조하세요.
       - **[핵심 지침]** 거시적인 표현(예: 금융권은~, 가속화하고 있다~)을 지양하고, **구체적인 은행명과 사업 명칭을 직접 언급**하며 서술하세요.
       - 오늘 뉴스 중 가장 중요한 **경쟁사들의 실질적인 액션(신상품 출시, 조직 개편, 파트너십 등)**을 중심으로 3~4문장의 전략적 통찰을 제공하세요.
       - (예: "단순히 기술 협력을 합니다" (X) -> "하나금융이 SC그룹과 디지털 자산 동맹을 맺고 글로벌 시장 선점에 나섰습니다" (O))
      - **[링크 배치]** 각 문장의 근거가 되는 원문 링크를 문장 끝 마침표 바로 앞에 <a href='URL'>🔗</a> 형태로 삽입하세요.

    2. <카테고리별 주요 기사 분류>:
       - 아래 4가지 카테고리로 기사를 분류하여 배치하세요:
         ① 경영전략 ② 신상품 ③ IT(기술/보안) ④ 기타
       - **[레이아웃 변경]** 카테고리 제목(<h3>) 바로 옆에 해당 분야의 [핵심 트렌드]를 한 줄로 나란히 배치하세요. 
       - 기사가 없는 카테고리는 "해당 분야 주요 기사 없음"이라고 표시하세요.
       - 카테고리별로 각 기사를 관통하는 핵심 트렌드를 한 줄로 요약하여 제시하세요.
       - **[중요]** 각 기사의 [기사내용desc]는 **데이터로 제공된 원문을 임의로 요약하거나 수정하지 말고 텍스트 그대로(As-is) 전체를 표시**하세요. 네이버에서 전달받은 <br> 태그 등 HTML 서식도 그대로 유지해야 합니다.
       - 각 기사는 <ul>과 <li>를 사용하며, 기사 제목에 원문 링크를 삽입하세요.
    
    3. 전문적인 어조(예: ~로 분석됨, ~이 요망됨)를 유지하고, <h3> 태그로 섹션을 명확히 구분하여 가독성을 극대화하세요.
    """
    
    # 모델 호출 부분
    # response = model.generate_content(prompt)
    # return response.text

    response = client.models.generate_content(
        model='gemini-3.1-pro-preview', 
        contents=prompt
    )
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
