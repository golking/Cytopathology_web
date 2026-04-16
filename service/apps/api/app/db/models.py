from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


UUID_DEFAULT = text("gen_random_uuid()")
EMPTY_OBJECT_JSONB = text("'{}'::jsonb")
EMPTY_ARRAY_JSONB = text("'[]'::jsonb")


class BigIntPkMixin:
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )


class PublicIdMixin:
    public_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        unique=True,
        server_default=UUID_DEFAULT,
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Virus(BigIntPkMixin, CreatedAtMixin, Base):
    __tablename__ = "viruses"
    __table_args__ = (
        CheckConstraint(
            "code ~ '^[a-z0-9_]+$'",
            name="code_format",
        ),
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )


class CellLine(BigIntPkMixin, CreatedAtMixin, Base):
    __tablename__ = "cell_lines"
    __table_args__ = (
        CheckConstraint(
            "code ~ '^[A-Za-z0-9_\\-]+$'",
            name="code_format",
        ),
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    species: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )


class Model(BigIntPkMixin, CreatedAtMixin, Base):
    __tablename__ = "models"
    __table_args__ = (
        CheckConstraint(
            "task_type IN ('time_classification','cpe_segmentation','cpe_scoring')",
            name="task_type_allowed",
        ),
        CheckConstraint("input_width > 0", name="input_width_positive"),
        CheckConstraint("input_height > 0", name="input_height_positive"),
        CheckConstraint("input_channels IN (1,3)", name="input_channels_allowed"),
        CheckConstraint(
            "confidence_threshold IS NULL OR "
            "(confidence_threshold >= 0 AND confidence_threshold <= 1)",
            name="confidence_threshold_between_0_1",
        ),
        UniqueConstraint(
            "task_type",
            "name",
            "version",
            name="uq_models_task_type_name_version",
        ),
        Index("ix_models_task_type_is_active", "task_type", "is_active"),
    )

    model_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    framework: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'pytorch'"),
    )
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    input_width: Mapped[int] = mapped_column(Integer, nullable=False)
    input_height: Mapped[int] = mapped_column(Integer, nullable=False)
    input_channels: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    preprocessing_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=EMPTY_OBJECT_JSONB,
    )
    postprocessing_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=EMPTY_OBJECT_JSONB,
    )
    confidence_threshold: Mapped[float | None] = mapped_column(
        Numeric(4, 3),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )


class InferenceProfile(BigIntPkMixin, CreatedAtMixin, Base):
    __tablename__ = "inference_profiles"
    __table_args__ = (
        CheckConstraint(
            "(classifier_model_id IS NOT NULL "
            "OR segmenter_model_id IS NOT NULL "
            "OR scorer_model_id IS NOT NULL)",
            name="has_any_model",
        ),
        Index(
            "ix_inference_profiles_virus_cell_line_is_active",
            "virus_id",
            "cell_line_id",
            "is_active",
        ),
        Index(
            "ux_inference_profiles_default_pair",
            "virus_id",
            "cell_line_id",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
    )

    profile_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    virus_id: Mapped[int] = mapped_column(
        ForeignKey("viruses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cell_line_id: Mapped[int] = mapped_column(
        ForeignKey("cell_lines.id", ondelete="RESTRICT"),
        nullable=False,
    )

    classifier_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("models.id", ondelete="RESTRICT"),
        nullable=True,
    )
    segmenter_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("models.id", ondelete="RESTRICT"),
        nullable=True,
    )
    scorer_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("models.id", ondelete="RESTRICT"),
        nullable=True,
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    virus: Mapped["Virus"] = relationship("Virus")
    cell_line: Mapped["CellLine"] = relationship("CellLine")
    classifier_model: Mapped["Model | None"] = relationship(
        "Model",
        foreign_keys=[classifier_model_id],
    )
    segmenter_model: Mapped["Model | None"] = relationship(
        "Model",
        foreign_keys=[segmenter_model_id],
    )
    scorer_model: Mapped["Model | None"] = relationship(
        "Model",
        foreign_keys=[scorer_model_id],
    )


