"""Actual held-out case studies for the assignment 2 PDF."""
# pyright: reportImplicitStringConcatenation=false
# ruff: noqa: E501, EM101, EM102, TRY003

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Image, PageBreak, Paragraph, Spacer, Table, TableStyle

from retina.report_data import ROOT, JsonValue, ReportDataError
from retina.report_layout import section_title


def _mapping(value: JsonValue, name: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ReportDataError(f"Expected object: {name}")
    return value


def _text(data: dict[str, JsonValue], key: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise ReportDataError(f"Expected text field: {key}")
    return value


def _grade(data: dict[str, JsonValue], key: str) -> int:
    value = data[key]
    if not isinstance(value, int):
        raise ReportDataError(f"Expected integer field: {key}")
    return value


def _case_row(
    case: dict[str, JsonValue],
    label: str,
    style: dict[str, ParagraphStyle],
) -> list[Flowable]:
    base = ROOT / "outputs/assignment2/examples"
    input_path = base / _text(case, "input_file")
    sensitivity_path = base / _text(case, "sensitivity_file")
    missing = [str(path) for path in (input_path, sensitivity_path) if not path.exists()]
    if missing:
        raise ReportDataError(f"Missing assignment 2 case image: {', '.join(missing)}")
    image_name = _text(case, "image")
    actual = _grade(case, "actual")
    predicted = _grade(case, "predicted")
    image_size = 58 * mm
    table = Table(
        [
            [
                Image(str(input_path), image_size, image_size),
                Image(str(sensitivity_path), image_size, image_size),
            ]
        ],
        colWidths=[75 * mm, 75 * mm],
        rowHeights=[image_size],
    )
    table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    return [
        Paragraph(
            f"{label} · ID {image_name} · 실제 {actual}등급 / 예측 {predicted}등급",
            style["h2"],
        ),
        table,
        Paragraph("왼쪽: 전처리 입력 · 오른쪽: 가림(occlusion) 민감도", style["caption"]),
        Spacer(1, 3 * mm),
    ]


def append_case_study_page(
    story: list[Flowable],
    examples: list[JsonValue],
    style: dict[str, ParagraphStyle],
) -> None:
    """Append every available deterministic held-out example without inventing one."""
    maximum_count = 2
    if len(examples) > maximum_count:
        raise ReportDataError("Expected at most two assignment 2 examples")
    by_kind: dict[str, dict[str, JsonValue]] = {}
    for index, value in enumerate(examples):
        case = _mapping(value, f"examples[{index}]")
        kind = _text(case, "kind")
        if kind not in {"correct", "incorrect"} or kind in by_kind:
            raise ReportDataError("Examples may contain one correct and one incorrect case")
        by_kind[kind] = case

    story.append(PageBreak())
    story.extend(section_title("06 · 사례 분석", "실제 테스트 이미지와 모델 민감도", style))
    for kind, label in (("correct", "정답 사례"), ("incorrect", "오답 사례")):
        case = by_kind.get(kind)
        if case is None:
            story.append(
                Paragraph(
                    f"{label}: 해당 범주의 예측이 없어 사례를 만들지 않았다.",
                    style["body"],
                )
            )
            story.append(Spacer(1, 4 * mm))
        else:
            story.extend(_case_row(case, label, style))
    story.append(
        Paragraph(
            "내보낸 사례는 테스트 예측 CSV에 기록된 순서(환자 ID 숫자 오름차순, 같은 ID에서는 이미지명 순)에서 "
            "각 범주의 첫 항목을 선택했다. 범주가 없으면 사례도 만들지 않았다. 따라서 보기 좋은 사례를 "
            "임의로 골라 성능을 과장하지 않았다. 붉은 영역은 해당 부분을 가렸을 때 선택 등급 점수가 낮아졌고, "
            "푸른 영역은 점수가 높아졌음을 뜻한다. 이는 모델 민감도일 뿐 병변 위치나 의학적 설명이 아니다.",
            style["small"],
        )
    )
