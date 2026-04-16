from hashlib import sha256
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR
from app.data.catalog import CATALOG_CELL_LINES, CATALOG_PROFILES, CATALOG_VIRUSES
from app.db.models import CellLine, InferenceProfile, Model, Virus
from app.ml.model_registry import CLASSIFIER_MODEL_REGISTRY


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_storage_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(BASE_DIR.resolve()))
    except ValueError:
        return str(path.resolve())


def seed_reference_data(db: Session) -> dict[str, int]:
    viruses_by_code: dict[str, Virus] = {}
    cell_lines_by_code: dict[str, CellLine] = {}
    models_by_key: dict[str, Model] = {}

    for item in CATALOG_VIRUSES:
        virus = db.scalar(select(Virus).where(Virus.code == item["code"]))
        if virus is None:
            virus = Virus(
                code=item["code"],
                name=item["name"],
            )
            db.add(virus)

        virus.name = item["name"]
        virus.description = item.get("description")
        virus.is_active = bool(item.get("is_active", True))
        viruses_by_code[item["code"]] = virus

    db.flush()

    for item in CATALOG_CELL_LINES:
        cell_line = db.scalar(select(CellLine).where(CellLine.code == item["code"]))
        if cell_line is None:
            cell_line = CellLine(
                code=item["code"],
                name=item["name"],
            )
            db.add(cell_line)

        cell_line.name = item["name"]
        cell_line.species = item.get("species")
        cell_line.description = item.get("description")
        cell_line.is_active = bool(item.get("is_active", True))
        cell_lines_by_code[item["code"]] = cell_line

    db.flush()

    for model_key, spec in CLASSIFIER_MODEL_REGISTRY.items():
        if not spec.model_path.exists():
            raise FileNotFoundError(
                f"Model file for '{model_key}' was not found: {spec.model_path}"
            )

        model = db.scalar(select(Model).where(Model.model_key == model_key))
        if model is None:
            model = Model(
                model_key=model_key,
                task_type="time_classification",
                name=spec.model_path.stem,
                version="1.0.0",
                framework="tensorflow",
                storage_path=_relative_storage_path(spec.model_path),
                input_width=spec.model_size,
                input_height=spec.model_size,
                input_channels=3,
            )
            db.add(model)

        model.task_type = "time_classification"
        model.name = spec.model_path.stem
        model.version = "1.0.0"
        model.framework = "tensorflow"
        model.storage_path = _relative_storage_path(spec.model_path)
        model.checksum = _sha256_file(spec.model_path)
        model.input_width = spec.model_size
        model.input_height = spec.model_size
        model.input_channels = 3
        model.preprocessing_config = {
            "reader": "pil_grayscale_to_rgb",
            "input_value_range": [0, 255],
            "raw_patch_size": spec.raw_patch_size,
            "crop_strategy": "five_crops_tl_tr_bl_br_center",
            "resize": {
                "width": spec.model_size,
                "height": spec.model_size,
                "method": "bilinear",
            },
            "channel_policy": "grayscale_to_rgb",
        }
        model.postprocessing_config = {
            "class_names": list(spec.class_names),
            "aggregation": "mean_probs",
            "top_k": 2,
        }
        model.confidence_threshold = float(spec.low_confidence_threshold)
        model.is_active = True

        models_by_key[model_key] = model

    db.flush()

    for item in CATALOG_PROFILES:
        profile = db.scalar(
            select(InferenceProfile).where(
                InferenceProfile.profile_key == item["profile_key"]
            )
        )
        if profile is None:
            profile = InferenceProfile(
                profile_key=item["profile_key"],
                name=item.get("name") or item["profile_key"],
                virus_id=viruses_by_code[item["virus_code"]].id,
                cell_line_id=cell_lines_by_code[item["cell_line_code"]].id,
            )
            db.add(profile)

        classifier_model_id = None
        if item.get("classifier_model_key") is not None:
            classifier_model_id = models_by_key[item["classifier_model_key"]].id

        segmenter_model_id = None
        if item.get("segmenter_model_key") is not None:
            segmenter_model_id = models_by_key[item["segmenter_model_key"]].id

        scorer_model_id = None
        if item.get("scorer_model_key") is not None:
            scorer_model_id = models_by_key[item["scorer_model_key"]].id

        profile.name = item.get("name") or item["profile_key"]
        profile.virus_id = viruses_by_code[item["virus_code"]].id
        profile.cell_line_id = cell_lines_by_code[item["cell_line_code"]].id
        profile.classifier_model_id = classifier_model_id
        profile.segmenter_model_id = segmenter_model_id
        profile.scorer_model_id = scorer_model_id
        profile.is_default = bool(item.get("is_default", False))
        profile.is_active = bool(item.get("is_active", True))

    db.flush()

    return {
        "viruses": len(viruses_by_code),
        "cell_lines": len(cell_lines_by_code),
        "models": len(models_by_key),
        "profiles": len(CATALOG_PROFILES),
    }