"""Eight-page assignment 2 report from genuine held-out model evaluation."""
# pyright: reportImplicitStringConcatenation=false
# ruff: noqa: E501, EM101, EM102, PLR0915, TRY003

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from retina.report_assignment2_results import ResultContext, append_result_pages
from retina.report_data import JsonValue, ReportDataError
from retina.report_layout import (
    data_table,
    metric_cards,
    page_header_footer,
    percentage,
    section_title,
    styles,
)
from retina.report_manifest import SplitSummary


def _mapping(value: JsonValue, name: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ReportDataError(f"Expected object: {name}")
    return value


def _number(data: dict[str, JsonValue], key: str) -> float:
    value = data[key]
    if not isinstance(value, (int, float)):
        raise ReportDataError(f"Expected numeric field: {key}")
    return float(value)


def _integer(data: dict[str, JsonValue], key: str) -> int:
    value = data[key]
    if not isinstance(value, int):
        raise ReportDataError(f"Expected integer field: {key}")
    return value


def _text(data: dict[str, JsonValue], key: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise ReportDataError(f"Expected text field: {key}")
    return value


def _split_row(label: str, summary: SplitSummary) -> list[str]:
    return [label, *[f"{count:,}" for count in summary.grade_counts], f"{summary.image_count:,}"]


def build_assignment2(
    metrics: dict[str, JsonValue],
    examples: list[JsonValue],
    run_config: dict[str, JsonValue],
    manifest: dict[str, SplitSummary],
    destination: Path,
) -> None:
    """Build a source-grounded educational model report."""
    style = styles()
    story: list[Flowable] = []
    dataset = _mapping(metrics["dataset"], "dataset")
    candidates = _mapping(metrics["validation_candidates"], "validation_candidates")
    test = _mapping(metrics["test"], "test")
    baseline = _mapping(metrics["majority_baseline_test"], "majority_baseline_test")
    selected_value = metrics["selected_model"]
    if not isinstance(selected_value, str):
        raise ReportDataError("selected_model must be a string")
    selected = selected_value
    train_count = _integer(dataset, "train")
    validation_count = _integer(dataset, "validation")
    test_count = _integer(dataset, "test")
    test_accuracy = _number(test, "accuracy")
    test_qwk = _number(test, "qwk")
    test_macro = _number(test, "macro_f1")
    train_manifest = manifest["train"]
    validation_manifest = manifest["validation"]
    test_manifest = manifest["test"]
    total_images = sum(item.image_count for item in manifest.values())
    total_patients = sum(item.patient_count for item in manifest.values())
    manifest_sha = _text(run_config, "manifest_sha256").upper()
    versions = ", ".join(
        [
            f"Python {_text(run_config, 'python')}",
            f"torch {_text(run_config, 'torch')}",
            f"torchvision {_text(run_config, 'torchvision')}",
            f"scikit-learn {_text(run_config, 'scikit_learn')}",
        ]
    )
    if (train_count, validation_count, test_count) != (
        train_manifest.image_count,
        validation_manifest.image_count,
        test_manifest.image_count,
    ):
        raise ReportDataError("Metrics dataset counts do not match manifest counts")

    story.extend(
        section_title(
            "과제 2 · 이미지 AI", "안저 이미지로 0~4등급을 얼마나 구분할 수 있을까?", style
        )
    )
    story.append(
        Paragraph(
            "ImageNet 사전학습 MobileNetV3-Small의 고정 특징과 다항 로지스틱 회귀를 결합했다. "
            f"{total_patients:,}명의 양안 {total_images:,}장을 환자 단위로 분리해, 검증 세트에서 모델을 "
            "선택한 뒤 테스트 세트는 한 번만 평가했다.",
            style["body"],
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(
        metric_cards(
            [
                (selected, "선택 모델"),
                (percentage(test_accuracy), "테스트 정확도"),
                (f"{test_qwk:.3f}", "테스트 QWK"),
                (f"{test_macro:.3f}", "테스트 macro-F1"),
            ],
            style,
        )
    )
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("이 수치가 뜻하는 것", style["h2"]))
    story.append(
        Paragraph(
            "테스트 정확도는 전체 정답 비율, QWK는 등급 간 거리까지 고려한 일치도, macro-F1은 각 등급을 "
            "동등하게 취급한 평균 성능이다. 클래스 불균형이 크므로 정확도만으로 모델을 평가하지 않았다.",
            style["body"],
        )
    )
    story.append(
        Paragraph(
            "교육용 부분집합 실험이며 의료 진단용 성능을 검증한 결과가 아니다.", style["small"]
        )
    )

    story.append(PageBreak())
    story.extend(section_title("01 · 평가 설계", "같은 환자의 양쪽 눈은 같은 분할에 둔다", style))
    story.append(
        Paragraph(
            f"전체 라벨에서 양안 최대 등급을 기준으로 자연 분포를 유지하며 {total_patients:,}명을 고정 표본으로 "
            f"추출했다. 이어 환자 ID 기준 {train_manifest.patient_count:,}/{validation_manifest.patient_count:,}/"
            f"{test_manifest.patient_count:,}명으로 분리했다. 같은 환자의 왼쪽 눈이 학습에, 오른쪽 눈이 "
            "테스트에 들어가는 누수를 차단했다.",
            style["body"],
        )
    )
    story.append(
        metric_cards(
            [
                (f"{train_count:,}", f"학습 이미지 · {train_manifest.patient_count:,}명"),
                (
                    f"{validation_count:,}",
                    f"검증 이미지 · {validation_manifest.patient_count:,}명",
                ),
                (f"{test_count:,}", f"테스트 이미지 · {test_manifest.patient_count:,}명"),
            ],
            style,
        )
    )
    story.append(Spacer(1, 7 * mm))
    story.append(
        data_table(
            [
                ["분할", "0등급", "1등급", "2등급", "3등급", "4등급", "합계"],
                _split_row("학습", train_manifest),
                _split_row("검증", validation_manifest),
                _split_row("테스트", test_manifest),
            ],
            [28 * mm] + [23 * mm] * 6,
        )
    )
    story.append(
        Paragraph(
            f"중증 3등급과 증식성 4등급은 테스트에서 각각 {test_manifest.grade_counts[3]:,}장과 "
            f"{test_manifest.grade_counts[4]:,}장뿐이다. 이 등급의 재현율은 한두 장의 "
            "영향이 매우 크므로 안정적인 일반화 성능으로 해석할 수 없다.",
            style["small"],
        )
    )

    story.append(PageBreak())
    story.extend(section_title("02 · 모델 파이프라인", "전처리부터 고정 특징 분류까지", style))
    story.append(
        Paragraph(
            "1. 검은 여백을 제거하고 비율을 유지한 채 320 x 320 RGB 캔버스에 패딩했다.",
            style["body"],
        )
    )
    story.append(
        Paragraph(
            "2. ImageNet 사전학습 MobileNetV3-Small을 고정해 각 이미지의 특징 벡터를 추출했다.",
            style["body"],
        )
    )
    story.append(
        Paragraph(
            "3. 같은 특징에서 일반 로지스틱 회귀와 class_weight='balanced' 모델을 학습했다.",
            style["body"],
        )
    )
    story.append(
        Paragraph(
            "4. 검증 QWK를 우선하고 macro-F1을 보조 기준으로 최종 모델을 선택했다.", style["body"]
        )
    )
    story.append(
        Paragraph(
            f"5. 선택이 끝난 뒤 보관한 테스트 {test_count:,}장을 한 번 평가했다.",
            style["body"],
        )
    )
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("재현성 장치", style["h2"]))
    story.append(
        Paragraph(
            "표본과 분할 난수 시드를 고정하고 manifest.csv에 이미지·라벨·환자 ID·분할을 기록했다. "
            "원본 JPEG는 ZIP 중앙 디렉터리의 바이트 범위로 내려받은 뒤 크기와 CRC를 검증했고 SHA-256과 원본 "
            "해상도를 image_audit.csv에 남겼다. 훈련과 웹 추론은 같은 prepare_image 함수를 사용한다.",
            style["body"],
        )
    )
    story.append(
        Paragraph(
            "특징 추출기는 고정되어 있어 전체 신경망을 미세조정한 실험이 아니다. CPU 환경에서 재현 가능한 "
            f"교육용 기준선을 만드는 선택이다. 실행 환경은 {versions}이며, manifest SHA-256은 "
            f"{manifest_sha}다.",
            style["small"],
        )
    )

    append_result_pages(
        story,
        ResultContext(candidates, selected, test, baseline, examples, total_patients, style),
    )

    document = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        rightMargin=19 * mm,
        leftMargin=19 * mm,
        topMargin=19 * mm,
        bottomMargin=19 * mm,
    )
    document.build(story, onFirstPage=page_header_footer, onLaterPages=page_header_footer)
