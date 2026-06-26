# backend/app/services/image_service.py

"""Service layer for image and image-feature DB operations.

Decouples the route layer from SQLAlchemy logic, following the pattern
established by ``profile_service.py`` and ``chat_service.py``.
"""

from __future__ import annotations

import uuid
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.image import Image, ImageFeature
from app.models.enums import ProcessingStatus
from ai_engine.schemas.vision_schema import VisionFeatures

logger = logging.getLogger(__name__)


class ImageService:
    """CRUD operations for the ``images`` and ``image_features`` tables."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Image CRUD ──────────────────────────────────────────────────────────

    async def create_image(
        self,
        trip_id: str,
        file_name: str,
        file_url: str | None = None,
    ) -> Image:
        """Persist a new image record.

        Args:
            trip_id:  FK to the associated trip.
            file_name: Original upload file name.
            file_url:  Firebase Storage URL or ``None`` (processing in-flight).

        Returns:
            The newly created ``Image`` ORM instance.
        """
        image = Image(
            image_id=str(uuid.uuid4()),
            trip_id=trip_id,
            file_name=file_name,
            file_url=file_url,
            analysis_status=ProcessingStatus.pending,
        )
        self.db.add(image)
        return image

    async def get_images_for_trip(self, trip_id: str) -> list[Image]:
        """Return all images linked to a trip, ordered by upload time, with features eagerly loaded."""
        result = await self.db.execute(
            select(Image)
            .options(selectinload(Image.features))
            .where(Image.trip_id == trip_id)
            .order_by(Image.uploaded_at.asc())
        )
        return list(result.scalars().all())

    async def get_image(self, image_id: str) -> Image | None:
        """Fetch a single image by its ID."""
        result = await self.db.execute(
            select(Image).where(Image.image_id == image_id)
        )
        return result.scalar_one_or_none()

    async def get_image_with_features(self, image_id: str) -> Image | None:
        """Fetch a single image with its features eagerly loaded."""
        result = await self.db.execute(
            select(Image)
            .options(selectinload(Image.features))
            .where(Image.image_id == image_id)
        )
        return result.scalar_one_or_none()

    async def update_analysis_status(
        self,
        image_id: str,
        status: ProcessingStatus,
    ) -> Image | None:
        """Update the analysis status of an image (e.g. pending → completed)."""
        image = await self.get_image(image_id)
        if image:
            image.analysis_status = status
        return image

    async def delete_image(self, image_id: str) -> bool:
        """Delete an image and its associated features (cascade)."""
        image = await self.get_image(image_id)
        if not image:
            return False
        await self.db.delete(image)
        return True

    # ── Persist VisionFeatures ────────────────────────────────────────────

    async def create_image_with_features(
        self,
        trip_id: str,
        vision_features: VisionFeatures,
        file_name: str = "vision_upload.jpg",
    ) -> str:
        """Create an ``Image`` record + ``ImageFeature`` rows from ``VisionFeatures``.

        Maps each field of ``VisionFeatures`` to one or more ``ImageFeature`` rows:

        +---------------------------+---------------------------+
        | VisionFeatures field      | ImageFeature(s)           |
        +---------------------------+---------------------------+
        | interests                 | 1 row per interest        |
        | travel_style              | 1 row                     |
        | pace                      | 1 row                     |
        | food_preferences          | 1 row per preference      |
        | budget_level              | 1 row                     |
        | environment_type          | 1 row                     |
        | vibe                      | 1 row                     |
        | confidence                | 1 row (stored as value)   |
        +---------------------------+---------------------------+

        Returns:
            The ``image_id`` of the created ``Image`` record.
        """
        # ── Create Image record ────────────────────────────────────────────
        image_id = str(uuid.uuid4())
        image = Image(
            image_id=image_id,
            trip_id=trip_id,
            file_name=file_name,
            analysis_status=ProcessingStatus.completed,
        )
        self.db.add(image)

        # ── Map confidence to float ────────────────────────────────────────
        confidence_map = {"high": 0.9, "medium": 0.6, "low": 0.3}

        # ── Create ImageFeature rows ───────────────────────────────────────
        features: list[dict] = []

        for interest in vision_features.interests:
            features.append({
                "feature_type": "interest",
                "feature_name": interest,
                "confidence": confidence_map.get(vision_features.confidence, 0.5),
                "value": interest,
            })

        if vision_features.travel_style:
            features.append({
                "feature_type": "travel_style",
                "feature_name": vision_features.travel_style,
                "confidence": confidence_map.get(vision_features.confidence, 0.5),
                "value": vision_features.travel_style,
            })

        if vision_features.pace:
            features.append({
                "feature_type": "pace",
                "feature_name": vision_features.pace,
                "confidence": confidence_map.get(vision_features.confidence, 0.5),
                "value": vision_features.pace,
            })

        for pref in vision_features.food_preferences:
            features.append({
                "feature_type": "food_preference",
                "feature_name": pref,
                "confidence": confidence_map.get(vision_features.confidence, 0.5),
                "value": pref,
            })

        if vision_features.budget_level:
            features.append({
                "feature_type": "budget_level",
                "feature_name": vision_features.budget_level,
                "confidence": confidence_map.get(vision_features.confidence, 0.5),
                "value": vision_features.budget_level,
            })

        if vision_features.environment_type:
            features.append({
                "feature_type": "environment_type",
                "feature_name": vision_features.environment_type,
                "confidence": confidence_map.get(vision_features.confidence, 0.5),
                "value": vision_features.environment_type,
            })

        if vision_features.vibe:
            features.append({
                "feature_type": "vibe",
                "feature_name": vision_features.vibe,
                "confidence": confidence_map.get(vision_features.confidence, 0.5),
                "value": vision_features.vibe,
            })

        features.append({
            "feature_type": "confidence",
            "feature_name": vision_features.confidence,
            "confidence": confidence_map.get(vision_features.confidence, 0.5),
            "value": vision_features.confidence,
        })

        for feat in features:
            self.db.add(ImageFeature(
                feature_id=str(uuid.uuid4()),
                image_id=image_id,
                **feat,
            ))

        logger.info(
            "[ImageService] Persisted image %s with %d features (confidence=%s)",
            image_id,
            len(features),
            vision_features.confidence,
        )
        return image_id

    # ── ImageFeature CRUD ───────────────────────────────────────────────────

    async def create_feature(
        self,
        image_id: str,
        feature_type: str,
        feature_name: str | None = None,
        confidence: float | None = None,
        value: str | None = None,
        metadata: dict | None = None,
    ) -> ImageFeature:
        """Persist a single image feature."""
        feature = ImageFeature(
            feature_id=str(uuid.uuid4()),
            image_id=image_id,
            feature_type=feature_type,
            feature_name=feature_name,
            confidence=confidence,
            value=value,
            extra_info=metadata,
        )
        self.db.add(feature)
        return feature

    async def get_features_for_image(self, image_id: str) -> list[ImageFeature]:
        """Return all features for a given image."""
        result = await self.db.execute(
            select(ImageFeature).where(ImageFeature.image_id == image_id)
        )
        return list(result.scalars().all())

    async def delete_features_for_image(self, image_id: str) -> None:
        """Remove all features linked to an image (e.g. before re-analysis)."""
        from sqlalchemy import delete
        await self.db.execute(
            delete(ImageFeature).where(ImageFeature.image_id == image_id)
        )
