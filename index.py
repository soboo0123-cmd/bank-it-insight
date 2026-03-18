import os
import re
import requests
from datetime import datetime, timezone, timedelta

# 1. 환경 변수 로드 확인
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')

# 2. 화이트리스트 (v2.2 설계안 반영 - 150여 개 Press ID)
WHITELIST_PRESS_IDS = {
    "1032", "1005", "2312", "1020", "2385", "1021", "1081", "1022", "2364", "2268", "2844", "1023", "1025", "2041", "1028", "1469",
    "1001", "1421", "1003", "1422", "1056", "1214", "1055", "1052", "1437", "1019", "1448", "1449", "1374", "1004", "2151", "2656", "2802", "2108", "2155", "2233", "2099", "2916", "2741", "2251", "2221", "2807", "2713", "2423",
    "1009", "1015", "1011", "1018", "1277", "1014", "1016", "1030", "1029", "1092", "1008", "1648", "1366", "2003", "1138", "2046", "2096", "1293", "1123", "2090", "2274", "2366", "2810", "2141", "2499", "2119", "2138", "2282", "2898", "2254", "2792", "2213", "2137", "2214", "2704", "2017", "2506", "2016", "2394", "2374", "2480", "2001", "2528", "2405", "2492", "2609", "2716", "2133", "2015", "2298", "2038", "2524", "2118", "2839", "2296", "2804", "2256", "2036", "2676", "2048", "2752", "2404", "2300", "2781", "2585", "2325", "2201", "2829", "2206", "2140", "2785", "2243", "2177", "2110", "2795",
    "2291", "2525", "2002", "2025", "2515", "2383", "2421", "2735", "2538", "2318", "2745", "2541", "2743", "2742", "2662", "2477", "2805", "2490", "2402", "2847", "2167", "2375", "2451", "2794", "2708", "2915", "2698", "2556"
}

def get_naver_news_debug(query):
    """API 호출 상태를 상세히 출력합니다."""
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
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            items = response.json().get('items', [])
            print(f"✅ [성공] 키워드 '{query}': {len(items)}건 수집")
            return items
        else:
            print(f"❌ [에러] 키워드 '{query}': 상태코드 {response.status_code}")
            print(f"   - 에러 메시지: {response.text}")
            return []
    except Exception as e:
        print(f"⚠️ [예외] 호출 중 오류: {str(e)}")
        return []

def extract_press_id(url):
    match = re.search(r'n\.news\.naver\.com/(?:mnews/)?article/(\d+)/', url)
    return match.group(1) if match else None

def run_debug():
    print("=== [1. 환경 변수 로드 테스트] ===")
    print(f"ID 로드 상태: {'성공' if NAVER_CLIENT_ID else '실패 (None)'}")
    print(f"Secret 로드 상태: {'성공' if NAVER_CLIENT_SECRET else '실패 (None)'}\n")

    if not NAVER_CLIENT_ID:
        print("🛑 환경 변수가 없습니다! Codespaces의 Secrets 설정을 확인하세요.")
        return

    # 1단계 수집
    print("=== [2. 네이버 API 수집 결과] ===")
    queries = ["은행 +AI", "은행 +IT", "은행 +신상품"]
    all_raw = []
    for q in queries:
        all_raw.extend(get_naver_news_debug(q))

    # 2단계 필터링 분석
    print(f"\n=== [3. 필터링 상세 분석 (총 {len(all_raw)}건 대상)] ===")
    seen_urls = set()
    final_items = []
    kst = timezone(timedelta(hours=9))
    limit_time = datetime.now(kst) - timedelta(days=1)

    counts = {"duplicate": 0, "not_naver": 0, "not_whitelist": 0, "old": 0}

    for item in all_raw:
        link = item.get('link', '')
        
        if link in seen_urls:
            counts["duplicate"] += 1
            continue
        seen_urls.add(link)

        if "n.news.naver.com" not in link:
            counts["not_naver"] += 1
            continue

        press_id = extract_press_id(link)
        if not press_id or press_id not in WHITELIST_PRESS_IDS:
            counts["not_whitelist"] += 1
            continue

        try:
            pub_date = datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S +0900').replace(tzinfo=kst)
            if pub_date < limit_time:
                counts["old"] += 1
                continue
        except:
            continue

        final_items.append(item)

    print(f"- 중복 제거: {counts['duplicate']}건")
    print(f"- 네이버링크 아님: {counts['not_naver']}건")
    print(f"- 화이트리스트 아님: {counts['not_whitelist']}건")
    print(f"- 24시간 초과: {counts['old']}건")
    print(f"\n✅ 최종 필터 통과 기사: {len(final_items)}건")

    if final_items:
        print("\n=== [4. 통과된 기사 샘플 (최근 3건)] ===")
        for i, item in enumerate(final_items[:3]):
            print(f"{i+1}. {item['title']} ({item['link']})")

if __name__ == "__main__":
    run_debug()
