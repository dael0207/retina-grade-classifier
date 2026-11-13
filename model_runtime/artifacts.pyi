from pathlib import Path

class ArtifactData:
    format_version: int
    extractor: str
    coefficients: tuple[tuple[float, ...], ...]
    intercepts: tuple[float, ...]
    classes: tuple[int, ...]
    feature_mean: tuple[float, ...]
    feature_scale: tuple[float, ...]
    def __init__(
        self,
        format_version: int,
        extractor: str,
        coefficients: tuple[tuple[float, ...], ...],
        intercepts: tuple[float, ...],
        classes: tuple[int, ...],
        feature_mean: tuple[float, ...],
        feature_scale: tuple[float, ...],
    ) -> None: ...

def save_artifact(path: Path, data: ArtifactData) -> None: ...
def load_artifact(path: Path) -> ArtifactData: ...
