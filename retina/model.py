"""Safe model artifact and MobileNetV3 feature inference."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, ClassVar, TypedDict, final

from PIL import Image
from pydantic import BaseModel, ConfigDict

from model_runtime.artifacts import ArtifactData, load_artifact, save_artifact
from model_runtime.vision import VisionRuntime
from retina.imaging import prepare_image
from retina.sensitivity import SensitivityResult, build_occlusion_sensitivity

if TYPE_CHECKING:
    from pathlib import Path

    from model_runtime.vision import TensorView

FloatVector = tuple[float, ...]
FloatMatrix = tuple[FloatVector, ...]
IntVector = tuple[int, ...]
MODEL_FORMAT_VERSION = 1
EXTRACTOR_NAME = "torchvision-mobilenet-v3-small-default-classifier-2"
GRADE_COUNT = 5


class PredictionJson(TypedDict):
    """Public JSON schema consumed by the web application."""

    grade: int
    scores: list[float]


class BackboneProvenance(TypedDict):
    """Recorded origin and digest for the offline pretrained backbone."""

    architecture: str
    weight: str
    source_url: str
    sha256: str


class BackboneProvenanceModel(BaseModel):
    """Strict parser for the backbone provenance trust boundary."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    architecture: str
    weight: str
    source_url: str
    sha256: str


@dataclass(frozen=True, slots=True)
class BatchPrediction:
    """Predicted grades and five-grade score rows."""

    grades: IntVector
    scores: FloatMatrix


@dataclass(frozen=True, slots=True)
class ImagePrediction:
    """Prediction for one image with scores aligned to grades zero through four."""

    grade: int
    scores: tuple[float, float, float, float, float]

    def to_json(self) -> PredictionJson:
        """Convert the prediction into the stable API schema."""
        return {"grade": self.grade, "scores": list(self.scores)}


@dataclass(frozen=True, slots=True)
class LinearClassifier:
    """Standardized multinomial linear head stored without executable pickle data."""

    coefficients: FloatMatrix
    intercepts: FloatVector
    classes: IntVector
    feature_mean: FloatVector
    feature_scale: FloatVector

    def __post_init__(self) -> None:
        """Reject incompatible classifier value layouts."""
        if not self.coefficients or not self.coefficients[0]:
            msg = "classifier coefficients must be a non-empty matrix"
            raise ValueError(msg)
        feature_count = len(self.coefficients[0])
        valid = (
            all(len(row) == feature_count for row in self.coefficients)
            and len(self.intercepts) == len(self.coefficients)
            and len(self.classes) == len(self.coefficients)
            and len(self.feature_mean) == feature_count
            and len(self.feature_scale) == feature_count
            and all(value > 0 for value in self.feature_scale)
            and all(0 <= grade < GRADE_COUNT for grade in self.classes)
        )
        if not valid:
            msg = "incompatible linear classifier values"
            raise ValueError(msg)

    def predict(self, features: FloatMatrix) -> BatchPrediction:
        """Predict five-grade scores from a feature matrix."""
        feature_count = len(self.feature_mean)
        if any(len(row) != feature_count for row in features):
            msg = "feature matrix has an incompatible shape"
            raise ValueError(msg)
        score_rows = tuple(self._predict_row(row) for row in features)
        grades = tuple(max(range(GRADE_COUNT), key=row.__getitem__) for row in score_rows)
        return BatchPrediction(grades=grades, scores=score_rows)

    def _predict_row(self, row: FloatVector) -> FloatVector:
        standardized = tuple(
            (value - mean) / scale
            for value, mean, scale in zip(row, self.feature_mean, self.feature_scale, strict=True)
        )
        logits = tuple(
            sum(weight * value for weight, value in zip(weights, standardized, strict=True))
            + intercept
            for weights, intercept in zip(self.coefficients, self.intercepts, strict=True)
        )
        maximum = max(logits)
        exponentials = tuple(math.exp(value - maximum) for value in logits)
        denominator = sum(exponentials)
        class_probabilities = tuple(value / denominator for value in exponentials)
        scores = [0.0] * GRADE_COUNT
        for grade, probability in zip(self.classes, class_probabilities, strict=True):
            scores[grade] = probability
        return tuple(scores)


@lru_cache(maxsize=1)
def _official_runtime() -> VisionRuntime:
    return VisionRuntime.official("cpu")


def preprocessing_tensor(image: Image.Image) -> TensorView:
    """Apply canonical retina preparation and official weight transforms."""
    return _official_runtime().preprocess(prepare_image(image))


