# Retina Pair Lab 디자인 시스템

## 0. Reference and intent

- 2026-11-13 실제 참고 서비스(`retina-age.intra.avrosoft.co.kr`)를 Chrome 375/768/1280px에서 조사했다. 런타임 증거는 `artifacts/reference/`에 있으며 `getComputedStyle`로 색·타입·간격·상태를 추출했다.
- 참고 서비스에서 가져오는 것은 종이색 바탕, 짙은 광학 스테이지, 선과 여백 중심의 계층, 즉시 실행 가능한 예제, 데이터·평가·운영 근거를 같은 제품 안에서 보여 주는 방식이다. 연령 예측, ODIR, ConvNeXt, 운영 로그와 수치는 가져오지 않는다.
- 두 과제와 Retina Pair Lab의 이름·콘텐츠·검증 범위는 그대로 유지한다. 정확한 복제물이 아니라 현재 2,000안 교육 데이터와 실제 산출물에 맞춘 과학 워크스페이스다.
- 화면의 기억점은 두 개의 실제 안저 사진이 하나의 어두운 광학 프레임 안에서 마주 보는 `Bilateral Stage`다.
- 분위기는 따뜻한 종이 위에 잉크로 기록한 임상 연구 노트다. 청록색은 인터랙션과 상태에만 쓰고, 붉은 망막 사진이 화면의 주인공이 되게 한다.
- Layer A: `taste-skill.md`의 운영 화면 밀도와 계층 규칙. 구체적 참고: 사용자가 제공한 질환 설명 카드 및 양안 비교 방향.

## 1. Product principles

1. **Evidence before effect**: 모든 큰 숫자에는 분모, 지표명, 해석 한계를 붙인다.
2. **Retina first**: 실제 안저 이미지는 장식이 아니라 비교 대상이다. 썸네일로 축소하지 않고 충분한 관찰 면적을 준다.
3. **One decision per surface**: 한 카드에는 하나의 질문만 둔다. 분석, 사례 탐색, 예측은 별도 구역으로 분리한다.
4. **Educational boundary**: 모델 점수는 진단 확률이라고 부르지 않는다. 교육용 데이터 실험이라는 문구가 예측 결과 가까이에 항상 보인다.

## 2. Tokens

### Color

| Token | Value | Use |
|---|---:|---|
| `--paper` | `#f3f5f2` | page background, reference runtime |
| `--paper-raised` | `#fbfcfa` | primary surfaces |
| `--paper-deep` | `#e8ece8` | hover, subtle bands, reference runtime |
| `--ink` | `#14302f` | primary text, reference runtime |
| `--ink-soft` | `#47605d` | supporting text, reference runtime |
| `--line` | `#cdd7d2` | dividers and borders |
| `--teal` | `#1e7f5e` | action and active state, reference runtime |
| `--teal-deep` | `#175f48` | high contrast state, reference runtime |
| `--teal-pale` | `#dce5e1` | status fill, reference runtime |
| `--amber` | `#c8741a` | caution and focus, reference runtime |
| `--optic` | `#0b1211` | image stage, reference runtime |
| `--white` | `#f3f5f2` | text on dark surfaces |
| `--danger` | `#9f3b32` | errors only |

No raw color values may appear in component CSS outside these token declarations.

### Type

- Sans: `Pretendard`, `SUIT`, `Noto Sans KR`, system sans-serif. 외부 웹폰트는 불러오지 않는다.
- Display: sans 계열 700을 사용한다. 참고 서비스의 압축 영문체는 숫자 눈금과 작은 라벨의 자간으로만 재해석한다.
- Numeric: `Arial`, system sans-serif with `font-variant-numeric: tabular-nums`.
- Scale: 12, 14, 16, 20, 28, 40, 64px. Fluid display uses `clamp(2.2rem, 6vw, 4rem)`.

### Spacing and shape

- Space: 4, 8, 12, 16, 24, 32, 48, 72px.
- Radius: 8px controls, 12px panels, 18px image stage, full pill only for state tags and selected filters.
- Shadow: 기본 종이 패널은 그림자를 쓰지 않고 선과 여백으로 구분한다. 광학 스테이지만 얕은 inset과 어두운 그림자를 허용한다.
- Content width: 1180px max with 24px desktop gutters and 16px mobile gutters.

## 3. Layout grammar

- Sticky top bar contains product name, project status, and the two task tabs. 데스크톱 높이는 약 64px이며 모바일에서는 브랜드 아래에 탭이 흐른다.
- Hero is a compact orientation band, not a landing-page billboard. 선택 과제의 실제 기능과 근거가 첫 화면에 들어오도록 세로 여백을 줄인다.
- Assignment 1 uses a 5/7 split: evidence rail and bilateral stage. On mobile the evidence rail precedes images.
- Assignment 2 uses an upload/result split that becomes a single column below 820px.
- All scroll ownership remains with the document. No nested page-level scroll panes.

