class FitResult:
    coefficients: tuple[tuple[float, ...], ...]
    intercepts: tuple[float, ...]
    classes: tuple[int, ...]
    feature_mean: tuple[float, ...]
    feature_scale: tuple[float, ...]

def fit_logistic(
    features: tuple[tuple[float, ...], ...],
    labels: tuple[int, ...],
    *,
    balanced: bool,
    seed: int,
) -> FitResult: ...
