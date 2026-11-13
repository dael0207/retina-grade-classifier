from collections.abc import Callable
from typing import ClassVar

from PIL import Image
from torch import Tensor
from torch import nn

class MobileNetV3(nn.Module):
    features: nn.Sequential
    avgpool: nn.AdaptiveAvgPool2d
    classifier: nn.Sequential

class MobileNet_V3_Small_Weights:
    DEFAULT: ClassVar[MobileNet_V3_Small_Weights]
    name: str
    url: str
    def transforms(self) -> Callable[[Image.Image], Tensor]: ...

def mobilenet_v3_small(
    *, weights: MobileNet_V3_Small_Weights | None = ...
) -> MobileNetV3: ...
