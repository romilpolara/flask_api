from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

from app.detector import DetectionError, get_detector
from app.metadata import OBJECT_INFO

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Global Object Detection API",
    description="Upload an image or pass an image URL to detect objects using best1.pt.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class URLDetectionRequest(BaseModel):
    image_url: HttpUrl
    conf: float = Field(default=0.25, ge=0.0, le=1.0)
    iou: float = Field(default=0.45, ge=0.0, le=1.0)
    include_image: bool = False


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/classes")
def classes() -> dict[str, object]:
    detector = get_detector()
    return {
        "labels": detector.get_labels(),
        "object_info": OBJECT_INFO,
    }


@app.post("/detect/file")
async def detect_file(
    file: UploadFile = File(...),
    conf: float = Form(0.25),
    iou: float = Form(0.45),
    include_image: bool = Form(False),
) -> dict[str, object]:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload a valid image file.")

    try:
        image_bytes = await file.read()
        return get_detector().detect_bytes(
            image_bytes=image_bytes,
            source_name=file.filename or "uploaded-image",
            conf=conf,
            iou=iou,
            include_image=include_image,
        )
    except DetectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/detect/url")
def detect_url(payload: URLDetectionRequest) -> dict[str, object]:
    try:
        return get_detector().detect_url(
            image_url=str(payload.image_url),
            conf=payload.conf,
            iou=payload.iou,
            include_image=payload.include_image,
        )
    except DetectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
