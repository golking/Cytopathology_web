from app.data.asset_store import ASSET_STORE
from app.ml.classifier import predict_multicrop_from_path
from app.services.catalog_service import get_profile_record_by_key


def run_classification_inference(session: dict, image_record: dict) -> dict:
    profile_record = get_profile_record_by_key(session["profile_key"])
    if profile_record is None:
        raise RuntimeError(
            f"Profile '{session['profile_key']}' was not found."
        )

    model_key = profile_record.get("classifier_model_key")
    if not model_key:
        raise RuntimeError(
            f"Profile '{session['profile_key']}' does not define classifier_model_key."
        )

    original_asset_id = image_record.get("original_asset_id")
    asset_record = ASSET_STORE.get(original_asset_id)
    if asset_record is None:
        raise RuntimeError(
            f"Original asset '{original_asset_id}' was not found."
        )

    prediction = predict_multicrop_from_path(
        model_key=model_key,
        image_path=asset_record["absolute_path"],
    )

    warnings: list[str] = []
    if prediction.confidence_flag == "low":
        warnings.append("low_confidence")

    return {
        "predicted_time_class": prediction.predicted_class,
        "predicted_time_confidence": prediction.confidence,
        "top2_predictions": prediction.top2_predictions,
        "confidence_flag": prediction.confidence_flag,
        "warnings": warnings,
        "inference_time_ms": prediction.inference_time_ms,
        "predicted_time_class_index": prediction.predicted_index,
        "mean_probs": prediction.mean_probs,
        "model_key": model_key,
    }