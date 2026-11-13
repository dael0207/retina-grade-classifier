"""Torchvision execution isolated behind a small typed interface."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, final, override

import torch
from torch import nn
from torchvision.models import MobileNet_V3_Small_Weights, MobileNetV3, mobilenet_v3_small

if TYPE_CHECKING:
    from pathlib import Path

    from PIL import Image


class WeightLoader(Protocol):
    """Typed surface used for verified tensor-only state dictionaries."""

    def __call__(
        self,
        f: Path,
        *,
        map_location: str,
        weights_only: Literal[True],
    ) -> dict[str, torch.Tensor]:
        """Load a verified tensor-only state dictionary."""
        ...


load_weights: WeightLoader = torch.load


class TensorTransform(Protocol):
    """Typed callable contract supplied by torch sequential modules."""

    def __call__(self, inputs: torch.Tensor) -> torch.Tensor:
        """Apply the tensor transform."""
        ...


@final
class FeatureModel(nn.Module):
    """Typed MobileNet feature path ending at the penultimate classifier layer."""

    def __init__(self, base: MobileNetV3) -> None:
        """Build the penultimate MobileNet feature path."""
        super().__init__()
        self._layers: TensorTransform = nn.Sequential(
            base.features,
            base.avgpool,
            nn.Flatten(start_dim=1),
            *list(base.classifier.children())[:3],
        )

    @override
    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        """Compute one embedding row per input image."""
        return self._layers(inputs)


@final
class VisionRuntime:
    """Typed runtime adapter around torchvision MobileNet inference."""

    def __init__(self, base: MobileNetV3, device: str) -> None:
        """Bind the backbone and feature path to a device."""
        self._backbone = base
        self._model = FeatureModel(base).eval().to(device)
        self._device = torch.device(device)

    @classmethod
    def official(cls, device: str) -> VisionRuntime:
        """Load the official default pretrained backbone."""
        return cls(mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT), device)

    @staticmethod
    def configure_threads(count: int) -> None:
        """Set torch's CPU worker count."""
        torch.set_num_threads(count)

    @classmethod
    def local(cls, path: Path, device: str) -> VisionRuntime:
        """Load a local tensor-only state dictionary."""
        base = mobilenet_v3_small(weights=None)
        state = load_weights(path, map_location=device, weights_only=True)
        _ = base.load_state_dict(state)
        return cls(base, device)

    def preprocess(self, prepared: Image.Image) -> torch.Tensor:
        """Apply the official transform to a prepared image."""
        return MobileNet_V3_Small_Weights.DEFAULT.transforms()(prepared)

    @torch.inference_mode()
    def embed_prepared(self, images: list[Image.Image]) -> tuple[tuple[float, ...], ...]:
        """Extract immutable feature rows from prepared images."""
        if not images:
            return ()
        batch = torch.stack([self.preprocess(image) for image in images]).to(self._device)
        values = self._model.forward(batch).cpu()
        return tuple(
            tuple(float(values[row, column]) for column in range(values.shape[1]))
            for row in range(values.shape[0])
        )

    def save_backbone(self, path: Path) -> None:
        """Persist the tensor-only backbone state dictionary."""
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self._backbone.state_dict(), path)

    @property
    def weight_name(self) -> str:
        """Return the official torchvision weight identifier."""
        return MobileNet_V3_Small_Weights.DEFAULT.name

    @property
    def source_url(self) -> str:
        """Return the official torchvision download URL."""
        return MobileNet_V3_Small_Weights.DEFAULT.url
