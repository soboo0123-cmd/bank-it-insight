import os
import re
import requests
from datetime import datetime, timezone, timedelta

# 1. 환경 변수 설정 (테스트용)
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')

# 2. 화이트리스트 (Press ID)
WHITELIST_PRESS_IDS = {
    "1032", "1005", "2312", "1020", "2385", "1021", "1081", "1022", "2364", "2268", "2844", "1023", "1025", "2041", "1028", "1469",
    "1001", "1421", "1003", "1422", "1056", "1214", "1055", "1052", "1437", "1019", "1448", "1449", "1374", "1004", "2151", "2656", "2802", "2108", "2155", "2233", "2099", "2916", "2741", "2251", "2221", "2807", "2713", "2423",
    "1009", "1015", "1011", "1018", "1277", "1014", "1016", "1030", "1029", "1092", "1008", "1648", "1366", "2003", "1138", "2046", "2096", "1293", "1123", "2090", "2274", "2366", "2810", "2141", "2499", "2119", "2138", "2282", "2898", "2254", "2792", "2213", "2137", "2214", "2704", "2017", "2506", "2016", "2394", "2374", "2480", "2001", "2528", "2405", "2492", "2609", "2716", "2133", "2015", "2298", "2038", "2524", "2118", "2839", "2296", "2804", "2256", "2036", "2676", "2048", "2752", "2404", "2300", "2781", "2585", "2325", "2201", "2829", "2206", "2140", "2785", "2243", "2177", "2110", "2795",
    "2291", "2525", "2002", "2025", "2515", "2383", "2421", "2735", "2538", "2318", "2745", "2541", "2743", "2742", "2662", "2477", "2805", "2490", "2402", "2847", "2167", "2375", "2451", "2794", "2708", "2915", "2698", "2556"
}

def get_naver_news(query):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    params = {"query": query, "display": 50, "start": 1, "sort": "date"}
    response = requests.get(url, headers=headers, params=params)
    return response.json().get('items', []) if response.status_code == 200 else []

def extract_press_id(url):
    match = re.search(r'n\.news\.naver\.com/(?:mnews/)?article/(\d+)/', url)
    return match.group(1) if match else None

def debug_collect_news():
    queries = ["은행 +AI", "은행 +IT", "은행 +신상품"]
    all_raw_items = []
    
    # 1단계: API 원본 수집
    print("--- [1단계] 네이버 API 호출 ---")
    for q in queries:
        items = get_naver_news(q)
        print(f"'{q}' 검색 결과: {len(items)}건")
        all_raw_items.extend(items)
    print(f"총 수집된 원본 기사: {len(all_raw_items)}건\n")

    # 2단계: 필터링 진행 상황 확인
    print("--- [2단계] 필터링 프로세스 시작 ---")
    seen_urls = set()
    final_items = []
    
    kst = timezone(timedelta(hours=9))
    limit_time = datetime.now(kst) - timedelta(days=1)

    counts = {"total": len(all_raw_items), "dup": 0, "not_naver": 0, "not_whitelist": 0, "old": 0, "pass": 0}

    for item in all_raw_items:
        link = item.get('link', '')
        
        # 중복 체크
        if link in seen_urls:
            counts["dup"] += 1
            continue
        seen_urls.add(link)

        # 네이버 뉴스 여부
        if "n.news.naver.com" not in link:
            counts["not_naver"] += 1
            continue

        # 화이트리스트 체크
        press_id = extract_press_id(link)
        if not press_id or press_id not in WHITELIST_PRESS_IDS:
            counts["not_whitelist"] += 1
            continue

        # 시간 체크 (24시간 이내)
        try:
            pub_date = datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S +0900').replace(tzinfo=kst)
            if pub_date < limit_time:
                counts["old"] += 1
                continue
        except:
            continue

        # 모든 필터 통과
        counts["pass"] += 1
        final_items.append(item)

    print(f"1. 중복 제거로 탈락: {counts['dup']}건")
    print(f"2. 네이버 뉴스 링크가 아니어서 탈락: {counts['not_naver']}건")
    print(f"3. 화이트리스트(Press ID) 미포함으로 탈락: {counts['not_whitelist']}건")
    print(f"4. 24시간 이전 기사라 탈락: {counts['old']}건")
    print(f"\n✅ 최종 AI에게 전달될 기사 수: {counts['pass']}건")
    
    if final_items:
        print("\n--- [3단계] AI에게 보낼 최종 제목 리스트 ---")
        for i, item in enumerate(final_items):
            print(f"{i+1}. [{extract_press_id(item['link'])}] {item['title']}")
    else:
        print("\n❌ 필터링 후 남은 기사가 없습니다. 화이트리스트 ID나 네이버 뉴스 링크 여부를 확인하세요.")

if __name__ == "__main__":
    debug_collect_news()
