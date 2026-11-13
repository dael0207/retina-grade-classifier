"""Result and limitation pages for the assignment 2 PDF."""
# pyright: reportImplicitStringConcatenation=false
# ruff: noqa: E501, EM101, EM102, TRY003

from dataclasses import dataclass

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, PageBreak, Paragraph, Spacer

from retina.report_assignment2_cases import append_case_study_page
from retina.report_data import JsonValue, ReportDataError
from retina.report_layout import confusion_rows, data_table, metric_cards, percentage, section_title


@dataclass(frozen=True, slots=True)
class ResultContext:
    """Evidence required to render the final five model pages."""

    candidates: dict[str, JsonValue]
    selected: str
    test: dict[str, JsonValue]
    baseline: dict[str, JsonValue]
    examples: list[JsonValue]
    total_patients: int
    style: dict[str, ParagraphStyle]


def _number(data: dict[str, JsonValue], key: str) -> float:
    value = data[key]
    if not isinstance(value, (int, float)):
        raise ReportDataError(f"Expected numeric field: {key}")
    return float(value)


def _mapping(value: JsonValue, name: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ReportDataError(f"Expected object: {name}")
    return value


def _metric_rows(candidates: dict[str, JsonValue], selected: str) -> list[list[str]]:
    rows = [["모델", "검증 정확도", "검증 QWK", "검증 macro-F1", "선택"]]
    for name in ("unweighted", "balanced"):
        metrics = _mapping(candidates[name], name)
        rows.append(
            [
                name,
                percentage(_number(metrics, "accuracy")),
                f"{_number(metrics, 'qwk'):.4f}",
                f"{_number(metrics, 'macro_f1'):.4f}",
                "●" if name == selected else "",
            ]
        )
    return rows


def _matrix(metrics: dict[str, JsonValue]) -> list[list[int]]:
    raw = metrics["confusion_matrix"]
    if not isinstance(raw, list):
        raise ReportDataError("Expected confusion_matrix list")
    matrix: list[list[int]] = []
    for row in raw:
        if not isinstance(row, list) or not all(isinstance(item, int) for item in row):
            raise ReportDataError("Confusion matrix rows must contain integers")
        matrix.append([item for item in row if isinstance(item, int)])
    return matrix


def _recalls(metrics: dict[str, JsonValue]) -> list[list[str]]:
    raw = _mapping(metrics["recall_by_grade"], "recall_by_grade")
    rows = [["등급", "표본 수", "테스트 재현율", "해석"]]
    labels = ["없음", "경증", "중등도", "중증", "증식성"]
    supports = [sum(row) for row in _matrix(metrics)]
    for grade, label in enumerate(labels):
        value = raw[str(grade)]
        if not isinstance(value, (int, float)):
            raise ReportDataError(f"Invalid recall for grade {grade}")
        rows.append([str(grade), str(supports[grade]), percentage(float(value)), label])
    return rows


def _validation_recall_rows(candidates: dict[str, JsonValue]) -> list[list[str]]:
    """Compare per-grade validation recall for both selection candidates."""
    rows = [["후보", "0등급", "1등급", "2등급", "3등급", "4등급"]]
    for name in ("unweighted", "balanced"):
        metrics = _mapping(candidates[name], name)
        recalls = _mapping(metrics["recall_by_grade"], f"{name}.recall_by_grade")
        values: list[str] = []
        for grade in range(5):
            value = recalls[str(grade)]
            if not isinstance(value, (int, float)):
                raise ReportDataError(f"Invalid validation recall for grade {grade}")
            values.append(percentage(float(value)))
        rows.append([name, *values])
    return rows


def append_result_pages(
    story: list[Flowable],
    context: ResultContext,
) -> None:
    """Append validation, test, error, case-study, and limitation pages."""
    candidates = context.candidates
    selected = context.selected
    test = context.test
    baseline = context.baseline
    style = context.style
    test_accuracy = _number(test, "accuracy")
    test_qwk = _number(test, "qwk")
    test_macro = _number(test, "macro_f1")
    test_supports = [sum(row) for row in _matrix(test)]
    story.append(PageBreak())
    story.extend(section_title("03 · 검증 세트 선택", "두 후보를 같은 분할에서 비교", style))
    story.append(
        data_table(
            _metric_rows(candidates, selected), [40 * mm, 34 * mm, 34 * mm, 36 * mm, 20 * mm]
        )
    )
    story.append(Spacer(1, 7 * mm))
    story.append(
        Paragraph(
            f"선택된 모델은 {selected}이다. 모델 선택은 테스트 결과를 보지 않고 검증 QWK와 macro-F1으로 완료했다. "
            "클래스 가중치는 다수 등급의 영향력을 줄이는 대신 전체 정확도를 낮출 수 있으므로 실제 검증 결과로 "
            "선택 여부를 결정했다.",
            style["body"],
        )
    )
    story.append(
        Paragraph(
            "후보가 두 개뿐인 소규모 비교이며, 하이퍼파라미터 탐색이나 여러 신경망 구조 비교를 수행한 결과는 아니다.",
            style["small"],
        )
    )
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("검증 등급별 재현율", style["h2"]))
    story.append(
        data_table(
            _validation_recall_rows(candidates),
            [42 * mm, 24 * mm, 24 * mm, 24 * mm, 24 * mm, 24 * mm],
        )
    )

    story.append(PageBreak())
    story.extend(section_title("04 · 최종 테스트", "다수 클래스 기준선과 함께 읽기", style))
    story.append(
        data_table(
            [
                ["모델", "정확도", "QWK", "macro-F1"],
                [
                    f"선택 모델 ({selected})",
                    percentage(test_accuracy),
                    f"{test_qwk:.4f}",
                    f"{test_macro:.4f}",
                ],
                [
                    "다수 클래스 기준선",
                    percentage(_number(baseline, "accuracy")),
                    f"{_number(baseline, 'qwk'):.4f}",
                    f"{_number(baseline, 'macro_f1'):.4f}",
                ],
            ],
            [61 * mm, 35 * mm, 35 * mm, 35 * mm],
        )
    )
    story.append(Spacer(1, 8 * mm))
    story.append(
        metric_cards(
            [
                (
                    f"{(test_accuracy - _number(baseline, 'accuracy')) * 100:+.2f}%p",
                    "정확도 변화",
                ),
                (f"{test_qwk - _number(baseline, 'qwk'):+.3f}", "QWK 변화"),
                (
                    f"{test_macro - _number(baseline, 'macro_f1'):+.3f}",
                    "macro-F1 변화",
                ),
            ],
            style,
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            f"선택 모델의 정확도 {percentage(test_accuracy)}는 다수 클래스 기준선 "
            f"{percentage(_number(baseline, 'accuracy'))}보다 낮다. 그러나 기준선의 QWK는 0이고 macro-F1은 "
            f"{_number(baseline, 'macro_f1'):.4f}인 반면, 선택 모델은 QWK {test_qwk:.4f}, macro-F1 "
            f"{test_macro:.4f}로 순서형·등급 균형 지표가 더 높다. 정확도 하나만 높이는 것과 여러 등급을 "
            "구분하는 것은 다른 목표임을 보여준다.",
            style["body"],
        )
    )

    story.append(PageBreak())
    story.extend(section_title("05 · 등급별 오류", "혼동행렬과 재현율", style))
    story.append(data_table(confusion_rows(_matrix(test)), [34 * mm] + [25 * mm] * 5))
    story.append(Spacer(1, 6 * mm))
    story.append(data_table(_recalls(test), [24 * mm, 30 * mm, 55 * mm, 53 * mm]))
    story.append(Spacer(1, 5 * mm))
    story.append(
        Paragraph(
            "혼동행렬의 행은 실제 등급, 열은 예측 등급이다. 재현율 0은 해당 등급을 한 장도 맞히지 못했다는 뜻이다. "
            "소수 등급에서 낮은 값이 관찰되면 실제 활용 전에 더 많은 자료, 임상적으로 검증된 외부 평가, "
            "교정과 오류 분석이 필요하다.",
            style["body"],
        )
    )
    story.append(
        Paragraph(
            f"이 테스트에서 1등급 {test_supports[1]:,}장과 3등급 {test_supports[3]:,}장은 한 장도 맞히지 못했다. "
            f"4등급 재현율은 {percentage(_number(_mapping(test['recall_by_grade'], 'recall_by_grade'), '4'))}지만 "
            f"표본이 {test_supports[4]:,}장뿐이어서 안정적인 일반화 성능으로 해석할 수 없다.",
            style["small"],
        )
    )

    append_case_study_page(story, context.examples, style)

    story.append(PageBreak())
    story.extend(section_title("07 · 한계와 재현", "모델 점수는 진단 확률이 아니다", style))
    story.append(
        Paragraph(
            f"이 실험은 전체 라벨이 아니라 자연 분포를 보존한 {context.total_patients:,}명 부분집합을 사용했다. ImageNet 특징을 "
            "고정했으며 외부 병원 자료, 카메라 차이, 인구집단 변화에 대한 검증이 없다. 웹 화면의 5개 점수는 "
            "분류기가 만든 상대 점수이며 임상적으로 교정된 질병 확률이나 진단 확신도가 아니다.",
            style["body"],
        )
    )
    story.append(Paragraph("실행 및 재현", style["h2"]))
    story.append(
        Paragraph(
            "학습: python -m retina.training --manifest data/manifest.csv --image-dir data/images --output-dir outputs/assignment2<br/>"
            "검증: python -m pytest tests/test_model.py -q<br/>"
            "시연: python -m uvicorn retina.server:app --host 127.0.0.1 --port 8765",
            style["small"],
        )
    )
    story.append(Paragraph("참고자료", style["h2"]))
    story.append(
        Paragraph(
            "Kaggle Diabetic Retinopathy Detection data / evaluation<br/>"
            "https://www.kaggle.com/c/diabetic-retinopathy-detection/data<br/>"
            "https://www.kaggle.com/competitions/diabetic-retinopathy-detection<br/>"
            "Torchvision MobileNetV3 documentation<br/>https://pytorch.org/vision/stable/models/mobilenetv3.html",
            style["small"],
        )
    )
    story.append(Paragraph("참고 프로젝트와의 차이", style["h2"]))
    story.append(
        Paragraph(
            "참고 글 https://ai.intra.avrosoft.co.kr/posts/261113002 및 실행 앱 "
            "https://retina-age.intra.avrosoft.co.kr/ 은 EyePACS와 나이 라벨이 있는 ODIR-5K를 사용한 "
            "망막 나이 표현을 다룬다. 현재 자료에는 image와 level만 있고 나이 정답이 없으므로, 이 과제는 "
            "가능한 결과 제시 개선을 참고했을 뿐 화면을 일대일로 복제하지 않았다. 같은 나이 예측 모델이나 "
            "동등한 성능을 구현했다고 주장하지 않는다.",
            style["small"],
        )
    )
