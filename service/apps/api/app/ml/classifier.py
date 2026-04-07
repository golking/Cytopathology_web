import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image

from app.ml.model_registry import CLASSIFIER_MODEL_REGISTRY, ClassifierModelSpec

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict[str, Any] = {}


@dataclass
class ClassificationPrediction:
    predicted_index: int
    predicted_class: str
    confidence: float
    mean_probs: list[float]
    top2_predictions: list[dict[str, float | str]]
    confidence_flag: str
    inference_time_ms: int


def _read_image_any_format(path: str | Path) -> np.ndarray:
    """
    Читаем JPG/PNG/TIFF через PIL, переводим в grayscale,
    потом дублируем в 3 канала, как в твоём локальном коде.
    Диапазон остаётся 0..255, без нормализации.
    """
    with Image.open(path) as image:
        gray = image.convert("L")
        arr = np.asarray(gray, dtype=np.float32)  # [H, W]

    rgb = np.repeat(arr[..., None], 3, axis=-1)   # [H, W, 3]
    return rgb


def _pad_to_min_size(img: np.ndarray, min_size: int) -> np.ndarray:
    """
    Для обычных картинок используем reflect padding.
    Для очень маленьких изображений делаем fallback на edge padding,
    чтобы не падать на ограничениях reflect.
    """
    h, w = img.shape[:2]

    pad_h = max(0, min_size - h)
    pad_w = max(0, min_size - w)

    if pad_h == 0 and pad_w == 0:
        return img

    pad_spec = (
        (pad_h // 2, pad_h - pad_h // 2),
        (pad_w // 2, pad_w - pad_w // 2),
        (0, 0),
    )

    try:
        return np.pad(img, pad_spec, mode="reflect")
    except ValueError:
        return np.pad(img, pad_spec, mode="edge")


def _five_crops_from_fullres(
    img: np.ndarray,
    raw_patch_size: int,
    model_size: int,
) -> np.ndarray:
    import tensorflow as tf

    img = _pad_to_min_size(img, raw_patch_size)

    h, w = img.shape[:2]

    y0 = 0
    x0 = 0
    y1 = h - raw_patch_size
    x1 = w - raw_patch_size
    yc = (h - raw_patch_size) // 2
    xc = (w - raw_patch_size) // 2

    crops = [
        img[y0:y0 + raw_patch_size, x0:x0 + raw_patch_size, :],  # top-left
        img[y0:y0 + raw_patch_size, x1:x1 + raw_patch_size, :],  # top-right
        img[y1:y1 + raw_patch_size, x0:x0 + raw_patch_size, :],  # bottom-left
        img[y1:y1 + raw_patch_size, x1:x1 + raw_patch_size, :],  # bottom-right
        img[yc:yc + raw_patch_size, xc:xc + raw_patch_size, :],  # center
    ]

    crops = np.stack(crops, axis=0).astype(np.float32)  # [5, 1024, 1024, 3]

    crops = tf.image.resize(
        crops,
        [model_size, model_size],
        method="bilinear",
    ).numpy()  # [5, 512, 512, 3]

    return crops


def _load_model(model_key: str) -> Any:
    import tensorflow as tf

    spec = CLASSIFIER_MODEL_REGISTRY.get(model_key)
    if spec is None:
        raise KeyError(f"Classifier model key '{model_key}' is not registered.")

    if not spec.model_path.exists():
        raise FileNotFoundError(
            f"Classifier model file not found: {spec.model_path}"
        )

    logger.info("Loading classifier model '%s' from %s", model_key, spec.model_path)
    model = tf.keras.models.load_model(spec.model_path, compile=False)
    return model


def _get_model(model_key: str) -> Any:
    model = _MODEL_CACHE.get(model_key)
    if model is None:
        model = _load_model(model_key)
        _MODEL_CACHE[model_key] = model
    return model


def predict_multicrop_from_path(
    model_key: str,
    image_path: str | Path,
) -> ClassificationPrediction:
    spec: ClassifierModelSpec | None = CLASSIFIER_MODEL_REGISTRY.get(model_key)
    if spec is None:
        raise KeyError(f"Classifier model key '{model_key}' is not registered.")

    model = _get_model(model_key)

    started = perf_counter()

    img = _read_image_any_format(image_path)
    crops = _five_crops_from_fullres(
        img=img,
        raw_patch_size=spec.raw_patch_size,
        model_size=spec.model_size,
    )

    probs = model.predict(crops, verbose=0)
    probs = np.asarray(probs, dtype=np.float32)

    if probs.ndim != 2:
        raise ValueError(
            f"Unexpected classifier output shape: {probs.shape}. Expected [N, C]."
        )

    mean_probs = probs.mean(axis=0)

    if len(mean_probs) != len(spec.class_names):
        raise ValueError(
            "The number of output classes does not match class_names. "
            f"Output classes: {len(mean_probs)}, class_names: {len(spec.class_names)}"
        )

    pred_idx = int(np.argmax(mean_probs))
    predicted_class = spec.class_names[pred_idx]
    confidence = float(mean_probs[pred_idx])

    topk_idx = np.argsort(mean_probs)[::-1][: min(2, len(mean_probs))]
    top2_predictions = [
        {
            "predicted_class": spec.class_names[int(idx)],
            "confidence": float(mean_probs[int(idx)]),
        }
        for idx in topk_idx
    ]

    confidence_flag = (
        "low"
        if confidence < spec.low_confidence_threshold
        else "normal"
    )

    inference_time_ms = int((perf_counter() - started) * 1000)

    return ClassificationPrediction(
        predicted_index=pred_idx,
        predicted_class=predicted_class,
        confidence=confidence,
        mean_probs=[float(x) for x in mean_probs.tolist()],
        top2_predictions=top2_predictions,
        confidence_flag=confidence_flag,
        inference_time_ms=inference_time_ms,
    )