## 4. Content hierarchy

1. Orient: dataset identity and educational boundary.
2. Prove: verified counts and bilateral agreement.
3. Explore: switch real patient examples and inspect grades.
4. Predict: upload one image and receive the trained model's actual output.
5. Qualify: show held-out metrics and limitations next to the prediction surface.

## 5. Reusable primitives

- `Topbar`: brand, status, task navigation. States: default, active tab, keyboard focus.
- `Section label`: eyebrow, title, explanatory copy.
- `Evidence tile`: value, label, denominator/context. States: populated, loading, unavailable.
- `Metric strip`: compact horizontal evidence row; wraps on narrow screens.
- `Optic frame`: dark bilateral image stage with left/right labels and grade badges. States: loaded, missing image, error.
- `Case selector`: previous/next buttons plus case counter. States: default, hover, focus, disabled.
- `Gap filter`: 전체/0/1/2/3/4 단일 선택 pill. 선택 시 해당 사례만 순환하며 결과 수를 즉시 알린다.
- `Grade badge`: grade number and Korean label. Five fixed grade variants use the common amber/teal ramp without implying clinical urgency.
- `Upload well`: native file input with visible label. States: idle, drag, selected, loading, invalid.
- `Demo eye`: held-out 원본 2개를 클릭하면 사용자 업로드와 같은 예측 경로를 실행한다. 실제 라벨과 사전 계산 예측을 함께 표시한다.
- `Score row`: class label, visual bar, numeric score. The bar is descriptive model output, not probability language.
- `Image mode toggle`: 원본/가림 민감도 단일 선택 segment. 가림 민감도는 모델 반응이며 병변 위치 정답이 아니다.
- `Evidence table`: confusion matrix, split support, provenance, download links. 작은 화면에서는 표 컨테이너만 가로 스크롤한다.
- `Notice`: info, caution, error variants.
- `Skeleton`: quiet block fill with a single opacity pulse; disabled by reduced-motion.

Primitive showcase: `web/showcase.html` exercises default, loading, disabled, focusable, and error states before product-screen QA.

## 6. Interaction and motion

- Task tabs update `aria-selected`, URL hash, and panel visibility without a page reload. beui.dev `tabs`의 단일 tab-stop과 방향키 이동 규칙을 적용한다.
- Gap filters and the image-mode toggle use the beui.dev `tabs` mechanism: selected 상태가 명시적으로 이동하고, 색/불투명도는 140ms로 바뀌며 reduced-motion에서는 즉시 전환한다.
- Upload follows the beui.dev `file-upload` state contract: drag depth를 추적하고, 유효성 오류와 비동기 분석 상태가 같은 표면에서 명확히 바뀐다.
- Case navigation replaces the pair with a 140ms opacity transition. It never slides because left/right direction already carries meaning.
- Upload state changes from idle to selected to analyzing; submit is disabled while analyzing.
- Motion uses only opacity and transform, duration 120-180ms, `cubic-bezier(.2,.8,.2,1)`.
- `prefers-reduced-motion: reduce` removes transitions and skeleton animation.

## 7. Accessibility constraints

- Body text contrast targets WCAG AA; primary controls target AAA where possible.
- All controls have visible `:focus-visible` outlines at least 3px wide.
- Tabs follow button semantics with `role=tab`, `aria-controls`, and keyboard focus.
- Images have contextual alt text including side and provided grade; no diagnostic interpretation is inserted into alt text.
- Score information is present as text in addition to bar length.
- Minimum hit area is 44px. Layout remains readable at 200% zoom and 375px width.
- Errors are placed in an `aria-live=polite` region and do not rely on color alone.

## 8. Accepted debt and handoff

- Web fonts are intentionally not loaded from a CDN so the app works offline. Typeface rendering therefore varies by machine.
- The assignment charts are static generated figures; their source data is also exposed as text/JSON for access.
- The model sensitivity image is optional. If the trained adapter does not provide one, the UI explains that it is unavailable instead of fabricating a visualization.
- 라이브 참고 서비스의 외부 폰트는 복제하지 않는다. 오프라인 제출물에서 글꼴이 달라질 수 있으나 시스템 글꼴 계층과 고정된 크기·행간은 유지한다.
- Final browser evidence must cover 375, 768, and 1280px, both task panels, upload validation, missing-model state, and reduced-motion behavior.