@final
class MobileNetEmbedder:
    """Frozen ImageNet MobileNetV3-small feature extractor."""

    def __init__(self, *, device: str = "cpu", backbone_path: Path | None = None) -> None:
        """Load official or verified local pretrained weights."""
        if backbone_path is None:
            self._runtime = VisionRuntime.official(device)
        else:
            _verify_backbone(backbone_path)
            self._runtime = VisionRuntime.local(backbone_path, device)

    @staticmethod
    def configure_threads(count: int) -> None:
        """Configure the underlying CPU thread pool."""
        VisionRuntime.configure_threads(count)

    def embed_images(self, images: list[Image.Image]) -> FloatMatrix:
        """Extract embeddings from in-memory source images."""
        return self.embed_prepared_images([prepare_image(image) for image in images])

    def embed_prepared_images(self, images: list[Image.Image]) -> FloatMatrix:
        """Extract embeddings from images already prepared to the canonical square."""
        return self._runtime.embed_prepared(images)

    def embed_paths(self, paths: list[Path], *, batch_size: int = 16) -> FloatMatrix:
        """Read paths in bounded batches and extract embeddings."""
        chunks: list[FloatVector] = []
        for start in range(0, len(paths), batch_size):
            images: list[Image.Image] = []
            for path in paths[start : start + batch_size]:
                with Image.open(path) as image:
                    images.append(image.convert("RGB"))
            chunks.extend(self.embed_images(images))
        return tuple(chunks)

    def save_backbone(self, destination: Path) -> BackboneProvenance:
        """Save official weights locally and return reproducibility metadata."""
        self._runtime.save_backbone(destination)
        return {
            "architecture": "mobilenet_v3_small",
            "weight": self._runtime.weight_name,
            "source_url": self._runtime.source_url,
            "sha256": _sha256(destination),
        }


def save_model(classifier: LinearClassifier, destination: Path) -> None:
    """Save inert numeric arrays in a compressed NPZ artifact."""
    save_artifact(
        destination,
        ArtifactData(
            MODEL_FORMAT_VERSION,
            EXTRACTOR_NAME,
            classifier.coefficients,
            classifier.intercepts,
            classifier.classes,
            classifier.feature_mean,
            classifier.feature_scale,
        ),
    )


def load_model(source: Path) -> LinearClassifier:
    """Load and validate an inert NPZ classifier artifact."""
    artifact = load_artifact(source)
    if artifact.format_version != MODEL_FORMAT_VERSION or artifact.extractor != EXTRACTOR_NAME:
        msg = "unsupported model artifact format"
        raise ValueError(msg)
    return LinearClassifier(
        artifact.coefficients,
        artifact.intercepts,
        artifact.classes,
        artifact.feature_mean,
        artifact.feature_scale,
    )


def _sha256(source: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_backbone(source: Path) -> None:
    provenance_path = source.with_name("backbone_provenance.json")
    if not provenance_path.is_file():
        msg = f"missing backbone provenance: {provenance_path}"
        raise FileNotFoundError(msg)
    provenance = BackboneProvenanceModel.model_validate_json(
        provenance_path.read_text(encoding="utf-8")
    )
    if _sha256(source) != provenance.sha256:
        msg = "backbone SHA-256 verification failed"
        raise ValueError(msg)


@lru_cache(maxsize=2)
def _cached_embedder(backbone_path: Path) -> MobileNetEmbedder:
    return MobileNetEmbedder(device="cpu", backbone_path=backbone_path)


def predict_image(image: Image.Image, artifact_path: Path) -> ImagePrediction:
    """Predict one image with the cached frozen feature extractor."""
    classifier = load_model(artifact_path)
    result = classifier.predict(
        _cached_embedder(artifact_path.with_name("backbone.pth")).embed_images([image])
    )
    row = result.scores[0]
    return ImagePrediction(
        grade=result.grades[0],
        scores=(row[0], row[1], row[2], row[3], row[4]),
    )


def occlusion_sensitivity(
    image: Image.Image,
    artifact_path: Path,
    *,
    grid_size: int = 4,
) -> SensitivityResult:
    """Measure score changes for grid occlusion without a second preprocessing pass."""
    classifier = load_model(artifact_path)
    embedder = _cached_embedder(artifact_path.with_name("backbone.pth"))
    return build_occlusion_sensitivity(image, classifier, embedder, grid_size=grid_size)
