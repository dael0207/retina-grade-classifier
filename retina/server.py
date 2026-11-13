"""Local FastAPI surface for the two diabetic-retinopathy assignments."""

from __future__ import annotations

import base64
import io
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Final, override

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from retina.evidence_api import add_evidence_routes

PROJECT_ROOT: Final = Path(__file__).resolve().parents[1]
MAX_UPLOAD_BYTES: Final = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES: Final = frozenset({"image/jpeg", "image/png"})


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Filesystem contract for generated analysis, model, and web assets."""

    root: Path
    web: Path
    assignment1: Path
    assignment2: Path
    analysis_summary: Path
    examples: Path
    model_metrics: Path
    model_artifact: Path
    images: Path
    figures: Path

    @classmethod
    def from_root(cls, root: Path) -> AppPaths:
        """Resolve every application path from one project root."""
        assignment1 = root / "outputs" / "assignment1"
        assignment2 = root / "outputs" / "assignment2"
        return cls(
            root=root,
            web=root / "web",
            assignment1=assignment1,
            assignment2=assignment2,
            analysis_summary=assignment1 / "summary.json",
            examples=assignment1 / "examples.json",
            model_metrics=assignment2 / "metrics.json",
            model_artifact=assignment2 / "model.npz",
            images=root / "data" / "images",
            figures=assignment1,
        )


class PredictionResponse(BaseModel):
    """Five-grade model output returned to the local browser."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    grade: int = Field(ge=0, le=4)
    scores: list[float] = Field(min_length=5, max_length=5)
    sensitivity_image: str | None = None


@dataclass(frozen=True, slots=True)
class ModelUnavailableError(Exception):
    """Raised when prediction is requested before training finishes."""

    artifact_path: Path

    @override
    def __str__(self) -> str:
        """Describe the missing artifact for local diagnostics."""
        return f"model artifact is unavailable: {self.artifact_path}"


Predictor = Callable[[Image.Image], PredictionResponse]


def _default_predictor(paths: AppPaths) -> Predictor:
    """Build the adapter only when the first valid prediction is requested."""

    def predict(image: Image.Image) -> PredictionResponse:
        if not paths.model_artifact.is_file():
            raise ModelUnavailableError(artifact_path=paths.model_artifact)
        from retina.model import (  # noqa: PLC0415 - preserves lazy GPU/model load
            occlusion_sensitivity,
            predict_image,
        )

        result = predict_image(image, artifact_path=paths.model_artifact)
        sensitivity = occlusion_sensitivity(image, artifact_path=paths.model_artifact)
        with io.BytesIO() as stream:
            sensitivity.overlay.save(stream, format="PNG")
            encoded = base64.b64encode(stream.getvalue()).decode("ascii")
        payload = result.to_json()
        return PredictionResponse(
            grade=payload["grade"],
            scores=payload["scores"],
            sensitivity_image=f"data:image/png;base64,{encoded}",
        )

    return predict


def _json_file_response(path: Path, label: str) -> Response:
    if not path.is_file():
        detail = f"{label}가 아직 생성되지 않았습니다. 생성 단계를 먼저 실행해 주세요."
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
    raw = path.read_text(encoding="utf-8")
    return Response(content=raw, media_type="application/json")


async def _read_upload(request: Request) -> bytes:
    content_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0]
    if content_type not in ALLOWED_IMAGE_TYPES:
        detail = "JPEG 또는 PNG 이미지 파일만 분석할 수 있습니다."
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=detail)

    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > MAX_UPLOAD_BYTES:
            detail = "이미지 크기는 10MB 이하여야 합니다."
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=detail)
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="이미지 파일이 비어 있습니다.")
    return bytes(payload)


def _decode_image(payload: bytes) -> Image.Image:
    try:
        with Image.open(io.BytesIO(payload)) as candidate:
            candidate.verify()
        with Image.open(io.BytesIO(payload)) as verified:
            return verified.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        detail = "올바른 JPEG 또는 PNG 이미지인지 확인해 주세요."
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=detail) from error


def create_app(
    paths: AppPaths | None = None,
    predictor: Predictor | None = None,
) -> FastAPI:
    """Create the local-only application with injectable paths and predictor."""
    resolved_paths = paths or AppPaths.from_root(PROJECT_ROOT)
    resolved_predictor = predictor or _default_predictor(resolved_paths)
    app = FastAPI(
        title="Retina Pair Lab",
        description="당뇨망막병증 데이터 교육용 분석 프로젝트",
        docs_url=None,
        redoc_url=None,
    )

    app.mount(
        "/assets",
        StaticFiles(directory=resolved_paths.web, check_dir=False),
        name="assets",
    )
    app.mount(
        "/images",
        StaticFiles(directory=resolved_paths.images, check_dir=False),
        name="images",
    )
    app.mount(
        "/figures",
        StaticFiles(directory=resolved_paths.figures, check_dir=False),
        name="figures",
    )

    def get_index() -> FileResponse:
        return FileResponse(resolved_paths.web / "index.html")

    def get_showcase() -> FileResponse:
        return FileResponse(resolved_paths.web / "showcase.html")

    def get_analysis() -> Response:
        return _json_file_response(resolved_paths.analysis_summary, "분석 결과")

    def get_examples() -> Response:
        return _json_file_response(resolved_paths.examples, "양안 사례")

    def get_model_metrics() -> Response:
        return _json_file_response(resolved_paths.model_metrics, "모델 평가 결과")

    async def post_predict(request: Request) -> PredictionResponse:
        payload = await _read_upload(request)
        image = await run_in_threadpool(_decode_image, payload)
        try:
            return await run_in_threadpool(resolved_predictor, image)
        except ModelUnavailableError as error:
            detail = "학습된 모델이 아직 준비되지 않았습니다. 모델 학습 단계를 먼저 실행해 주세요."
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=detail,
            ) from error

    app.add_api_route("/", get_index, methods=["GET"], include_in_schema=False)
    app.add_api_route("/showcase", get_showcase, methods=["GET"], include_in_schema=False)
    app.add_api_route("/api/analysis", get_analysis, methods=["GET"], response_class=Response)
    app.add_api_route("/api/examples", get_examples, methods=["GET"], response_class=Response)
    app.add_api_route(
        "/api/model-metrics",
        get_model_metrics,
        methods=["GET"],
        response_class=Response,
    )
    app.add_api_route(
        "/api/predict",
        post_predict,
        methods=["POST"],
        response_model=PredictionResponse,
    )

    add_evidence_routes(app, resolved_paths.root)
    return app


app = create_app()
