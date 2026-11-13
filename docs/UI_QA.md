# UI QA 기록

## 대상과 실행 방법

- 통합 앱: `http://127.0.0.1:8765`
- 구성 요소 상태표: `http://127.0.0.1:8765/showcase`
- 과제 1 오프라인 뷰어: `outputs/assignment1/viewer.html`
- 자동화: `uv run scripts/qa_ui.py`

Playwright와 설치된 Google Chrome을 실제 렌더러로 사용한다. 최종 산출물은 `output/qa/evidence.json`에 모인다.

## 반응형 표면

375×900, 768×900, 1280×900에서 과제 1, 과제 2, 구성 요소 상태표, 오프라인 뷰어를 전체 페이지 캡처한다. 각 화면에서 `document.documentElement.scrollWidth`가 뷰포트 너비를 넘지 않는지 검사한다.

- `analysis-{375,768,1280}.png`
- `model-{375,768,1280}.png`
- `showcase-{375,768,1280}.png`
- `assignment1-offline-{375,768,1280}.png`

## 상호작용 검증

- 과제 탭은 마우스와 좌·우/Home/End 키로 선택되며 `aria-selected`, tab stop, URL hash, 패널 표시가 함께 바뀐다.
- 통합 앱의 `차이 4` 필터는 `aria-pressed=true`, 2개 사례, 제목 `등급 차이 4`를 표시한다. `전체`는 10개 사례로 복원한다.
- 오프라인 뷰어도 같은 필터에서 2개/10개 사례 전환을 확인한다. 빈 필터 상태는 제목 안내, 이미지 숨김, 이전·다음 비활성으로 안전하게 처리된다.
- 실제 브라우저 `DataTransfer`로 텍스트 파일을 드롭해 JPEG/PNG 형식 오류를 확인한다.
- 첫 번째 최종평가 예제를 클릭해 실제 원본을 `/api/predict`로 보내고, 실제 라벨 문맥·5개 점수·가림 민감도까지 기다린다.
- 결과의 `원본 / 가림 민감도` 전환을 실제로 클릭하고, 병변 위치 정답이 아니라는 설명을 함께 캡처한다.
- 과제 1의 `양안 쌍 CSV` 링크는 실제 브라우저 download 이벤트와 `pairs.csv` 파일명을 반환해야 한다.
- `prefers-reduced-motion: reduce`에서 차이 필터를 전환해 축소 동작 경로를 확인한다.
- 오프라인 차트의 `원본 크기로 보기` 링크를 새 창에서 열어 캡처한다.

상호작용 증거:

- `analysis-gap-4.png`
- `assignment1-offline-gap-4.png`
- `prediction-invalid.png`
- `prediction-valid-demo.png`, `prediction-valid-demo-{375,768}.png`
- `prediction-sensitivity.png`
- `analysis-reduced-motion.png`
- `assignment1-chart-fullsize.png`

## 데이터·모델 확인

- 과제 1은 전체 35,126안/17,563쌍의 `summary.json`, 실제 사례 10개의 `examples.json`, 5×5 교차표와 등급 차이 분포를 표시한다.
- 과제 2는 2,000안 교육 하위집합의 환자 단위 1,400/300/300 분할을 표시한다.
- 최종평가 정확도, QWK, macro-F1, 클래스별 지지도·재현율, 혼동행렬을 `metrics.json`에서 읽는다.
- 다수 등급 기준선의 높은 정확도와 낮은 QWK/macro-F1을 같이 보여 정확도 단독 해석을 막는다.
- 원본 2,018장 검증, 환자 분할 중복 0명, 최종평가 1회, manifest SHA-256을 `/api/provenance`에서 읽는다.
- PDF·CSV·JSON 다운로드는 서버 allowlist 안의 산출물만 노출한다.

## 알려진 한계

- 서버는 JPEG/PNG 구조와 10MB 제한을 검증하지만 업로드가 실제 안저 사진인지 판별하도록 학습되지 않았다.
- 모델 출력 점수는 진단 확률이 아니다.
- 가림 민감도는 모델 반응이며 병변 위치 정답이 아니다.
- 최종평가 3등급은 7안, 4등급은 5안이므로 화면에 지지도를 항상 함께 표시한다.
- 외부 웹폰트를 쓰지 않아 운영체제에 따라 글꼴 모양은 달라질 수 있다.
