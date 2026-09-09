"""Style Cut Desk — cutout plus a local style-preset library."""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Iterator

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageFilter, ImageOps
from pydantic import BaseModel, Field

from axioxmedia import (
    AIO_BRAND,
    aio_logo_png,
    aio_watermark,
    apply_hwnd_icon,
    axiox_window_title,
)

APP_VERSION = "1.1.0"
EXPORT_CAPS = (512, 1024, 2048, 4096, 8192)

PRESETS = [
    {
        "id": "white-stencil",
        "zh": "白线黑底模板",
        "en": "White stencil",
        "fill": "#000000",
        "hint_zh": "透明件填白，内部结构描黑，默认铺黑底。",
        "hint_en": "White fill, black inner lines, black plate by default.",
    },
    {
        "id": "black-stencil",
        "zh": "黑线白底模板",
        "en": "Black stencil",
        "fill": "#ffffff",
        "hint_zh": "透明件填黑，内部结构描白，默认铺白底。",
        "hint_en": "Black fill, white inner lines, white plate by default.",
    },
    {
        "id": "line-art",
        "zh": "线稿",
        "en": "Line art",
        "fill": "transparent",
        "hint_zh": "只保留结构线，背景保持透明或你选的填充色。",
        "hint_en": "Edges only. Background stays transparent or your fill.",
    },
    {
        "id": "silhouette",
        "zh": "单色剪影",
        "en": "Silhouette",
        "fill": "transparent",
        "hint_zh": "整块剪影铺成一种颜色，默认用全局 LUT 色。",
        "hint_en": "Flat subject fill. Uses the LUT tint when set.",
    },
    {
        "id": "cutout-color",
        "zh": "保留原色透明件",
        "en": "Color cutout",
        "fill": "transparent",
        "hint_zh": "只抠底，不改物体颜色。",
        "hint_en": "Keep original subject color after the cutout.",
    },
]

LUTS = [
    {"id": "none", "zh": "关闭", "en": "Off"},
    {"id": "steel", "zh": "钢青", "en": "Steel"},
    {"id": "rust", "zh": "锈橙", "en": "Rust"},
    {"id": "night", "zh": "夜青", "en": "Night"},
    {"id": "mono", "zh": "单色", "en": "Mono"},
    {"id": "paper", "zh": "图纸", "en": "Paper"},
]


def app_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = app_root()
STATIC = ROOT / "static"
JOBS_ROOT = runtime_dir() / "work" / "jobs"
LOG_FILE = runtime_dir() / "style_cut_desk.log"

