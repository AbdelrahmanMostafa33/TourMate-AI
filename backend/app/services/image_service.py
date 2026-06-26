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

from app.models.image import Image, ImageFeature
from app.models.enums import ProcessingStatus

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
        """Return all images linked to a trip, ordered by upload time."""
        result = await self.db.execute(
            select(Image)
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
