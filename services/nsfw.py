from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional

from aiogram import Bot
from nudenet import NudeDetector

logger = logging.getLogger(__name__)

GLOBAL_THRESHOLD = 0.7

CLASS_THRESHOLDS = {
    # Female
    "FEMALE_GENITALIA_EXPOSED": 0.7,
    "FEMALE_GENITALIA_COVERED": 0.8,
    "FEMALE_BREAST_EXPOSED": 0.7,
    "FEMALE_BREAST_COVERED": 0.99,
    # Male
    "MALE_GENITALIA_EXPOSED": 0.3,
    "MALE_BREAST_EXPOSED": 0.3,
    # Shared areas
    "ANUS_EXPOSED": 0.7,
    "ANUS_COVERED": 0.6,
    "FEET_EXPOSED": 0.5,
    "FEET_COVERED": 0.5,
    "BELLY_EXPOSED": 0.5,
    "BELLY_COVERED": 0.5,
    "BUTTOCKS_EXPOSED":0.5,
}

UNSAFE_CLASSES = set(CLASS_THRESHOLDS.keys())

# Lazy-loaded singleton detector with a lock to avoid concurrent initialization.
_detector: Optional[NudeDetector] = None
_detector_lock = asyncio.Lock()


async def _load_detector() -> NudeDetector:
    global _detector
    if _detector:
        return _detector

    async with _detector_lock:
        if _detector:
            return _detector

        def _load() -> NudeDetector:
            # Downloads weights on first call if not cached locally.
            return NudeDetector()

        _detector = await asyncio.to_thread(_load)
        logger.info("NSFW detector loaded (NudeDetector)")
        return _detector


async def _classify(image_path: str) -> dict:
    detector = await _load_detector()

    def _run() -> dict:
        # Returns list of detections; wrap as dict for uniform handling.
        return {"detections": detector.detect(image_path)}

    return await asyncio.to_thread(_run)


async def is_photo_nsfw(
    image_path: str,
    threshold: float | None = None,
    class_thresholds: Optional[dict[str, float]] = None,
) -> bool:
    """
    Returns True if image is considered NSFW.
    Uses NudeDetector: flags if any configured class meets or exceeds its threshold.
    """
    detection_threshold = GLOBAL_THRESHOLD if threshold is None else threshold
    thresholds = {**CLASS_THRESHOLDS, **(class_thresholds or {})}
    allowed_classes = set(thresholds.keys()) or UNSAFE_CLASSES

    result = await _classify(image_path)
    detections = result.get("detections") or []
    for item in detections:
        cls = item.get("class")
        if cls not in allowed_classes:
            continue
        score = float(item.get("score", 0.0) or 0.0)
        cutoff = thresholds.get(cls, detection_threshold)
        if score >= cutoff:
            return True
    return False



async def download_photo_to_tmp(bot: Bot, file_id: str) -> str:
    """Download Telegram file to a temporary JPEG path and return it."""
    tg_file = await bot.get_file(file_id)
    fd, path = tempfile.mkstemp(suffix=".jpg")
    tmp_path = Path(path)
    try:
        with open(fd, "wb") as f:
            await bot.download_file(tg_file.file_path, f)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return str(tmp_path)
