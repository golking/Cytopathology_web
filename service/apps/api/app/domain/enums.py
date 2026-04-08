from enum import Enum


class TaskType(str, Enum):
    TIME_CLASSIFICATION = "time_classification"
    CPE_SEGMENTATION = "cpe_segmentation"
    CPE_SCORING = "cpe_scoring"


class AnalysisSessionStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisImageStatus(str, Enum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingJobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"