class User(BigIntPkMixin, PublicIdMixin, CreatedAtMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('researcher','admin')",
            name="role_allowed",
        ),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'researcher'"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class FileAsset(BigIntPkMixin, PublicIdMixin, CreatedAtMixin, Base):
    __tablename__ = "file_assets"
    __table_args__ = (
        CheckConstraint(
            "asset_type IN "
            "('original_image','preprocessed_image','mask','overlay','heatmap','report')",
            name="asset_type_allowed",
        ),
        CheckConstraint(
            "storage_backend IN ('fs','s3')",
            name="storage_backend_allowed",
        ),
        CheckConstraint("size_bytes >= 0", name="size_bytes_non_negative"),
        CheckConstraint(
            "width IS NULL OR width > 0",
            name="width_positive_or_null",
        ),
        CheckConstraint(
            "height IS NULL OR height > 0",
            name="height_positive_or_null",
        ),
        Index("ix_file_assets_asset_type_created_at", "asset_type", "created_at"),
        Index("ix_file_assets_checksum", "checksum"),
    )

    asset_type: Mapped[str] = mapped_column(String(30), nullable=False)
    storage_backend: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'fs'"),
    )
    storage_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class AnalysisSession(BigIntPkMixin, PublicIdMixin, CreatedAtMixin, Base):
    __tablename__ = "analysis_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created','queued','processing','completed','failed','cancelled')",
            name="status_allowed",
        ),
        CheckConstraint("images_count >= 0", name="images_count_non_negative"),
        CheckConstraint(
            "completed_images_count >= 0",
            name="completed_images_count_non_negative",
        ),
        CheckConstraint(
            "failed_images_count >= 0",
            name="failed_images_count_non_negative",
        ),
        CheckConstraint(
            "completed_images_count + failed_images_count <= images_count",
            name="finished_counts_lte_images_count",
        ),
        Index("ix_analysis_sessions_status_created_at", "status", "created_at"),
        Index("ix_analysis_sessions_user_created_at", "user_id", "created_at"),
        Index(
            "ix_analysis_sessions_virus_cell_line_created_at",
            "virus_id",
            "cell_line_id",
            "created_at",
        ),
        Index(
            "ix_analysis_sessions_client_token_created_at",
            "client_token",
            "created_at",
        ),
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    client_token: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )
    virus_id: Mapped[int] = mapped_column(
        ForeignKey("viruses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cell_line_id: Mapped[int] = mapped_column(
        ForeignKey("cell_lines.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inference_profile_id: Mapped[int] = mapped_column(
        ForeignKey("inference_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False)
    images_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    completed_images_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    failed_images_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    summary_metrics: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User | None"] = relationship("User")
    virus: Mapped["Virus"] = relationship("Virus")
    cell_line: Mapped["CellLine"] = relationship("CellLine")
    inference_profile: Mapped["InferenceProfile"] = relationship("InferenceProfile")

    images: Mapped[list["AnalysisImage"]] = relationship(
        "AnalysisImage",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    processing_job: Mapped["ProcessingJob | None"] = relationship(
        "ProcessingJob",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def queued_at(self) -> datetime | None:
        if self.processing_job is None:
            return None
        return self.processing_job.created_at


class AnalysisImage(BigIntPkMixin, PublicIdMixin, CreatedAtMixin, Base):
    __tablename__ = "analysis_images"
    __table_args__ = (
        CheckConstraint("image_index > 0", name="image_index_positive"),
        CheckConstraint(
            "width IS NULL OR width > 0",
            name="width_positive_or_null",
        ),
        CheckConstraint(
            "height IS NULL OR height > 0",
            name="height_positive_or_null",
        ),
        CheckConstraint(
            "channels IS NULL OR channels BETWEEN 1 AND 4",
            name="channels_between_1_4_or_null",
        ),
        CheckConstraint(
            "status IN ('uploaded','queued','processing','completed','failed')",
            name="status_allowed",
        ),
        UniqueConstraint(
            "session_id",
            "image_index",
            name="uq_analysis_images_session_image_index",
        ),
        Index("ix_analysis_images_session_status", "session_id", "status"),
        Index("ix_analysis_images_checksum", "checksum"),
    )

    session_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_index: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    checksum: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    original_asset_id: Mapped[int] = mapped_column(
        ForeignKey("file_assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    preprocessed_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("file_assets.id", ondelete="RESTRICT"),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped["AnalysisSession"] = relationship(
        "AnalysisSession",
        back_populates="images",
    )
    original_asset: Mapped["FileAsset"] = relationship(
        "FileAsset",
        foreign_keys=[original_asset_id],
    )
    preprocessed_asset: Mapped["FileAsset | None"] = relationship(
        "FileAsset",
        foreign_keys=[preprocessed_asset_id],
    )
    result: Mapped["ImageAnalysisResult | None"] = relationship(
        "ImageAnalysisResult",
        back_populates="image",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ProcessingJob(BigIntPkMixin, CreatedAtMixin, Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('analysis')",
            name="job_type_allowed",
        ),
        CheckConstraint(
            "status IN ('queued','processing','completed','failed')",
            name="status_allowed",
        ),
        CheckConstraint("attempt_no > 0", name="attempt_no_positive"),
        UniqueConstraint(
            "session_id",
            "job_type",
            name="uq_processing_jobs_session_job_type",
        ),
        Index("ix_processing_jobs_status_created_at", "status", "created_at"),
        Index(
            "ix_processing_jobs_active_queue",
            "created_at",
            postgresql_where=text("status IN ('queued','processing')"),
        ),
    )

    session_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'analysis'"),
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    attempt_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    session: Mapped["AnalysisSession"] = relationship(
        "AnalysisSession",
        back_populates="processing_job",
    )


class ImageAnalysisResult(BigIntPkMixin, CreatedAtMixin, Base):
    __tablename__ = "image_analysis_results"
    __table_args__ = (
        CheckConstraint(
            "predicted_time_confidence IS NULL OR "
            "(predicted_time_confidence >= 0 AND predicted_time_confidence <= 1)",
            name="predicted_time_confidence_between_0_1",
        ),
        CheckConstraint(
            "confidence_flag IN ('normal','low','very_low')",
            name="confidence_flag_allowed",
        ),
        CheckConstraint(
            "cpe_score IS NULL OR cpe_score >= 0",
            name="cpe_score_non_negative_or_null",
        ),
        CheckConstraint(
            "cpe_area_percent IS NULL OR "
            "(cpe_area_percent >= 0 AND cpe_area_percent <= 100)",
            name="cpe_area_percent_between_0_100",
        ),
        CheckConstraint(
            "inference_time_ms IS NULL OR inference_time_ms >= 0",
            name="inference_time_ms_non_negative_or_null",
        ),
        Index(
            "ix_image_analysis_results_predicted_time_class",
            "predicted_time_class",
        ),
        Index(
            "ix_image_analysis_results_cpe_severity_label",
            "cpe_severity_label",
        ),
    )

    image_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_images.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    classifier_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("models.id", ondelete="RESTRICT"),
        nullable=True,
    )
    segmenter_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("models.id", ondelete="RESTRICT"),
        nullable=True,
    )
    scorer_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("models.id", ondelete="RESTRICT"),
        nullable=True,
    )

    predicted_time_class: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    predicted_time_confidence: Mapped[float | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    top2_predictions: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    confidence_flag: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'normal'"),
    )

    cpe_score: Mapped[float | None] = mapped_column(
        Numeric(6, 3),
        nullable=True,
    )
    cpe_severity_label: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    cpe_area_percent: Mapped[float | None] = mapped_column(
        Numeric(6, 3),
        nullable=True,
    )

    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=EMPTY_OBJECT_JSONB,
    )
    warnings: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=EMPTY_ARRAY_JSONB,
    )

    mask_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("file_assets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    overlay_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("file_assets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    heatmap_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("file_assets.id", ondelete="RESTRICT"),
        nullable=True,
    )

    inference_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    image: Mapped["AnalysisImage"] = relationship(
        "AnalysisImage",
        back_populates="result",
    )

    classifier_model: Mapped["Model | None"] = relationship(
        "Model",
        foreign_keys=[classifier_model_id],
    )
    segmenter_model: Mapped["Model | None"] = relationship(
        "Model",
        foreign_keys=[segmenter_model_id],
    )
    scorer_model: Mapped["Model | None"] = relationship(
        "Model",
        foreign_keys=[scorer_model_id],
    )

    mask_asset: Mapped["FileAsset | None"] = relationship(
        "FileAsset",
        foreign_keys=[mask_asset_id],
    )
    overlay_asset: Mapped["FileAsset | None"] = relationship(
        "FileAsset",
        foreign_keys=[overlay_asset_id],
    )
    heatmap_asset: Mapped["FileAsset | None"] = relationship(
        "FileAsset",
        foreign_keys=[heatmap_asset_id],
    )