app = FastAPI(title="Style Cut Desk", version="1.0.0")
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def write_log(message: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(message.rstrip() + "\n")
    except OSError:
        pass


def job_dir(job_id: str) -> Path:
    path = JOBS_ROOT / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_job(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    return job


def emit(job: dict[str, Any], event: str, **payload: Any) -> None:
    item = {"event": event, **payload}
    with _jobs_lock:
        job.setdefault("events", []).append(item)
        job["last"] = item


def sse_pack(event: str, **payload: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def load_rgba(path: Path) -> Image.Image:
    img = Image.open(path)
    if getattr(img, "is_animated", False):
        img.seek(0)
    return img.convert("RGBA")


def save_png(img: Image.Image, path: Path, compress: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    params: dict[str, Any] = {"format": "PNG"}
    if compress:
        params.update(optimize=True, compress_level=9)
    else:
        params.update(optimize=False, compress_level=3)
    img.save(path, **params)


def parse_hex_color(value: str) -> tuple[int, int, int, int] | None:
    text = (value or "").strip().lower()
    if not text or text in {"transparent", "none", "alpha"}:
        return None
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) == 6:
        text += "ff"
    if len(text) != 8:
        raise HTTPException(400, "颜色格式应为 #RRGGBB 或 transparent")
    try:
        r = int(text[0:2], 16)
        g = int(text[2:4], 16)
        b = int(text[4:6], 16)
        a = int(text[6:8], 16)
    except ValueError as exc:
        raise HTTPException(400, "颜色格式无效") from exc
    return r, g, b, a


def conv2(gray: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    h, w = gray.shape
    kh, kw = kernel.shape
    ph, pw = kh // 2, kw // 2
    padded = np.pad(gray, ((ph, ph), (pw, pw)), mode="edge")
    out = np.zeros((h, w), dtype=np.float32)
    for i in range(kh):
        for j in range(kw):
            out += kernel[i, j] * padded[i : i + h, j : j + w]
    return out


def dilate_bool(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    if radius <= 0:
        return mask
    padded = np.pad(mask, radius, mode="constant", constant_values=False)
    out = np.zeros_like(mask)
    h, w = mask.shape
    span = 2 * radius + 1
    for dy in range(span):
        for dx in range(span):
            out |= padded[dy : dy + h, dx : dx + w]
    return out


def gradient_mag(gray: np.ndarray) -> np.ndarray:
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
    ky = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32)
    gx = conv2(gray, kx)
    gy = conv2(gray, ky)
    return np.sqrt(gx * gx + gy * gy)


def apply_lut(rgb: np.ndarray, lut: str, strength: float) -> np.ndarray:
    strength = float(max(0.0, min(1.0, strength)))
    if lut == "none" or strength <= 0:
        return rgb
    src = rgb.astype(np.float32)
    r, g, b = src[..., 0], src[..., 1], src[..., 2]
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if lut == "steel":
        dst = np.stack([luma * 0.72 + 18, luma * 0.86 + 28, luma * 1.05 + 46], axis=-1)
    elif lut == "rust":
        dst = np.stack([luma * 1.08 + 36, luma * 0.62 + 16, luma * 0.38 + 8], axis=-1)
    elif lut == "night":
        dst = np.stack([luma * 0.35 + 8, luma * 0.78 + 22, luma * 1.12 + 38], axis=-1)
    elif lut == "mono":
        dst = np.stack([luma, luma, luma], axis=-1)
    elif lut == "paper":
        inv = 255.0 - luma
        dst = np.stack([inv * 0.94 + 18, inv * 0.90 + 16, inv * 0.82 + 10], axis=-1)
    else:
        return rgb
    mixed = src * (1.0 - strength) + dst * strength
    return np.clip(mixed, 0, 255)


def style_cutout(cut: Image.Image, preset: str) -> Image.Image:
    arr = np.array(cut)
    rgb = arr[..., :3].astype(np.float32)
    alpha = arr[..., 3].astype(np.float32)
    subject = alpha > 12
    if not subject.any():
        return cut.copy()

    gray = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    mag = gradient_mag(gray)
    alpha_edge = gradient_mag(alpha)
    inner = subject & ((mag > 28) | (alpha_edge > 18))
    inner = dilate_bool(inner, 1)
    fill_mask = subject & ~inner

    out = np.zeros_like(arr)
    if preset == "cutout-color":
        out[..., :3] = arr[..., :3]
        out[..., 3] = arr[..., 3]
        return Image.fromarray(out, "RGBA")

    if preset == "silhouette":
        out[subject, 0] = 237
        out[subject, 1] = 241
        out[subject, 2] = 247
        out[subject, 3] = 255
        return Image.fromarray(out, "RGBA")

    if preset == "line-art":
        lines = dilate_bool(inner, 0)
        out[lines, :3] = 237
        out[lines, 3] = 255
        return Image.fromarray(out, "RGBA")

    if preset == "black-stencil":
        out[fill_mask, :3] = 12
        out[inner, :3] = 245
        out[subject, 3] = 255
        return Image.fromarray(out, "RGBA")

    # white-stencil — matches the supplied board / stencil example
    out[fill_mask, :3] = 245
    out[inner, :3] = 12
    out[subject, 3] = 255
    return Image.fromarray(out, "RGBA")


def composite_plate(
    subject: Image.Image,
    fill: tuple[int, int, int, int] | None,
    plate: Image.Image | None,
    plate_enabled: bool,
    pad_outer: int,
    pad_inner: int,
) -> Image.Image:
    pad_outer = max(0, min(4096, int(pad_outer)))
    pad_inner = max(0, min(4096, int(pad_inner)))
    sw, sh = subject.size
    inner_w = sw + pad_inner * 2
    inner_h = sh + pad_inner * 2
    canvas_w = inner_w + pad_outer * 2
    canvas_h = inner_h + pad_outer * 2

    if fill is None:
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    else:
        canvas = Image.new("RGBA", (canvas_w, canvas_h), fill)

    if plate_enabled and plate is not None:
        plate_rgba = plate.convert("RGBA")
        fitted = ImageOps.fit(plate_rgba, (inner_w, inner_h), method=Image.Resampling.LANCZOS)
        canvas.paste(fitted, (pad_outer, pad_outer), fitted)

    canvas.alpha_composite(subject, (pad_outer + pad_inner, pad_outer + pad_inner))
    return canvas


def apply_lut_image(img: Image.Image, lut: str, strength: float) -> Image.Image:
    if lut == "none" or strength <= 0:
        return img
    arr = np.array(img)
    rgb = apply_lut(arr[..., :3], lut, strength)
    out = arr.copy()
    alpha = arr[..., 3] > 0
    out[..., :3][alpha] = rgb[alpha].astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def export_sizes_for(width: int, height: int, force: bool = False) -> list[dict[str, Any]]:
    long_side = max(int(width), int(height))
    items = [{"id": "original", "label": f"{width}×{height}", "px": long_side, "force": False}]
    for cap in EXPORT_CAPS:
        if force or cap <= long_side:
            label = f"{cap}×{cap}" if force else f"{cap}×"
            items.append({"id": str(cap), "label": label, "px": cap, "force": force})
    return items


def resize_export(img: Image.Image, size: str, force: bool = False) -> Image.Image:
    if size in {"", "original", "source", "0"}:
        return img
    try:
        cap = int(str(size).rstrip("xX"))
    except ValueError as exc:
        raise HTTPException(400, "无法识别的导出尺寸") from exc
    if cap <= 0:
        return img
    if force:
        return img.resize((cap, cap), Image.Resampling.LANCZOS)
    w, h = img.size
    long_side = max(w, h)
    if long_side == cap:
        return img
    scale = cap / float(long_side)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    return img.resize((nw, nh), Image.Resampling.LANCZOS)


def normalize_image(data: bytes, suffix: str) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    if getattr(img, "is_animated", False):
        img.seek(0)
    if img.mode not in {"RGBA", "RGB"}:
        img = img.convert("RGBA")
    else:
        img = img.convert("RGBA")
    return img


def rembg_cut(img: Image.Image) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()
    try:
        from rembg import remove

        cut = remove(raw)
        return Image.open(io.BytesIO(cut)).convert("RGBA")
    except Exception as exc:
        write_log(f"rembg unavailable, fallback: {exc}")
        return edge_flood_cut(img)


def edge_flood_cut(img: Image.Image) -> Image.Image:
    arr = np.array(img.convert("RGBA"))
    rgb = arr[..., :3].astype(np.int16)
    h, w, _ = arr.shape
    samples = [
        rgb[0, 0],
        rgb[0, w - 1],
        rgb[h - 1, 0],
        rgb[h - 1, w - 1],
        rgb[0, w // 2],
        rgb[h - 1, w // 2],
        rgb[h // 2, 0],
        rgb[h // 2, w - 1],
    ]
    key = np.median(np.stack(samples, axis=0), axis=0)
    dist = np.sqrt(((rgb - key) ** 2).sum(axis=2))
    bg = dist < 28
    # flood from the border only so interior similar colors stay
    visited = np.zeros((h, w), dtype=bool)
    stack = []
    for x in range(w):
        stack.append((0, x))
        stack.append((h - 1, x))
    for y in range(h):
        stack.append((y, 0))
        stack.append((y, w - 1))
    while stack:
        y, x = stack.pop()
        if visited[y, x] or not bg[y, x]:
            continue
        visited[y, x] = True
        if y > 0:
            stack.append((y - 1, x))
        if y + 1 < h:
            stack.append((y + 1, x))
        if x > 0:
            stack.append((y, x - 1))
        if x + 1 < w:
            stack.append((y, x + 1))
    alpha = np.where(visited, 0, 255).astype(np.uint8)
    # soften the cut a little
    alpha_img = Image.fromarray(alpha, "L").filter(ImageFilter.GaussianBlur(radius=0.8))
    out = arr.copy()
    out[..., 3] = np.array(alpha_img)
    return Image.fromarray(out, "RGBA")


def chroma_cut(img: Image.Image, color: str, strength: float) -> Image.Image:
    key = parse_hex_color(color) or (0, 255, 0, 255)
    strength = float(max(0.001, min(1.0, strength)))
    arr = np.array(img.convert("RGBA"))
    rgb = arr[..., :3].astype(np.float32)
    target = np.array(key[:3], dtype=np.float32)
    dist = np.sqrt(((rgb - target) ** 2).sum(axis=2))
    thresh = 4.0 + strength * 255.0
    fade = np.clip((dist - thresh * 0.55) / max(1.0, thresh * 0.45), 0, 1)
    out = arr.copy()
    out[..., 3] = (out[..., 3].astype(np.float32) * fade).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


class RemoveBody(BaseModel):
    mode: str = Field(pattern="^(auto|chroma)$")
    color: str = "#00ff00"
    strength: float = 0.001


class StyleBody(BaseModel):
    preset: str = "white-stencil"
    fill: str = "#000000"
    lut: str = "none"
    lut_strength: float = 1.0
    plate_enabled: bool = False
    pad_outer: int = 24
    pad_inner: int = 16


class SaveBody(BaseModel):
    path: str


class ExportBody(BaseModel):
    path: str
    size: str = "original"
    compress: bool = False
    force: bool = False


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/brand/logo.png")
def brand_logo() -> Response:
    return Response(content=aio_logo_png(), media_type="image/png")


@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(content=aio_logo_png(), media_type="image/png")


@app.get("/api/defaults")
def api_defaults() -> dict[str, Any]:
    dest = str(Path.home() / "Pictures")
    if os.name == "nt":
        d = Path("D:/")
        if d.exists():
            dest = str(Path("D:/Exports"))
    return {
        "brand": aio_watermark(),
        "presets": PRESETS,
        "luts": LUTS,
        "export_caps": list(EXPORT_CAPS),
        "dest": dest,
        "aio": AIO_BRAND,
        "version": APP_VERSION,
    }


@app.get("/api/presets")
def api_presets() -> dict[str, Any]:
    return {"presets": PRESETS, "luts": LUTS}


@app.post("/api/jobs/normalize")
async def api_normalize(file: UploadFile = File(...)) -> dict[str, Any]:
    data = await file.read()
    if not data:
        raise HTTPException(400, "空文件")
    job_id = uuid.uuid4().hex[:12]
    folder = job_dir(job_id)
    try:
        img = normalize_image(data, Path(file.filename or "src.png").suffix)
    except Exception as exc:
        raise HTTPException(400, f"无法读取图片：{exc}") from exc
    src_path = folder / "source.png"
    save_png(img, src_path)
    job = {
        "id": job_id,
        "src_name": Path(file.filename or "image.png").name,
        "width": img.size[0],
        "height": img.size[1],
        "source": str(src_path),
        "cut": None,
        "styled": None,
        "plate": None,
        "events": [],
        "last": {"event": "progress", "percent": 8, "label": "normalized"},
    }
    with _jobs_lock:
        _jobs[job_id] = job
    return {
        "id": job_id,
        "width": img.size[0],
        "height": img.size[1],
        "name": job["src_name"],
        "sizes": export_sizes_for(img.size[0], img.size[1]),
    }


@app.post("/api/jobs/{job_id}/remove")
def api_remove(job_id: str, body: RemoveBody) -> dict[str, Any]:
    job = get_job(job_id)
    src = load_rgba(Path(job["source"]))
    emit(job, "progress", percent=20, label="cutout")
    if body.mode == "chroma":
        cut = chroma_cut(src, body.color, body.strength)
    else:
        cut = rembg_cut(src)
    cut_path = job_dir(job_id) / "result.png"
    save_png(cut, cut_path)
    preview_path = job_dir(job_id) / "preview.png"
    save_png(cut, preview_path)
    job["cut"] = str(cut_path)
    emit(job, "done", has_result=True)
    return {"id": job_id, "has_result": True}


@app.get("/api/jobs/{job_id}/events")
def api_events(job_id: str) -> StreamingResponse:
    job = get_job(job_id)

    def stream() -> Iterator[str]:
        seen = 0
        end = time.time() + 120
        while time.time() < end:
            with _jobs_lock:
                events = list(job.get("events") or [])
            while seen < len(events):
                item = events[seen]
                seen += 1
                event = item.get("event") or "progress"
                payload = {k: v for k, v in item.items() if k != "event"}
                yield sse_pack(event, **payload)
                if event in {"done", "error"}:
                    return
            time.sleep(0.15)
        yield sse_pack("error", message="progress timeout")

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/preview.png")
def api_preview(job_id: str, layer: str = "auto") -> FileResponse:
    job = get_job(job_id)
    if layer == "source":
        path = Path(job["source"])
    elif layer == "cut" and job.get("cut"):
        path = Path(job["cut"])
    elif layer == "styled" and job.get("styled"):
        path = Path(job["styled"])
    else:
        path = Path(job.get("styled") or job.get("cut") or job["source"])
    return FileResponse(path, media_type="image/png")


@app.get("/api/jobs/{job_id}/result.png")
def api_result(job_id: str) -> FileResponse:
    job = get_job(job_id)
    if not job.get("cut"):
        raise HTTPException(404, "还没有抠底结果")
    return FileResponse(job["cut"], media_type="image/png")


@app.get("/api/jobs/{job_id}/styled.png")
def api_styled(job_id: str) -> FileResponse:
    job = get_job(job_id)
    if not job.get("styled"):
        raise HTTPException(404, "还没有风格结果")
    return FileResponse(job["styled"], media_type="image/png")


@app.post("/api/jobs/{job_id}/save")
def api_save(job_id: str, body: SaveBody) -> dict[str, Any]:
    job = get_job(job_id)
    src = job.get("styled") or job.get("cut")
    if not src:
        raise HTTPException(400, "没有可保存的结果")
    dest = Path(body.path).expanduser()
    if dest.exists() and dest.resolve() == Path(job["source"]).resolve():
        raise HTTPException(400, "禁止覆盖原图")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return {"path": str(dest)}


@app.post("/api/jobs/{job_id}/plate")
async def api_plate(job_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    job = get_job(job_id)
    data = await file.read()
    if not data:
        raise HTTPException(400, "空底图")
    try:
        plate = normalize_image(data, Path(file.filename or "plate.png").suffix)
    except Exception as exc:
        raise HTTPException(400, f"无法读取底图：{exc}") from exc
    path = job_dir(job_id) / "plate.png"
    save_png(plate, path)
    job["plate"] = str(path)
    return {"ok": True, "width": plate.size[0], "height": plate.size[1]}


@app.post("/api/jobs/{job_id}/style")
def api_style(job_id: str, body: StyleBody) -> dict[str, Any]:
    job = get_job(job_id)
    if not job.get("cut"):
        raise HTTPException(400, "请先抠底")
    ids = {p["id"] for p in PRESETS}
    if body.preset not in ids:
        raise HTTPException(400, "未知预设")
    lut_ids = {item["id"] for item in LUTS}
    if body.lut not in lut_ids:
        raise HTTPException(400, "未知 LUT")
    emit(job, "progress", percent=62, label="style")
    cut = load_rgba(Path(job["cut"]))
    styled = style_cutout(cut, body.preset)
    fill = parse_hex_color(body.fill)
    plate = load_rgba(Path(job["plate"])) if job.get("plate") else None
    composed = composite_plate(
        styled,
        fill,
        plate,
        body.plate_enabled and plate is not None,
        body.pad_outer,
        body.pad_inner,
    )
    composed = apply_lut_image(composed, body.lut, body.lut_strength)
    out_path = job_dir(job_id) / "styled.png"
    save_png(composed, out_path)
    job["styled"] = str(out_path)
    emit(job, "done", has_result=True)
    return {
        "id": job_id,
        "width": composed.size[0],
        "height": composed.size[1],
        "preset": body.preset,
    }


@app.get("/api/jobs/{job_id}/export-sizes")
def api_export_sizes(job_id: str, force: bool = False) -> dict[str, Any]:
    job = get_job(job_id)
    return {"sizes": export_sizes_for(job["width"], job["height"], force=force)}


@app.post("/api/jobs/{job_id}/export")
def api_export(job_id: str, body: ExportBody) -> dict[str, Any]:
    job = get_job(job_id)
    src = job.get("styled") or job.get("cut")
    if not src:
        raise HTTPException(400, "没有可导出的结果")
    img = load_rgba(Path(src))
    img = resize_export(img, body.size, force=body.force)
    dest = Path(body.path).expanduser()
    if dest.exists() and dest.resolve() == Path(job["source"]).resolve():
        raise HTTPException(400, "禁止覆盖原图")
    dest.parent.mkdir(parents=True, exist_ok=True)
    save_png(img, dest, compress=body.compress)
    return {"path": str(dest), "width": img.size[0], "height": img.size[1]}


@app.post("/api/dialog/save")
def api_dialog_save(name: str = "style-cut.png") -> dict[str, Any]:
    try:
        import webview

        windows = webview.windows
        if not windows:
            return {"path": ""}
        picked = windows[0].create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=Path(name).name or "style-cut.png",
            file_types=("PNG (*.png)",),
        )
        if not picked:
            return {"path": ""}
        path = picked if isinstance(picked, str) else picked[0]
        return {"path": path}
    except Exception as exc:
        write_log(f"save dialog: {exc}")
        return {"path": ""}


@app.post("/api/dialog/open")
def api_dialog_open() -> dict[str, Any]:
    try:
        import webview

        windows = webview.windows
        if not windows:
            return {"path": ""}
        picked = windows[0].create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Images (*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.tif;*.tiff;*.gif)",),
        )
        if not picked:
            return {"path": ""}
        path = picked if isinstance(picked, str) else picked[0]
        return {"path": path}
    except Exception as exc:
        write_log(f"open dialog: {exc}")
        return {"path": ""}


def ensure_stdio() -> None:
    if sys.stdout is None:
        sys.stdout = LOG_FILE.open("a", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = LOG_FILE.open("a", encoding="utf-8")


def _free_port(preferred: int = 8787) -> int:
    import socket

    for port in (preferred, 8788, 8789, 8790, 0):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            chosen = int(sock.getsockname()[1])
        except OSError:
            chosen = -1
        finally:
            sock.close()
        if chosen > 0:
            return chosen
    raise RuntimeError("没有可用的本地端口")


def run_server(host: str, port: int, reload: bool = False) -> None:
    import uvicorn

    ensure_stdio()
    if reload:
        uvicorn.run(app, host=host, port=port, reload=True, log_level="warning", log_config=None)
        return
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        log_config=None,
        lifespan="on",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    server.run()


def wait_ready(url: str, server_error: list[str], timeout: float = 30.0) -> None:
    import httpx

    deadline = time.time() + timeout
    while time.time() < deadline:
        if server_error:
            raise RuntimeError(server_error[0])
        try:
            with httpx.Client(timeout=0.8, trust_env=False) as http:
                if http.get(url).status_code < 500:
                    return
        except httpx.HTTPError:
            time.sleep(0.2)
    extra = f"\n服务线程错误：{server_error[0]}" if server_error else ""
    raise RuntimeError(f"本地服务启动超时：{url}{extra}\n日志：{LOG_FILE}")


def show_error(message: str) -> None:
    write_log(message)
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "Style Cut Desk", 0x10)
            return
        except Exception:
            pass
    print(message, file=sys.stderr)


def run_desktop() -> None:
    import traceback
    import webbrowser

    import httpx

    write_log(f"start frozen={getattr(sys, 'frozen', False)} meipass={getattr(sys, '_MEIPASS', '')}")
    write_log(f"static={STATIC} exists={STATIC.exists()}")
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    write_log(f"bind {url}")
    server_error: list[str] = []

    def _serve() -> None:
        try:
            run_server("127.0.0.1", port, reload=False)
        except Exception:
            server_error.append(traceback.format_exc())
            write_log(server_error[-1])

    thread = threading.Thread(target=_serve, name="uvicorn", daemon=True)
    thread.start()
    wait_ready(f"{url}/api/defaults", server_error)

    try:
        import webview

        window = webview.create_window(
            title=axiox_window_title(),
            url=url,
            width=1480,
            height=920,
            min_size=(980, 700),
            background_color="#0b0d12",
        )

        def paint_chrome(_=None) -> None:
            if os.name != "nt":
                return
            try:
                import ctypes

                hwnd = int(window.native.Handle.ToInt32())
                apply_hwnd_icon(hwnd)
                value = ctypes.c_int(1)
                for attr in (20, 19):
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
                    )
            except Exception as exc:
                write_log(f"dark titlebar skipped: {exc}")

        try:
            window.events.shown += paint_chrome
        except Exception:
            pass
        webview.start()
        return
    except Exception:
        write_log(traceback.format_exc())
        webbrowser.open(url)
        while thread.is_alive():
            thread.join(timeout=0.5)


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    if "--web" in sys.argv:
        run_server("127.0.0.1", _free_port(), reload=False)
    else:
        try:
            run_desktop()
        except Exception as exc:
            show_error(str(exc))
            raise
