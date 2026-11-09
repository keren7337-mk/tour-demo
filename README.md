# 어디 갈까? — 한국관광공사 TourAPI 활용 예제

시도·시군구를 고르면 관광지·문화시설·음식점 등을 지도와 사진으로 보여 주고, 장소를 고르면 소개글을 띄웁니다. 두 번째 탭에서는 기간 안에 열리는 축제·행사를 볼 수 있습니다.

## 실행

```
pip install -r requirements.txt
```

1. `.env.example`을 복사해 이름을 `.env`로 바꿉니다. (메모장에서 저장할 때 파일 형식은 '모든 파일')
2. `.env`를 열어 `TOUR_API_KEY=` 뒤에 공공데이터포털 인증키를 붙여 넣습니다.
   - 마이페이지 > 데이터활용 > Open API > 인증키 발급현황
   - Encoding 키, Decoding 키 어느 쪽이든 작동합니다.
3. 실행합니다.

```
streamlit run app.py
```

키가 없으면 사이드바에서 **예시 데이터**를 고르면 화면을 확인할 수 있습니다. (예시 데이터는 모두 가상)

## 사용하는 API (국문 관광정보 서비스 KorService2, 활용매뉴얼 v4.4)

| 기능 | 오퍼레이션 |
|---|---|
| 시도·시군구 목록 | `ldongCode2` |
| 지역별 목록 | `areaBasedList2` |
| 키워드 검색 | `searchKeyword2` |
| 축제·행사 | `searchFestival2` |
| 소개글·홈페이지 | `detailCommon2` |

- 기본 주소: `https://apis.data.go.kr/B551011/KorService2/{오퍼레이션}`
- 공통 필수 값: `serviceKey`, `MobileOS`, `MobileApp` / JSON으로 받으려면 `_type=json`
- 개발계정은 오퍼레이션별 하루 1,000건까지 → 같은 조회는 1시간 동안 다시 보내지 않도록 캐시해 두었습니다.

## 자주 나는 오류

| 메시지 | 원인 |
|---|---|
| `SERVICE_KEY_IS_NOT_REGISTERED_ERROR (코드 30)` | 키가 틀렸거나, 승인 직후라 아직 반영 전(10~30분 소요) |
| `.env 파일에서 TOUR_API_KEY를 찾지 못했습니다` | 파일 이름이 `.env.txt`로 저장됨, 또는 다른 폴더에 있음 |
| `LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR (코드 22)` | 하루 호출 한도 초과 |
| 결과가 없습니다 | 해당 지역·종류에 데이터가 없음, 키워드를 바꿔 보기 |

사진에는 저작권 유형이 붙어 있습니다. 제3유형은 출처 표시와 함께 변경 금지입니다.
