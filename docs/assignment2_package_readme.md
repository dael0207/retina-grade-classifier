# 과제 2 — 안저 이미지 5등급 분류 앱

이 ZIP은 환자 단위로 분리한 1,000명·2,000장 표본에서 만든 교육용 분류 모델, 평가 기록, 로컬 FastAPI 앱을 포함합니다.

## 바로 실행하기

Windows에서 `START_APP.bat`을 더블클릭합니다. 필요한 경우 `INSTALL.ps1`이 프로젝트 전용 `.venv`를 만들고 CPU용 PyTorch를 설치합니다. 준비가 끝나면 브라우저에서 <http://127.0.0.1:8765>가 열립니다. 서버 콘솔에서 `Ctrl+C`를 누르면 종료됩니다.

직접 실행하려면 ZIP 루트의 PowerShell에서 다음 명령을 사용합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\INSTALL.ps1
.\.venv\Scripts\python.exe -m uvicorn retina.server:app --host 127.0.0.1 --port 8765
```

`uv`가 없다면 <https://docs.astral.sh/uv/getting-started/installation/>에서 먼저 설치합니다.

## 주요 파일

- `report.pdf`: 8쪽 최종 보고서
- `START_APP.bat`, `INSTALL.ps1`: 로컬 앱 실행과 전용 환경 설치
- `pyproject.toml`, `uv.lock`: Windows CPU 실행 환경의 정확한 잠금 정보
- `web/`: 실제 앱 화면 소스
- `outputs/assignment2/model.npz`: 선택된 분류기
- `outputs/assignment2/backbone.pth`: 오프라인 특징 추출 백본
- `outputs/assignment2/metrics.json`: 최종평가 지표와 혼동행렬
- `outputs/assignment2/predictions.csv`: 보류 테스트 예측 300건
- `outputs/assignment2/run_config.json`, `training.log`: 실행 설정과 재구성 기록
- `outputs/assignment2/examples/`: 정답·오답 입력 및 가림 민감도 사례
- `data/manifest.csv`, `data/image_audit.csv`, `data/integrity.json`: 환자 분할과 원본 무결성 근거
- `QA_SUMMARY.md`: 추출 후 앱·API·반응형 화면 최종 검증
- `PACKAGE_MANIFEST.json`: 포함 파일별 크기와 SHA-256
- `DATA_LICENSE.md`, `docs/REFERENCE_COMPARISON.md`: 데이터 출처·이용 조건과 참고 서비스 대비 범위

## 전체 파이프라인 재현

`REPRODUCE.ps1`은 분석, 환자 표본 생성, 필요한 원본 부분 다운로드, 무결성 검사, 모델 학습, 현재 예측 CSV에 따른 정답·오답 사례 내보내기, 보고서와 ZIP 생성을 차례로 실행합니다. `-SkipTraining`을 사용해도 기존 모델과 예측에서 사례 파일을 다시 만들어 하드코딩된 환자 ID에 의존하지 않습니다. 네트워크와 CPU 시간이 필요하며 기존 제출 결과를 확인하는 데는 재학습이 필요하지 않습니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\REPRODUCE.ps1
```

모델 출력 점수는 의료 진단 확률이 아니며, 가림 민감도 화면도 병변 위치의 정답이 아닙니다.
