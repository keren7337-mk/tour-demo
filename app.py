"""
어디 갈까? — 한국관광공사 국문 관광정보 서비스(TourAPI, KorService2) 활용 예제

실행:  streamlit run app.py
준비:  같은 폴더의 .env 파일에  TOUR_API_KEY=공공데이터포털에서_받은_인증키  를 적어 둡니다.
       (Encoding 키, Decoding 키 어느 쪽을 넣어도 작동합니다.)
       키가 없으면 사이드바에서 '예시 데이터'를 골라 화면을 확인할 수 있습니다.

사용하는 오퍼레이션 (국문 관광정보 활용매뉴얼 v4.4 기준)
  - ldongCode2         법정동 코드 조회   → 시도·시군구 목록
  - areaBasedList2     지역기반 관광정보 조회
  - searchKeyword2     키워드 검색 조회
  - searchFestival2    행사정보 조회
  - detailCommon2      공통정보 조회(개요·홈페이지)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")  # 인증키는 코드가 아니라 .env 파일에서 읽는다

BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
SAMPLE_FILE = BASE_DIR / "sample_data.json"

# 관광타입(contentTypeId) — 매뉴얼의 국문 콘텐츠타입 코드표
CONTENT_TYPES = {
    "전체": None, "관광지": "12", "문화시설": "14", "행사/공연/축제": "15", "여행코스": "25",
    "레포츠": "28", "숙박": "32", "쇼핑": "38", "음식점": "39",
}
TYPE_NAMES = {v: k for k, v in CONTENT_TYPES.items() if v}


class TourAPIError(Exception):
    pass


# ---------------------------------------------------------------------------
# API 호출
# ---------------------------------------------------------------------------
def service_key() -> str:
    key = os.getenv("TOUR_API_KEY", "").strip()
    # 공공데이터포털은 Encoding/Decoding 두 가지 키를 준다.
    # requests가 주소를 한 번 더 인코딩하므로, Encoding 키(%가 들어 있음)는 풀어서 쓴다.
    return unquote(key) if "%" in key else key


def parse_items(data: dict) -> tuple[list[dict], int]:
    """응답 구조: response → header(resultCode) / body → items → item[]"""
    resp = data.get("response", {})
    header = resp.get("header", {})
    code = str(header.get("resultCode", "0000"))
    if code not in ("0000", "00"):
        raise TourAPIError(f"결과 코드 {code}: {header.get('resultMsg', '')}")
    body = resp.get("body", {})
    total = int(body.get("totalCount", 0) or 0)
    items = body.get("items")
    if not items:  # 결과가 0건이면 items가 빈 문자열("")로 온다
        return [], total
    item = items.get("item", [])
    if isinstance(item, dict):  # 한 건이면 목록이 아니라 객체 하나로 올 수 있다
        item = [item]
    return item, total


@st.cache_data(ttl=3600, show_spinner=False)  # 같은 요청은 1시간 동안 다시 보내지 않는다(일 1,000건 제한)
def call_api(operation: str, params: tuple) -> tuple[list[dict], int]:
    key = service_key()
    if not key:
        raise TourAPIError(".env 파일에서 TOUR_API_KEY를 찾지 못했습니다.")
    query = {"serviceKey": key, "MobileOS": "WEB", "MobileApp": "VibeTourDemo", "_type": "json", **dict(params)}
    res = requests.get(f"{BASE_URL}/{operation}", params=query, timeout=20)
    text = res.text.strip()
    if text.startswith("<"):
        # 공공데이터포털의 인증 오류는 _type=json을 붙여도 XML로만 온다
        reason = re.search(r"<returnAuthMsg>(.*?)</returnAuthMsg>", text)
        code = re.search(r"<returnReasonCode>(.*?)</returnReasonCode>", text)
        msg = reason.group(1) if reason else text[:300]
        raise TourAPIError(f"{msg} (코드 {code.group(1) if code else '?'})")
    res.raise_for_status()
    try:
        data = res.json()
    except json.JSONDecodeError:
        raise TourAPIError("JSON이 아닌 응답이 왔습니다:\n" + text[:300])
    return parse_items(data)


def api(operation: str, **params) -> tuple[list[dict], int]:
    clean = tuple(sorted((k, v) for k, v in params.items() if v not in (None, "")))
    if st.session_state.get("source") == "예시 데이터":
        return sample(operation, dict(clean))
    return call_api(operation, clean)


# ---------------------------------------------------------------------------
# 예시 데이터 (키가 없을 때 화면 확인용, 내용은 모두 가상)
# ---------------------------------------------------------------------------
SAMPLE = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))


def sample(operation: str, params: dict) -> tuple[list[dict], int]:
    if operation == "ldongCode2":
        rows = SAMPLE["sigungu"].get(params["lDongRegnCd"], []) if "lDongRegnCd" in params else SAMPLE["sido"]
        return rows, len(rows)
    if operation == "detailCommon2":
        rows = [d for d in SAMPLE["detail"] if d["contentid"] == params.get("contentId")]
        return rows, len(rows)
    rows = SAMPLE["festivals"] if operation == "searchFestival2" else SAMPLE["places"]
    if params.get("lDongRegnCd"):
        rows = [r for r in rows if r["lDongRegnCd"] == params["lDongRegnCd"]]
    if params.get("lDongSignguCd"):
        rows = [r for r in rows if r["lDongSignguCd"] == params["lDongSignguCd"]]
    if params.get("contentTypeId"):
        rows = [r for r in rows if r["contenttypeid"] == params["contentTypeId"]]
    if params.get("keyword"):
        rows = [r for r in rows if params["keyword"] in r["title"]]
    return rows, len(rows)


# ---------------------------------------------------------------------------
# 도움 함수
# ---------------------------------------------------------------------------
def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.I)
    return re.sub(r"<[^>]+>", "", text).strip()


def first_url(text: str) -> str | None:
    m = re.search(r'https?://[^\s"<>]+', text or "")
    return m.group(0) if m else None


def fmt_date(s: str) -> str:
    return f"{s[:4]}.{s[4:6]}.{s[6:8]}" if s and len(s) >= 8 else "-"


def show_map(rows: list[dict]):
    pts = pd.DataFrame(
        [{"lat": r.get("mapy"), "lon": r.get("mapx")} for r in rows]
    ).apply(pd.to_numeric, errors="coerce").dropna()
    pts = pts[(pts["lat"] != 0) & (pts["lon"] != 0)]
    if len(pts):
        st.map(pts, size=60)


def show_error(e: Exception):
    st.error("데이터를 가져오지 못했습니다. 아래 메시지를 복사해 Claude Code에 붙여 넣어 보세요.")
    st.code(f"{type(e).__name__}: {e}")
    st.stop()


# ---------------------------------------------------------------------------
# 화면
# ---------------------------------------------------------------------------
st.set_page_config(page_title="어디 갈까?", page_icon="🧭", layout="wide")
st.title("🧭 어디 갈까?")
st.caption("데이터·사진 출처: 한국관광공사 국문 관광정보 서비스(TourAPI) · 공공데이터포털")

with st.sidebar:
    st.header("설정")
    st.radio(
        "데이터", ["실제 API", "예시 데이터"], key="source",
        index=0 if service_key() else 1,
        help="인증키가 없거나 승인 전이면 '예시 데이터'로 화면을 확인하세요.",
    )
    if st.session_state.source == "예시 데이터":
        st.info("예시 데이터는 모두 가상입니다.")

    try:
        sido_rows, _ = api("ldongCode2", numOfRows=50)
    except Exception as e:
        show_error(e)
    sido = {r["name"]: r["code"] for r in sido_rows}
    sido_name = st.selectbox("시도", list(sido))
    sido_code = sido[sido_name]

    try:
        sgg_rows, _ = api("ldongCode2", lDongRegnCd=sido_code, numOfRows=100)
    except Exception as e:
        show_error(e)
    sgg = {"전체": None} | {r["name"]: r["code"] for r in sgg_rows}
    sgg_name = st.selectbox("시군구", list(sgg))
    sgg_code = sgg[sgg_name]

tab_place, tab_festival = st.tabs(["📍 관광정보 찾기", "🎉 축제·행사"])

# --- 관광정보 찾기 ------------------------------------------------------------
with tab_place:
    c1, c2 = st.columns([1, 2])
    type_name = c1.selectbox("종류", list(CONTENT_TYPES), index=1)
    keyword = c2.text_input("키워드 (비워 두면 지역 전체)", placeholder="예: 시장, 해수욕장, 박물관")

    params = dict(
        lDongRegnCd=sido_code, lDongSignguCd=sgg_code,
        contentTypeId=CONTENT_TYPES[type_name], numOfRows=30, pageNo=1, arrange="Q",  # Q = 대표 이미지가 있는 것, 수정일순
    )
    try:
        if keyword.strip():
            places, total = api("searchKeyword2", keyword=keyword.strip(), **params)
        else:
            places, total = api("areaBasedList2", **params)
    except Exception as e:
        show_error(e)

    where = sido_name if not sgg_code else f"{sido_name} {sgg_name}"
    st.subheader(f"{where} · {type_name}" + (f" · '{keyword}'" if keyword.strip() else ""))
    if not places:
        st.warning("결과가 없습니다. 지역이나 종류, 키워드를 바꿔 보세요.")
    else:
        st.caption(f"전체 {total:,}건 중 {len(places)}건 표시")
        show_map(places)

        cols = st.columns(3)
        for i, p in enumerate(places):
            with cols[i % 3]:
                if p.get("firstimage"):
                    st.image(p["firstimage"], use_container_width=True)
                st.markdown(f"**{p.get('title', '')}**")
                st.caption(f"{TYPE_NAMES.get(p.get('contenttypeid'), '')} · {p.get('addr1', '')}")

        st.divider()
        st.subheader("자세히 보기")
        chosen = st.selectbox("장소 선택", places, format_func=lambda p: p.get("title", ""))
        try:
            detail, _ = api("detailCommon2", contentId=chosen["contentid"])
        except Exception as e:
            show_error(e)
        if detail:
            d = detail[0]
            left, right = st.columns([1, 2])
            if d.get("firstimage"):
                left.image(d["firstimage"], use_container_width=True)
            right.markdown(f"### {d.get('title', '')}")
            right.write(f"📍 {d.get('addr1', '')} {d.get('addr2', '')}")
            if d.get("tel"):
                right.write(f"☎️ {strip_html(d['tel'])}")
            url = first_url(d.get("homepage", ""))
            if url:
                right.markdown(f"🔗 [홈페이지]({url})")
            right.write(strip_html(d.get("overview", "")) or "개요 정보가 없습니다.")
            if d.get("cpyrhtDivCd") == "Type3":
                right.caption("사진 저작권: 제3유형(출처표시 + 변경금지) — 사진을 자르거나 고쳐 쓰면 안 됩니다.")
            elif d.get("cpyrhtDivCd") == "Type1":
                right.caption("사진 저작권: 제1유형(출처표시)")

# --- 축제·행사 ----------------------------------------------------------------
with tab_festival:
    today = dt.date.today()
    period = st.date_input("행사 기간", (today, today + dt.timedelta(days=60)))
    if not (isinstance(period, tuple) and len(period) == 2):
        st.info("시작일과 종료일을 모두 골라 주세요.")
    else:
        try:
            events, total = api(
                "searchFestival2",
                eventStartDate=period[0].strftime("%Y%m%d"), eventEndDate=period[1].strftime("%Y%m%d"),
                lDongRegnCd=sido_code, lDongSignguCd=sgg_code, numOfRows=50, pageNo=1, arrange="C",
            )
        except Exception as e:
            show_error(e)
        if not events:
            st.warning("이 기간에 등록된 행사가 없습니다.")
        else:
            events.sort(key=lambda e: e.get("eventstartdate", ""))
            st.caption(f"{sido_name} {sgg_name if sgg_code else ''} · 전체 {total:,}건 중 {len(events)}건")
            show_map(events)
            for e in events:
                with st.container(border=True):
                    a, b = st.columns([1, 4])
                    if e.get("firstimage2"):
                        a.image(e["firstimage2"], use_container_width=True)
                    b.markdown(f"**{e.get('title', '')}**")
                    b.write(f"🗓️ {fmt_date(e.get('eventstartdate'))} ~ {fmt_date(e.get('eventenddate'))}")
                    b.caption(f"{e.get('addr1', '')} {e.get('addr2', '')}")
