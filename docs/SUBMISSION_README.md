# 제출 패키지 안내

## 최종 제출물

- `output/pdf/assignment1_bilateral_analysis.pdf`: 전체 라벨 35,126장을 이용한 양안 등급 분석 보고서
- `output/pdf/assignment2_ai_classification.pdf`: 환자 단위 분리 부분집합 2,000장을 이용한 이미지 분류 보고서
- `web/`: 두 과제의 결과를 확인하고 실제 이미지를 예측하는 로컬 웹 프로그램
- `retina/`: 분석, 모델 학습, 추론, 보고서 생성 코드
- `outputs/assignment1/`: 과제 1 수치, 양안 표, 사례 선택 기록, 차트
- `outputs/assignment2/`: 과제 2 모델, 성능 수치, 테스트 예측 기록, 실제 정답·오답 사례와 민감도 이미지
- `data/manifest.csv`: 과제 2에 사용한 이미지, 라벨, 환자 ID, 분할 목록

원본 89.1GB ZIP은 제출 파일에 복제하지 않는다. `data/images/`는 실제 실행 시 필요한 부분집합이며, 제출 용량 제한이 있으면 제외하고 원본 Drive 링크와 재현 절차를 함께 제공한다.

## 실행

PowerShell에서 프로젝트 폴더로 이동한 뒤 다음 명령을 사용한다.

```powershell
.venv\Scripts\python.exe -m uvicorn retina.server:app --host 127.0.0.1 --port 8765
```

브라우저에서 `http://127.0.0.1:8765`를 연다. 프로그램은 로컬 컴퓨터에서만 접근하도록 설정되어 있다.

## 결과 재현

```powershell
powershell -ExecutionPolicy Bypass -File .\REPRODUCE.ps1
```

과제 2 학습은 CPU 환경에서 시간이 걸릴 수 있다. 생성된 `outputs/assignment2/model.npz`를 포함하면 시연할 때 재학습할 필요가 없다.

## 검증

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check retina tests
.venv\Scripts\python.exe -m basedpyright retina
```

보고서 PDF는 `pdftoppm`으로 모든 페이지를 PNG로 렌더링해 글자 잘림, 이미지 누락, 표 겹침 여부를 확인한다.
과제 2 사례 페이지는 테스트 예측 CSV의 기록 순서에서 첫 정답·첫 오답을 사용하며, 왼쪽 이미지는 모델의 전처리 입력이다. 민감도 색상은 병변 위치가 아니라 가림에 따른 모델 점수 변화를 뜻한다.

## 해석 시 주의

- 두 과제 모두 교육용이며 의료 진단 결과가 아니다.
- 과제 1의 양안 차이는 질병 진행이나 생물학적 비대칭의 원인을 증명하지 않는다.
- 과제 2는 1,000명 부분집합 실험이다. 테스트의 3등급은 7장, 4등급은 5장뿐이라 소수 등급 수치는 불안정하다.
- 프로그램의 등급별 점수는 임상적으로 교정된 질병 확률이나 진단 확신도가 아니다.
