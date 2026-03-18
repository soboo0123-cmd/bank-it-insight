import os
import re
import requests
from datetime import datetime, timezone, timedelta

# 1. 환경 변수 설정 점검
# Codespaces나 Colab에서 실행 시 직접 입력하거나 Secrets 설정이 필요합니다.
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')

# 2. 화이트리스트 (Press ID 150여개 - v2.2 지침 반영)
WHITELIST_PRESS_IDS = {
    "1032", "1005", "2312", "1020", "2385", "1021", "1081", "1022", "2364", "2268", "2844", "1023", "1025", "2041", "1028", "1469",
    "1001", "1421", "1003", "1422", "1056", "1214", "1055", "1052", "1437", "1019", "1448", "1449", "1374", "1004", "2151", "2656", "2802", "2108", "2155", "2233", "2099", "2916", "2741", "2251", "2221", "2807", "2713", "2423",
    "1009", "1015", "1011", "1018", "1277", "1014", "1016", "1030", "1029", "1092", "1008", "1648", "1366", "2003", "1138", "2046", "2096", "1293", "1123", "2090", "2274", "2366", "2810", "2141", "2499", "2119", "2138", "2282", "2898", "2254", "2792", "2213", "2137", "2214", "2704", "2017", "2506", "2016", "2394", "2374", "2480", "2001", "2528", "2405", "2492", "2609", "2716", "2133", "2015", "2298", "2038", "2524", "2118", "2839", "2296", "2804", "2256", "2036", "2676", "2048", "2752", "2404", "2300", "2781", "2585", "2325", "2201", "2829", "2206", "2140", "2785", "2243", "2177", "2110", "2795",
    "2291", "2525", "2002", "2025", "2515", "2383", "2421", "2735", "2538", "2318", "2745", "2541", "2743", "2742", "2662", "2477", "2805", "2490", "2402", "2847", "2167", "2375", "2451", "2794", "2708", "2915", "2698", "2556"
}

def get_naver_news_debug(query):
    """네이버 API 호출 상태를 상세히 출력합니다."""
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
            print(f"✅ [성공] 키워드 '{query}': {len(items)}건 수집됨")
            return items
        else:
            print(f"❌ [에러] 키워드 '{query}': 상태코드 {response.status_code}")
            print(f"   - 메시지: {response.text}")
            return []
    except Exception as e:
        print(f"⚠️ [예외] API 호출 중 오류 발생: {str(e)}")
        return []

def extract_press_id(url):
    """네이버 뉴스 URL에서 Press ID를 추출합니다."""
    match = re.search(r'n\.news\.naver\.com/(?:mnews/)?article/(\d+)/', url)
    return match.group(1) if match else None

def run_debug_process():
    print("=== [환경 변수 점검] ===")
    print(f"NAVER_CLIENT_ID: {'설정됨' if NAVER_CLIENT_ID else '미설정 (None)'}")
    print(f"NAVER_CLIENT_SECRET: {'설정됨' if NAVER_CLIENT_SECRET else '미설정 (None)'}\n")

    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("🛑 API 키가 설정되지 않아 중단합니다. 환경 변수를 확인하세요.\n")
        return

    # 1단계: 원본 데이터 수집
    print("=== [1단계: API 데이터 수집] ===")
    queries = ["은행 +AI", "은행 +IT", "은행 +신상품"]
    all_raw_items = []
    for q in queries:
        all_raw_items.extend(get_naver_news_debug(q))
    
    print(f"\n총 원본 수집 기사: {len(all_raw_items)}건\n")

    # 2단계: 필터링 과정 디버깅
    print("=== [2단계: 필터링 상세 분석] ===")
    seen_urls = set()
    final_items = []
    
    kst = timezone(timedelta(hours=9))
    limit_time = datetime.now(kst) - timedelta(days=1)

    # 통계용 변수
    stats = {
        "total": len(all_raw_items),
        "duplicate": 0,
        "not_naver_link": 0,
        "not_in_whitelist": 0,
        "too_old": 0,
        "passed": 0
    }

    for item in all_raw_items:
        link = item.get('link', '')
        
        # 필터 1: 중복 제거
        if link in seen_urls:
            stats["duplicate"] += 1
            continue
        seen_urls.add(link)

        # 필터 2: 네이버 뉴스 링크 여부
        if "n.news.naver.com" not in link:
            stats["not_naver_link"] += 1
            continue

        # 필터 3: 화이트리스트(Press ID) 체크
        press_id = extract_press_id(link)
        if not press_id or press_id not in WHITELIST_PRESS_IDS:
            stats["not_in_whitelist"] += 1
            continue

        # 필터 4: 24시간 이내 기사 체크
        try:
            # pubDate: "Tue, 17 Mar 2026 10:00:00 +0900"
            pub_date = datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S +0900').replace(tzinfo=kst)
            if pub_date < limit_time:
                stats["too_old"] += 1
                continue
        except Exception as e:
            # 날짜 파싱 실패 시 안전을 위해 제외
            continue

        # 모든 필터 통과
        final_items.append(item)
        stats["passed"] += 1

    # 결과 출력
    print(f"1. 중복 기사 제외: -{stats['duplicate']}건")
    print(f"2. 언론사 직링크(네이버뉴스 아님) 제외: -{stats['not_naver_link']}건")
    print(f"3. 화이트리스트 외 언론사(게임지 등) 제외: -{stats['not_in_whitelist']}건")
    print(f"4. 24시간 이전 기사 제외: -{stats['too_old']}건")
    print("-" * 30)
    print(f"✅ AI에게 전달될 최종 기사: {stats['passed']}건\n")

    if final_items:
        print("=== [3단계: 최종 리스트 샘플] ===")
        for i, item in enumerate(final_items[:10]): # 최대 10개만 출력
            pid = extract_press_id(item['link'])
            print(f"[{i+1}] {item['title']} (ID: {pid})")
        if len(final_items) > 10:
            print(f"... 외 {len(final_items)-10}건")
    else:
        print("⚠️ 주의: 최종 리스트가 비어 있습니다. 필터 조건을 완화하거나 키워드를 점검하세요.")

if __name__ == "__main__":
    run_debug_process()
