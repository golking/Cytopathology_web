from dataclasses import dataclass
from pathlib import Path

from app.core.config import BASE_DIR


@dataclass(frozen=True)
class ClassifierModelSpec:
    model_key: str
    model_path: Path
    class_names: tuple[str, ...]
    model_size: int = 512
    raw_patch_size: int = 1024
    low_confidence_threshold: float = 0.60


CLASSIFIER_MODEL_REGISTRY: dict[str, ClassifierModelSpec] = {
    "RSV_hep2_cls.keras": ClassifierModelSpec(
        model_key="RSV_hep2_cls.keras",
        model_path=BASE_DIR / "models" / "RSV_hep2_cls.keras",
        class_names=("24h", "48h", "72h", "control"),
        model_size=512,
        raw_patch_size=1024,
        low_confidence_threshold=0.60,
    ),
    "RSV_A549_cls.keras": ClassifierModelSpec(
        model_key="RSV_A549_cls.keras",
        model_path=BASE_DIR / "models" / "RSV_A549_cls.keras",
        class_names=("24h", "48h", "72h", "control"),
        model_size=512,
        raw_patch_size=1024,
        low_confidence_threshold=0.60,
    )
}