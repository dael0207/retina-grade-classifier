from retina.export_examples import PredictionRow, select_example_rows


def test_select_examples_returns_only_correct_when_every_prediction_is_correct() -> None:
    # Given
    rows = [PredictionRow("a", 0, 0), PredictionRow("b", 2, 2)]

    # When
    selected = select_example_rows(rows)

    # Then
    assert [(item.kind, item.row.image) for item in selected] == [("correct", "a")]


def test_select_examples_returns_only_incorrect_when_every_prediction_is_incorrect() -> None:
    # Given
    rows = [PredictionRow("a", 0, 1), PredictionRow("b", 2, 3)]

    # When
    selected = select_example_rows(rows)

    # Then
    assert [(item.kind, item.row.image) for item in selected] == [("incorrect", "a")]
