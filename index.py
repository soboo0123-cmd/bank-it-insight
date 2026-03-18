import os
import requests
import json
from google import genai
from datetime import datetime, timezone, timedelta

# 1. 환경 변수 설정
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
MAIL_API_URL = os.environ.get('MAIL_API_URL')
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL')

# Gemini 설정
client = genai.Client(api_key=GEMINI_API_KEY)


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
    queries = ["은행 +AI", "은행 +IT", "은행 +신상품", "은행 +디지털"]
    all_items = []
    seen_urls = set()

    kst = timezone(timedelta(hours=9))
    limit_time = datetime.now(kst) - timedelta(days=1)

    allowed_domains = [
        "khan.co.kr", "kmib.co.kr", "naeil.com", "donga.com", "m-i.kr", "munhwa.com", "seoul.co.kr",
        "segye.com", "shinailbo.co.kr", "asiatoday.co.kr", "jeonmae.co.kr", "chosun.com", "joongang.co.kr",
        "newscj.com", "hani.co.kr", "hankookilbo.com", "yna.co.kr", "news1.kr", "newsis.com", "kbs.co.kr",
        "imbc.com", "sbs.co.kr", "ytn.co.kr", "jtbc.co.kr", "mbn.co.kr", "tvchosun.com", "ichannela.com",
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

            if not link or link in seen_urls:
                continue

            try:
                pub_date = datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S +0900').replace(tzinfo=kst)
                is_recent = pub_date >= limit_time
            except:
                is_recent = False

            if not is_recent:
                continue

            is_allowed_url = any(domain in org_link for domain in allowed_domains) or \
                             any(domain in link for domain in allowed_domains) or \
                             ("n.news.naver.com" in link)

            if is_allowed_url:
                all_items.append(item)
                seen_urls.add(link)

    return all_items


def get_gemini_insight(news_list):
    if not news_list:
        return "<div>뉴스 없음</div>"

    news_context = ""
    for i, item in enumerate(news_list):
        title = item['title'].replace('<b>', '').replace('</b>', '')
        desc = item['description'].replace('<b>', '').replace('</b>', '')
        news_context += f"[{i+1}] 제목: {title}\n요약: {desc}\n링크: {item['link']}\n\n"

    prompt = f"""
    [데이터]
    {news_context}
    """

    response = client.models.generate_content(
        model='gemini-3.1-pro-preview',
        contents=prompt
    )

    result = response.text

    # 🔍 DEBUG: Gemini 응답 길이
    print(f"[DEBUG] Gemini 응답 길이: {len(result)}")

    return result


def send_insight_mail(insight_html, news_list):
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
            print(f"메일 발송 성공! (분석 대상 뉴스: {len(news_list)}건)")
        else:
            print(f"실패: 코드 {response.status_code}")
            print(f"[DEBUG] 응답 내용: {response.text}")

    except Exception as e:
        print(f"오류 발생: {e}")


if __name__ == "__main__":
    news_items = collect_all_news()
    print(f"[DEBUG] 뉴스 개수: {len(news_items)}")

    insights = get_gemini_insight(news_items)

    insights = insights.replace('```html', '').replace('```', '').strip()

    send_insight_mail(insights, news_items)
