# 과제 1 — 양안 등급 차이 분석

이 ZIP은 전체 `trainLabels.csv`의 35,126개 라벨을 환자 ID 기준 17,563개 좌·우 쌍으로 결합한 분석 제출물입니다.

## 바로 확인하기

1. `report.pdf`를 열어 분석 보고서를 읽습니다.
2. `outputs/assignment1/viewer.html`을 더블클릭해 독립 실행형 결과 화면을 엽니다.

뷰어는 서버나 인터넷 연결이 필요하지 않습니다. 차트와 20개 사례 이미지는 같은 폴더의 상대 경로에서 읽습니다.

## 분석 재현

Python 3.12와 `uv`가 설치된 Windows PowerShell에서 ZIP 루트 기준으로 실행합니다.

```powershell
uv venv .venv --python 3.12
uv pip install --python .\.venv\Scripts\python.exe -r requirements.txt
.\.venv\Scripts\python.exe -m retina.analysis trainLabels.csv outputs/assignment1
```

재실행하면 `summary.json`, `pairs.csv`, `examples.json`, 4개 차트와 최신 JSON이 내장된 `viewer.html`이 같은 경로에 생성됩니다. 사례 이미지 썸네일은 제출용으로 이미 포함되어 있습니다.

## 주요 파일

- `report.pdf`: 최종 보고서
- `outputs/assignment1/viewer.html`: 오프라인 결과 화면
- `outputs/assignment1/summary.json`: 핵심 통계
- `outputs/assignment1/pairs.csv`: 전체 양안 쌍
- `outputs/assignment1/examples.json`: 재현 가능한 사례 선정 기록
- `docs/assignment1_report.md`: 보고서 원문
- `retina/analysis.py`, `retina/charts.py`: 재현 코드
- `retina/viewer.py`, `retina/templates/assignment1_viewer.html`: 오프라인 뷰어 생성기와 템플릿
- `PACKAGE_MANIFEST.json`: 포함 파일별 크기와 SHA-256

결과는 제공 라벨의 관계를 설명하는 교육용 분석이며 임상적 인과나 진단을 뜻하지 않습니다.
