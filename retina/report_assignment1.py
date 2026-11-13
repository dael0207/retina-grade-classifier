"""Seven-page assignment 1 report from full-label bilateral analysis."""
# pyright: reportImplicitStringConcatenation=false
# ruff: noqa: E501, EM101, EM102, PLR0915, RUF001, TRY003

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from retina.report_data import ROOT, JsonValue, ReportDataError
from retina.report_images import paired_images
from retina.report_layout import (
    chart,
    data_table,
    metric_cards,
    page_header_footer,
    percentage,
    section_title,
    styles,
)


def _integer(data: dict[str, JsonValue], key: str) -> int:
    value = data[key]
    if not isinstance(value, int):
        raise ReportDataError(f"Expected integer field: {key}")
    return value


def _number(data: dict[str, JsonValue], key: str) -> float:
    value = data[key]
    if not isinstance(value, (int, float)):
        raise ReportDataError(f"Expected numeric field: {key}")
    return float(value)


def _int_list(data: dict[str, JsonValue], key: str) -> list[int]:
    value = data[key]
    if not isinstance(value, list) or not all(isinstance(item, int) for item in value):
        raise ReportDataError(f"Expected integer list: {key}")
    return [item for item in value if isinstance(item, int)]


def _number_list(data: dict[str, JsonValue], key: str) -> list[float]:
    value = data[key]
    if not isinstance(value, list) or not all(isinstance(item, (int, float)) for item in value):
        raise ReportDataError(f"Expected numeric list: {key}")
    return [float(item) for item in value if isinstance(item, (int, float))]


def _matrix(data: dict[str, JsonValue], key: str) -> list[list[int]]:
    value = data[key]
    if not isinstance(value, list):
        raise ReportDataError(f"Expected matrix: {key}")
    matrix: list[list[int]] = []
    for row in value:
        if not isinstance(row, list) or not all(isinstance(item, int) for item in row):
            raise ReportDataError(f"Expected integer matrix: {key}")
        matrix.append([item for item in row if isinstance(item, int)])
    grade_count = 5
    if len(matrix) != grade_count or any(len(row) != grade_count for row in matrix):
        raise ReportDataError(f"Expected 5 x 5 matrix: {key}")
    return matrix


def _pairs(data: dict[str, JsonValue]) -> list[dict[str, JsonValue]]:
    value = data["pairs"]
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ReportDataError("Expected pair records in examples.json")
    return [item for item in value if isinstance(item, dict)]


def _pair(
    story: list[Flowable], record: dict[str, JsonValue], style: dict[str, ParagraphStyle]
) -> None:
    patient = record["patient_id"]
    left_name = record["left_image"]
    right_name = record["right_image"]
    left_grade = record["left_grade"]
    right_grade = record["right_grade"]
    difference = record["difference"]
    if not isinstance(left_name, str) or not isinstance(right_name, str):
        raise ReportDataError("Example image names must be strings")
    story.append(
        paired_images(
            ROOT / "data/images" / f"{left_name}.jpg",
            ROOT / "data/images" / f"{right_name}.jpg",
            f"ID {patient} · 양안 원본 비교",
            f"ID {patient} · 왼쪽 {left_grade}등급 · 오른쪽 {right_grade}등급 · 절대 차이 {difference}",
            style,
        )
    )


