from app.db.models import AnalysisImage, AnalysisSession
from app.ml.classifier import predict_multicrop_from_path
from app.services.storage_service import resolve_storage_absolute_path


def run_classification_inference(
    session: AnalysisSession,
    image_record: AnalysisImage,
) -> dict:
    if session.inference_profile is None:
        raise RuntimeError("Inference profile is not attached to the analysis session.")

    classifier_model = session.inference_profile.classifier_model
    if classifier_model is None:
        raise RuntimeError(
            f"Profile '{session.inference_profile.profile_key}' does not define classifier model."
        )

    if image_record.original_asset is None:
        raise RuntimeError(
            f"Original asset for image '{image_record.public_id}' was not found."
        )

    image_path = resolve_storage_absolute_path(image_record.original_asset.storage_path)
    if not image_path.exists():
        raise RuntimeError(
            f"Original image file does not exist on storage: {image_path}"
        )

    prediction = predict_multicrop_from_path(
        model_key=classifier_model.model_key,
        image_path=image_path,
    )

    warnings: list[str] = []
    if prediction.confidence_flag == "low":
        warnings.append("low_confidence")

    return {
        "classifier_model_id": classifier_model.id,
        "predicted_time_class": prediction.predicted_class,
        "predicted_time_confidence": prediction.confidence,
        "top2_predictions": prediction.top2_predictions,
        "confidence_flag": prediction.confidence_flag,
        "warnings": warnings,
        "inference_time_ms": prediction.inference_time_ms,
        "metrics": {
            "mean_probs": prediction.mean_probs,
            "predicted_class_index": prediction.predicted_index,
        },
    }