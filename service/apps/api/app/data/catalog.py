
CATALOG_VIRUSES = [
    {
        "id": 1,
        "code": "rsv",
        "name": "Respiratory syncytial virus",
    },
]

CATALOG_CELL_LINES = [
    {
        "id": 1,
        "code": "hep2",
        "name": "HEp-2",
    },
    {
        "id": 2,
        "code": "A549",
        "name": "A549",
    }
]

CATALOG_PROFILES = [
    {
        "profile_key": "RSV_hep2_cls",
        "virus_code": "rsv",
        "cell_line_code": "hep2",
        "classifier_model_key": "RSV_hep2_cls.keras",
        "segmenter_model_key": None,
        "scorer_model_key": None,
        "is_default": True,
    },
    {
        "profile_key": "RSV_A549_cls",
        "virus_code": "rsv",
        "cell_line_code": "A549",
        "classifier_model_key": "RSV_A549_cls.keras",
        "segmenter_model_key": None,
        "scorer_model_key": None,
        "is_default": True,
    }
]