def build_assignment1(
    summary: dict[str, JsonValue], examples: dict[str, JsonValue], destination: Path
) -> None:
    """Build a source-grounded bilateral analysis PDF."""
    style = styles()
    story: list[Flowable] = []
    images = _integer(summary, "image_count")
    patients = _integer(summary, "patient_count")
    agreement = _number(summary, "exact_agreement")
    affected = _number(summary, "affected_exact_agreement")
    kappa = _number(summary, "weighted_kappa")
    class_counts = _int_list(summary, "class_counts")
    class_percentages = _number_list(summary, "class_percentages")
    differences = _int_list(summary, "difference_counts")
    cross_matrix = _matrix(summary, "cross_matrix")
    discordant_count = _integer(summary, "discordant_count")
    discordant_percentage = _number(summary, "discordant_percentage") / 100
    large_gap_count = _integer(summary, "large_gap_count")
    affected_patients = _integer(summary, "affected_patient_count")
    diagonal = [cross_matrix[index][index] for index in range(5)]

    story.extend(
        section_title("과제 1 · 데이터 분석", "같은 사람의 두 눈, 등급은 얼마나 다를까?", style)
    )
    story.append(
        Paragraph(
            f"{images:,}장의 라벨을 ID 기준으로 결합해 {patients:,}개의 완전한 양안 쌍을 분석했다. "
            "전체 일치율과 질환 관련 등급이 표시된 하위 집단을 분리해 0등급 다수의 영향을 확인했다.",
            style["body"],
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(
        metric_cards(
            [
                (f"{images:,}", "전체 안저 이미지"),
                (f"{patients:,}", "완전한 양안 ID"),
                (percentage(agreement), "전체 정확 일치율"),
                (f"{kappa:.3f}", "양안 QWK"),
            ],
            style,
        )
    )
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("핵심 결과", style["h2"]))
    story.append(
        Paragraph(
            f"전체 양안 등급은 {percentage(agreement)} 일치했지만, 적어도 한쪽이 1등급 이상인 집단의 "
            f"일치율은 {percentage(affected)}였다. 따라서 높은 전체 일치율을 양안 질환 상태가 항상 같다는 "
            "뜻으로 해석할 수 없다.",
            style["body"],
        )
    )
    story.append(
        Paragraph(
            "이 보고서는 교육용 데이터 분석이며 질병의 원인, 진행 또는 진단을 판정하지 않는다.",
            style["small"],
        )
    )

    story.append(PageBreak())
    story.extend(
        section_title("01 · 데이터와 방법", "파일 구조를 환자 단위 분석표로 바꾸기", style)
    )
    story.append(
        Paragraph(
            "제공 ZIP은 약 89.1GB이다. 전체 압축을 복제하지 않고 중앙 디렉터리와 trainLabels.csv를 부분 요청으로 "
            "확인했다. 라벨 열은 image와 level뿐이며 나이·성별·촬영 시점은 없다. image에서 ID와 left/right를 "
            "분리한 뒤 각 ID에 양쪽 눈이 한 장씩 있는지, 등급이 0~4인지, 중복이 없는지 검사했다.",
            style["body"],
        )
    )
    story.append(chart(ROOT / "outputs/assignment1/01_class_distribution.png", 144 * mm))
    rows = [
        ["등급", "0", "1", "2", "3", "4"],
        ["이미지 수", *[f"{value:,}" for value in class_counts]],
    ]
    story.append(data_table(rows, [31 * mm] + [28 * mm] * 5))
    story.append(
        Paragraph(
            f"0등급은 전체 이미지의 {class_percentages[0]:.2f}%다. 이 불균형 때문에 전체 정확도 또는 전체 일치율 하나만 제시하면 "
            "소수 등급의 특성이 가려질 수 있다.",
            style["small"],
        )
    )
    story.append(Paragraph("분석 단위와 검증", style["h2"]))
    story.append(
        Paragraph(
            "한 행은 이미지 한 장이지만 연구 질문의 단위는 환자 ID다. 좌우 방향을 분리한 뒤 ID마다 "
            f"왼쪽과 오른쪽이 정확히 한 장씩 존재하는지 확인했고, 누락·중복 없이 {patients:,}쌍을 얻었다. "
            "이 구조를 먼저 검증했기 때문에 이미지 수를 환자 수처럼 잘못 세지 않았다.",
            style["body"],
        )
    )

    story.append(PageBreak())
    story.extend(section_title("02 · 좌우 조합", "대각선은 일치, 바깥은 불일치", style))
    story.append(chart(ROOT / "outputs/assignment1/02_bilateral_cross_matrix.png", 145 * mm))
    story.append(
        Paragraph(
            f"가장 큰 조합은 양쪽 모두 0등급인 {diagonal[0]:,}명이다. 양쪽 모두 2등급은 {diagonal[2]:,}명, "
            f"1등급은 {diagonal[1]:,}명, 3등급은 {diagonal[3]:,}명, 4등급은 {diagonal[4]:,}명이다. "
            "순서형 등급 간 거리를 반영한 QWK는 "
            f"{kappa:.4f}였다. 이 값은 두 라벨의 통계적 일치 정도이며 임상 진단 성능이 아니다.",
            style["body"],
        )
    )
    story.append(Paragraph("QWK를 함께 본 이유", style["h2"]))
    story.append(
        Paragraph(
            "0~4는 순서가 있는 등급이므로 0과 1의 차이보다 0과 4의 차이를 더 크게 반영하는 QWK를 "
            "보조 지표로 사용했다. 다만 QWK는 이 데이터 안에서 두 눈 라벨이 얼마나 비슷한지를 요약한 "
            "통계량이며, 개인의 임상적 중증도나 진단 정확도를 뜻하지 않는다.",
            style["body"],
        )
    )

    story.append(PageBreak())
    story.extend(
        section_title(
            "03 · 차이의 크기",
            f"{percentage(discordant_percentage)}는 다르고, 큰 차이는 드물다",
            style,
        )
    )
    story.append(chart(ROOT / "outputs/assignment1/03_grade_difference.png", 137 * mm))
    difference_rows = [["절대 등급 차이", "ID 수", "전체 대비"]]
    difference_rows.extend(
        [
            [str(index), f"{count:,}", percentage(count / patients)]
            for index, count in enumerate(differences)
        ]
    )
    story.append(data_table(difference_rows, [55 * mm, 55 * mm, 55 * mm]))
    story.append(
        Paragraph(
            f"등급이 다른 ID는 {discordant_count:,}명({percentage(discordant_percentage)})이고 "
            f"차이가 2 이상인 ID는 {large_gap_count:,}명({percentage(large_gap_count / patients)})이다. "
            "차이가 큰 사례도 영상 품질, 판독 변동, 데이터 오류 가능성을 배제할 수 없으므로 실제 생물학적 "
            "비대칭으로 단정하지 않는다.",
            style["body"],
        )
    )
    story.append(Paragraph("조건부 집단으로 다시 보기", style["h2"]))
    story.append(
        Paragraph(
            f"전체 집단은 양쪽 모두 0등급인 쌍이 많다. 따라서 적어도 한쪽이 1등급 이상인 {affected_patients:,}명으로 "
            "조건을 좁혀 일치율을 다시 계산했다. 이 값은 질환이 확인된 임상 환자 비율이 아니라, 제공 라벨에서 "
            "한쪽 이상이 1~4로 표시된 하위 집단의 기술통계다.",
            style["body"],
        )
    )

    chosen = _pairs(examples)
    by_gap = {record["difference"]: record for record in chosen}
    story.append(PageBreak())
    story.extend(section_title("04 · 실제 사례 I", "같은 등급과 두 단계 차이를 나란히 보기", style))
    _pair(story, by_gap[0], style)
    _pair(story, by_gap[2], style)
    story.append(
        Paragraph(
            "사례는 차이별 비교를 위한 목적 표본이며 전체 분포의 무작위 대표 표본이 아니다.",
            style["small"],
        )
    )

    story.append(PageBreak())
    story.extend(section_title("05 · 실제 사례 II", "세 단계와 네 단계 차이 사례", style))
    _pair(story, by_gap[3], style)
    _pair(story, by_gap[4], style)
    story.append(
        Paragraph(
            "사진의 원형 영역 크기나 밝기만으로 질환 등급을 해석해서는 안 된다.", style["small"]
        )
    )

    story.append(PageBreak())
    story.extend(section_title("06 · 해석과 한계", "데이터가 말하는 범위에서 결론 내리기", style))
    story.append(chart(ROOT / "outputs/assignment1/04_agreement_comparison.png", 135 * mm))
    story.append(
        Paragraph(
            f"전체 집단 일치율은 {percentage(agreement)}지만, 적어도 한쪽이 1등급 이상인 {affected_patients:,}명에서는 "
            f"{percentage(affected)}다. 핵심 결론은 ‘대부분 같다’가 아니라, 0등급 쌍의 비중을 함께 보아야 "
            "양안 관계를 올바르게 설명할 수 있다는 것이다.",
            style["body"],
        )
    )
    story.append(Paragraph("주요 한계", style["h2"]))
    story.append(
        Paragraph(
            "병변 위치·판독자·촬영 시점·나이·성별 정보가 없고 단면 자료다. 제공 ZIP이 원 Kaggle 자료와 "
            "구조적으로 일치하지만 전체 파일의 동일성을 별도 해시로 입증하지 않았다. 이 결과로 시간에 따른 "
            "진행이나 양안 차이의 원인을 추론할 수 없다.",
            style["body"],
        )
    )
    story.append(
        Paragraph(
            "재현: python -m retina.analysis trainLabels.csv outputs/assignment1", style["small"]
        )
    )
    story.append(
        Paragraph(
            "참고: Kaggle Diabetic Retinopathy Detection data / evaluation<br/>"
            "https://www.kaggle.com/c/diabetic-retinopathy-detection/data<br/>"
            "https://www.kaggle.com/competitions/diabetic-retinopathy-detection",
            style["small"],
        )
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
