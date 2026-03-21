from __future__ import annotations

import base64
import io
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests
from PIL import Image, UnidentifiedImageError

BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_ultralytics_dir() -> Path:
    configured_dir = os.getenv("YOLO_CONFIG_DIR")
    if configured_dir:
        target = Path(configured_dir)
    else:
        # Azure App Service can mount deployed code as read-only, so prefer a writable temp dir.
        target = Path(tempfile.gettempdir()) / "ultralytics"

    target.mkdir(parents=True, exist_ok=True)
    return target


ULTRALYTICS_DIR = _resolve_ultralytics_dir()
os.environ["YOLO_CONFIG_DIR"] = str(ULTRALYTICS_DIR)

from ultralytics import YOLO

from app.metadata import DEFAULT_ESTIMATION_NOTE, OBJECT_INFO

MODEL_PATH = BASE_DIR / "model" / "best1.pt"


class DetectionError(Exception):
    """Raised when detection input is invalid or inference fails."""


class YOLODetector:
    def __init__(self, model_path: Path) -> None:
        if not model_path.exists():
            raise DetectionError(f"Model file not found: {model_path}")
        self.model_path = model_path
        self.model = YOLO(str(model_path))

    def get_labels(self) -> dict[int, str]:
        return dict(self.model.names)

    def detect_bytes(
        self,
        image_bytes: bytes,
        source_name: str,
        conf: float = 0.25,
        iou: float = 0.45,
        include_image: bool = False,
    ) -> dict[str, Any]:
        image = self._open_image(image_bytes)
        results = self.model.predict(image, conf=conf, iou=iou, verbose=False)
        if not results:
            raise DetectionError("No result returned by the model.")
        return self._serialize_result(
            result=results[0],
            source=source_name,
            include_image=include_image,
        )

    def detect_url(
        self,
        image_url: str,
        conf: float = 0.25,
        iou: float = 0.45,
        include_image: bool = False,
    ) -> dict[str, Any]:
        try:
            response = requests.get(image_url, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DetectionError(f"Unable to download image from URL: {exc}") from exc
        return self.detect_bytes(
            image_bytes=response.content,
            source_name=image_url,
            conf=conf,
            iou=iou,
            include_image=include_image,
        )

    def _open_image(self, image_bytes: bytes) -> Image.Image:
        try:
            image = Image.open(io.BytesIO(image_bytes))
            return image.convert("RGB")
        except UnidentifiedImageError as exc:
            raise DetectionError("Uploaded file is not a valid image.") from exc

    def _serialize_result(
        self,
        result: Any,
        source: str,
        include_image: bool,
    ) -> dict[str, Any]:
        labels = self.get_labels()
        boxes = result.boxes
        detections: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        biodegradable_count = 0
        non_biodegradable_count = 0
        recyclable_count = 0
        non_recyclable_count = 0
        total_estimated_weight_kg = 0.0
        total_estimated_energy_kwh = 0.0

        for index in range(len(boxes)):
            box = boxes[index]
            class_id = int(box.cls.item())
            label = labels.get(class_id, str(class_id))
            info = OBJECT_INFO.get(label, self._default_info(label))
            confidence = round(float(box.conf.item()), 4)
            x1, y1, x2, y2 = [round(float(value), 2) for value in box.xyxy[0].tolist()]
            width = round(x2 - x1, 2)
            height = round(y2 - y1, 2)
            estimated_weight_kg = round(float(info["estimated_item_weight_kg"]), 4)
            estimated_energy_kwh = round(
                estimated_weight_kg * float(info["estimated_energy_recovery_kwh_per_kg"]),
                4,
            )

            detections.append(
                {
                    "id": index + 1,
                    "class_id": class_id,
                    "label": label,
                    "confidence": confidence,
                    "bbox": {
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                        "width": width,
                        "height": height,
                    },
                    "estimated_weight_kg": estimated_weight_kg,
                    "estimated_energy_recovery_kwh": estimated_energy_kwh,
                    "info": info,
                }
            )
            counts[label] = counts.get(label, 0) + 1
            total_estimated_weight_kg += estimated_weight_kg
            total_estimated_energy_kwh += estimated_energy_kwh
            if info["is_biodegradable"]:
                biodegradable_count += 1
            else:
                non_biodegradable_count += 1
            if info["is_recyclable"]:
                recyclable_count += 1
            else:
                non_recyclable_count += 1

        detected_object_info = [
            self._build_object_summary(label, count)
            for label, count in sorted(counts.items())
        ]

        payload: dict[str, Any] = {
            "success": True,
            "source": source,
            "model_name": self.model_path.name,
            "image_size": {
                "width": int(result.orig_shape[1]),
                "height": int(result.orig_shape[0]),
            },
            "total_detections": len(detections),
            "counts": counts,
            "detections": detections,
            "detected_object_info": detected_object_info,
            "sustainability_summary": {
                "biodegradable_objects": biodegradable_count,
                "non_biodegradable_objects": non_biodegradable_count,
                "recyclable_objects": recyclable_count,
                "non_recyclable_objects": non_recyclable_count,
                "total_estimated_weight_kg": round(total_estimated_weight_kg, 4),
                "total_estimated_energy_recovery_kwh": round(total_estimated_energy_kwh, 4),
                "estimation_note": DEFAULT_ESTIMATION_NOTE,
            },
        }

        if include_image:
            payload["annotated_image"] = self._encode_annotated_image(result)

        return payload

    def _build_object_summary(self, label: str, count: int) -> dict[str, Any]:
        info = OBJECT_INFO.get(label, self._default_info(label))
        total_weight = round(count * float(info["estimated_item_weight_kg"]), 4)
        total_energy = round(total_weight * float(info["estimated_energy_recovery_kwh_per_kg"]), 4)
        return {
            "label": label,
            "count": count,
            "estimated_total_weight_kg": total_weight,
            "estimated_total_energy_recovery_kwh": total_energy,
            **info,
        }

    def _encode_annotated_image(self, result: Any) -> dict[str, str]:
        annotated = result.plot()
        image = Image.fromarray(annotated[:, :, ::-1])
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90)
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return {
            "mime_type": "image/jpeg",
            "base64": encoded,
        }

    def _default_info(self, label: str) -> dict[str, Any]:
        return {
            "title": label.title(),
            "category": "Detected Object",
            "description": "Object detected by the model.",
            "handling_tip": "Add your own business-specific description here if needed.",
            "waste_nature": "Unknown",
            "is_biodegradable": False,
            "is_recyclable": False,
            "recyclability": "Unknown",
            "estimated_item_weight_kg": 0.1,
            "estimated_energy_recovery_kwh_per_kg": 0.0,
            "energy_recovery_method": "Unknown",
            "estimation_note": DEFAULT_ESTIMATION_NOTE,
        }


@lru_cache(maxsize=1)
def get_detector() -> YOLODetector:
    return YOLODetector(MODEL_PATH)
