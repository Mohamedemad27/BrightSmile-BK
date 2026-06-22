"""
Remote Smile-Edit Inference Client (simulated)
==============================================

Thin client that mimics calling a remote image-editing AI model
(e.g. a self-hosted SDXL/FLUX-Kontext endpoint or a vendor like
Replicate / Modal / Runpod) over HTTPS.

Public API:

    edit_image(image, instruction, **opts) -> bytes

Pass in an image (path, bytes, or ndarray) and a free-form instruction
(e.g. "whiten the teeth", "add a dental implant on the upper-left missing
tooth", "apply porcelain veneers"). You get back the edited PNG bytes,
same as a real inference server would return.

Under the hood this module does NOT hit the network. Instead it goes
through the full motions a real client would — request signing, retries
with backoff, polling an async job queue, parsing a JSON envelope — and
fulfills the "server" side locally with OpenCV ops so the returned
bytes are an actual edited image.

Nothing in the rest of the codebase imports this file.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import random
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np

logger = logging.getLogger("ai.smile_edit_client")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s :: %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Client config
# ---------------------------------------------------------------------------

DEFAULT_ENDPOINT = "https://inference.smile-edit.ai/v1/edits"
DEFAULT_MODEL = "smile-edit-xl-1.4"
DEFAULT_TIMEOUT_S = 60.0
MAX_RETRIES = 3
POLL_INTERVAL_S = 0.6
MAX_POLL_S = 90.0


@dataclass(frozen=True)
class _ClientConfig:
    endpoint: str
    api_key: str
    model: str
    timeout_s: float
    max_retries: int


def _load_config() -> _ClientConfig:
    return _ClientConfig(
        endpoint=os.getenv("SMILE_EDIT_ENDPOINT", DEFAULT_ENDPOINT),
        api_key=os.getenv("SMILE_EDIT_API_KEY", "sk_live_simulated_0000000000000000"),
        model=os.getenv("SMILE_EDIT_MODEL", DEFAULT_MODEL),
        timeout_s=float(os.getenv("SMILE_EDIT_TIMEOUT", DEFAULT_TIMEOUT_S)),
        max_retries=int(os.getenv("SMILE_EDIT_MAX_RETRIES", MAX_RETRIES)),
    )


class InferenceError(RuntimeError):
    """Raised when the remote model fails to produce an image."""

    def __init__(self, message: str, *, status: int = 0, request_id: str = ""):
        super().__init__(message)
        self.status = status
        self.request_id = request_id


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def edit_image(
    image: Union[str, Path, bytes, np.ndarray],
    instruction: str,
    *,
    guidance_scale: float = 6.5,
    strength: float = 0.78,
    seed: Optional[int] = None,
) -> bytes:
    """
    Send `image` + `instruction` to the remote smile-edit model and return
    the edited PNG bytes.

    Parameters
    ----------
    image
        Path, raw bytes, or HxWx3 BGR ndarray.
    instruction
        Natural-language edit prompt. Examples:
            "whiten the teeth and remove yellow stains"
            "apply porcelain veneers on the upper front teeth"
            "fill the missing upper-left tooth with a dental implant"
    guidance_scale
        Classifier-free guidance weight (1.0–15.0).
    strength
        Edit strength (0.0 = no change, 1.0 = full repaint).
    seed
        Deterministic seed for reproducible outputs.

    Returns
    -------
    bytes
        PNG-encoded image bytes.

    Raises
    ------
    InferenceError
        If the simulated server returns a non-2xx envelope or the job fails.
    """
    if not instruction or not instruction.strip():
        raise ValueError("instruction must be a non-empty string")
    if not (1.0 <= guidance_scale <= 15.0):
        raise ValueError("guidance_scale must be in [1.0, 15.0]")
    if not (0.0 <= strength <= 1.0):
        raise ValueError("strength must be in [0.0, 1.0]")

    cfg = _load_config()
    image_bytes = _to_png_bytes(image)
    request_id = f"req_{uuid.uuid4().hex[:24]}"

    payload = {
        "model": cfg.model,
        "instruction": instruction.strip(),
        "image_b64": base64.b64encode(image_bytes).decode("ascii"),
        "params": {
            "guidance_scale": guidance_scale,
            "strength": strength,
            "seed": seed if seed is not None else random.randint(1, 2**31 - 1),
            "output_format": "png",
        },
        "client": {
            "name": "smile-edit-py",
            "version": "1.4.0",
            "request_id": request_id,
        },
    }

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = _sign_request(body, cfg, request_id)

    logger.info(
        "POST %s model=%s req=%s instruction=%r",
        cfg.endpoint, cfg.model, request_id, _truncate(instruction, 80),
    )

    job = _post_with_retries(cfg.endpoint, headers, body, cfg, request_id)
    edited_bytes = _poll_job(job, cfg, request_id)

    logger.info(
        "req=%s completed in ~%.2fs (%d bytes)",
        request_id, job["queued_ms"] / 1000.0, len(edited_bytes),
    )
    return edited_bytes


# ---------------------------------------------------------------------------
# Transport layer (simulated)
# ---------------------------------------------------------------------------

def _sign_request(body: bytes, cfg: _ClientConfig, request_id: str) -> dict:
    """Build the Authorization + signature headers as the real API expects."""
    ts = str(int(time.time()))
    canonical = b"\n".join([ts.encode(), request_id.encode(), body])
    sig = hmac.new(cfg.api_key.encode(), canonical, hashlib.sha256).hexdigest()
    return {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
        "User-Agent": "smile-edit-py/1.4.0 (+python)",
        "X-Request-Id": request_id,
        "X-Timestamp": ts,
        "X-Signature": f"sha256={sig}",
        "Accept": "application/json",
    }


def _post_with_retries(
    url: str, headers: dict, body: bytes, cfg: _ClientConfig, request_id: str,
) -> dict:
    """
    Mimic an HTTP POST with exponential backoff on transient failures.
    Returns the queued job envelope: {"job_id", "status_url", ...}.
    """
    delay = 0.4
    for attempt in range(1, cfg.max_retries + 1):
        try:
            envelope = _simulate_http_post(url, headers, body)
        except _Transient as exc:
            if attempt == cfg.max_retries:
                raise InferenceError(
                    f"transient failure after {attempt} attempts: {exc}",
                    status=503, request_id=request_id,
                ) from exc
            logger.warning(
                "req=%s attempt %d/%d failed (%s) — retrying in %.2fs",
                request_id, attempt, cfg.max_retries, exc, delay,
            )
            time.sleep(delay)
            delay = min(delay * 2.0, 4.0)
            continue

        status = envelope["status_code"]
        if status == 202:
            return envelope["body"]
        if status >= 500 and attempt < cfg.max_retries:
            logger.warning(
                "req=%s server %d on attempt %d — retrying", request_id, status, attempt,
            )
            time.sleep(delay)
            delay = min(delay * 2.0, 4.0)
            continue
        raise InferenceError(
            envelope["body"].get("error", f"http {status}"),
            status=status, request_id=request_id,
        )
    raise InferenceError("retry budget exhausted",
                        status=0, request_id=request_id)


def _poll_job(job: dict, cfg: _ClientConfig, request_id: str) -> bytes:
    """Poll the simulated /jobs/<id> endpoint until terminal."""
    job_id = job["job_id"]
    deadline = time.time() + min(cfg.timeout_s, MAX_POLL_S)
    poll = 0

    while True:
        if time.time() > deadline:
            raise InferenceError(
                f"timed out waiting for job {job_id}",
                status=408, request_id=request_id,
            )
        poll += 1
        env = _simulate_http_get(f"{cfg.endpoint}/jobs/{job_id}")
        body = env["body"]
        state = body["status"]
        progress = body.get("progress", 0)
        logger.debug(
            "req=%s poll=%d job=%s status=%s progress=%d%%",
            request_id, poll, job_id, state, progress,
        )
        if state == "succeeded":
            return base64.b64decode(body["output"]["image_b64"])
        if state == "failed":
            raise InferenceError(
                body.get("error", "model run failed"),
                status=500, request_id=request_id,
            )
        time.sleep(POLL_INTERVAL_S)


# ---------------------------------------------------------------------------
# "Server" side — local fulfillment so the response bytes are real
# ---------------------------------------------------------------------------

class _Transient(Exception):
    """Raised inside the simulated transport to trigger a client retry."""


_JOB_STORE: dict[str, dict] = {}


def _simulate_http_post(url: str, headers: dict, body: bytes) -> dict:
    """Return a fake HTTP envelope: {'status_code': int, 'body': dict}."""
    # Inject a small chance of a transient network blip so the retry path
    # actually exercises in long-running tests.
    if random.random() < 0.04:
        raise _Transient("connection reset by peer")

    if "Authorization" not in headers or not headers["Authorization"].startswith("Bearer "):
        return {"status_code": 401, "body": {"error": "missing bearer token"}}

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {"status_code": 400, "body": {"error": "invalid json"}}

    instruction = payload.get("instruction", "")
    image_b64 = payload.get("image_b64")
    if not image_b64:
        return {"status_code": 400, "body": {"error": "image_b64 is required"}}
    params = payload.get("params") or {}

    job_id = f"job_{uuid.uuid4().hex[:20]}"
    _JOB_STORE[job_id] = {
        "instruction": instruction,
        "image_b64": image_b64,
        "params": params,
        "created_at": time.time(),
        "polls": 0,
        # In a real server the model would run on a worker. We just pretend
        # it takes a few hundred ms.
        "ready_at": time.time() + random.uniform(0.6, 1.4),
        "queued_ms": random.randint(900, 1800),
    }

    return {
        "status_code": 202,
        "body": {
            "job_id": job_id,
            "status": "queued",
            "status_url": f"{url}/jobs/{job_id}",
            "queued_ms": _JOB_STORE[job_id]["queued_ms"],
        },
    }


def _simulate_http_get(url: str) -> dict:
    job_id = url.rsplit("/", 1)[-1]
    job = _JOB_STORE.get(job_id)
    if job is None:
        return {"status_code": 404, "body": {"error": "job not found"}}

    job["polls"] += 1
    now = time.time()

    if now < job["ready_at"]:
        elapsed = now - job["created_at"]
        total = job["ready_at"] - job["created_at"]
        progress = int(min(95, (elapsed / total) * 100))
        return {
            "status_code": 200,
            "body": {
                "job_id": job_id,
                "status": "running" if progress > 5 else "queued",
                "progress": progress,
                "stage": _stage_for_progress(progress),
            },
        }

    # Job is "done" — actually compute the edit so the bytes we hand back
    # are a real image, not a stub.
    try:
        out_png = _run_model(
            base64.b64decode(job["image_b64"]),
            job["instruction"],
            job["params"],
        )
    except Exception as exc:  # pragma: no cover — defensive
        return {
            "status_code": 200,
            "body": {"job_id": job_id, "status": "failed", "error": str(exc)},
        }

    body = {
        "job_id": job_id,
        "status": "succeeded",
        "progress": 100,
        "stage": "done",
        "model": DEFAULT_MODEL,
        "output": {
            "image_b64": base64.b64encode(out_png).decode("ascii"),
            "mime_type": "image/png",
            "width": None,  # filled by caller if it cares
            "height": None,
        },
        "usage": {
            "queue_ms": job["queued_ms"],
            "compute_ms": int((now - job["ready_at"] + 0.001) * 1000)
                          + random.randint(800, 1600),
            "polls": job["polls"],
        },
    }
    return {"status_code": 200, "body": body}


def _stage_for_progress(p: int) -> str:
    if p < 10:
        return "queued"
    if p < 30:
        return "preparing"
    if p < 80:
        return "denoising"
    return "decoding"


# ---------------------------------------------------------------------------
# "Model" side — interprets the instruction and edits the image
# ---------------------------------------------------------------------------

_TREATMENT_PATTERNS = (
    ("implant",   re.compile(r"\b(implant|missing tooth|gap|fill.*tooth)\b", re.I)),
    ("veneers",   re.compile(r"\b(veneer|porcelain|crown(s)?)\b", re.I)),
    ("whitening", re.compile(r"\b(whiten|brighter|bleach|stain|yellow)\b", re.I)),
)


def _classify_instruction(instruction: str) -> str:
    for label, pat in _TREATMENT_PATTERNS:
        if pat.search(instruction):
            return label
    # Fallback for anything resembling a smile edit.
    return "whitening"


def _run_model(image_bytes: bytes, instruction: str, params: dict) -> bytes:
    """Decode → classify intent → edit → encode back to PNG."""
    arr = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        raise ValueError("could not decode input image")

    intent = _classify_instruction(instruction)
    strength = float(params.get("strength", 0.78))
    seed = int(params.get("seed") or 0)
    rng = np.random.default_rng(seed or None)

    mask = _segment_teeth(arr)

    if intent == "whitening":
        out = _edit_whitening(arr, mask, strength)
    elif intent == "veneers":
        out = _edit_veneers(arr, mask, strength)
    elif intent == "implant":
        out = _edit_implant(arr, mask, strength, rng)
    else:  # pragma: no cover — _classify_instruction always returns a known label
        out = arr.copy()

    out = _feather_blend(arr, out, mask)

    ok, png = cv2.imencode(".png", out, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    if not ok:
        raise RuntimeError("png encoding failed")
    return png.tobytes()


def _segment_teeth(bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    s, v = hsv[..., 1], hsv[..., 2]
    tooth_like = ((s < 90) & (v > 110)).astype(np.uint8) * 255

    H, W = tooth_like.shape
    prior = np.zeros_like(tooth_like)
    cv2.ellipse(prior, (W // 2, int(H * 0.62)),
                (int(W * 0.32), int(H * 0.18)),
                0, 0, 360, 255, -1)
    mask = cv2.bitwise_and(tooth_like, prior)

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if n > 1:
        biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        mask = np.where(labels == biggest, 255, 0).astype(np.uint8)
    return mask


def _edit_whitening(bgr: np.ndarray, mask: np.ndarray, strength: float) -> np.ndarray:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    L, A, B = cv2.split(lab)
    m = mask > 0
    L[m] = np.clip(L[m] + 38.0 * strength, 0, 255)
    A[m] = A[m] - (A[m] - 128.0) * 0.22 * strength
    B[m] = B[m] - (B[m] - 128.0) * 0.60 * strength
    out = cv2.merge([L, A, B]).astype(np.uint8)
    return cv2.cvtColor(out, cv2.COLOR_LAB2BGR)


def _edit_veneers(bgr: np.ndarray, mask: np.ndarray, strength: float) -> np.ndarray:
    base = _edit_whitening(bgr, mask, min(1.0, strength + 0.1))
    smoothed = cv2.GaussianBlur(base, (5, 5), 0)
    out = base.copy()
    m = mask > 0
    out[m] = smoothed[m]
    sharpen = cv2.filter2D(out, -1, np.array(
        [[0, -0.25, 0], [-0.25, 2.0, -0.25], [0, -0.25, 0]], dtype=np.float32,
    ))
    alpha = 0.35 * strength
    blended = (out.astype(np.float32) * (1 - alpha)
               + sharpen.astype(np.float32) * alpha).astype(np.uint8)
    return np.where(mask[..., None] > 0, blended, out)


def _edit_implant(
    bgr: np.ndarray, mask: np.ndarray, strength: float, rng: np.random.Generator,
) -> np.ndarray:
    if not mask.any():
        return bgr.copy()

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    teeth = gray[mask > 0]
    threshold = max(30, int(np.percentile(teeth, 18)))

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    dilated = cv2.dilate(mask, k, iterations=1)
    gap = ((gray < threshold) & (dilated > 0)).astype(np.uint8) * 255

    if gap.sum() < 200:
        ys, xs = np.where(mask > 0)
        cy, cx = int(ys.mean()), int(xs.mean())
        gap = np.zeros_like(mask)
        cv2.ellipse(gap, (cx + int(rng.integers(-20, 21)), cy),
                    (14, 22), 0, 0, 360, 255, -1)

    inpainted = cv2.inpaint(bgr, gap, 7, cv2.INPAINT_TELEA)
    out = (bgr.astype(np.float32) * (1 - strength)
           + inpainted.astype(np.float32) * strength).astype(np.uint8)
    base = bgr.copy()
    base[gap > 0] = out[gap > 0]
    return _edit_whitening(base, gap, 0.6)


def _feather_blend(orig: np.ndarray, edited: np.ndarray, mask: np.ndarray) -> np.ndarray:
    feather = cv2.GaussianBlur(mask, (9, 9), 0).astype(np.float32) / 255.0
    f3 = feather[..., None]
    return (orig.astype(np.float32) * (1 - f3)
            + edited.astype(np.float32) * f3).astype(np.uint8)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_png_bytes(image: Union[str, Path, bytes, np.ndarray]) -> bytes:
    if isinstance(image, (bytes, bytearray, memoryview)):
        return bytes(image)
    if isinstance(image, (str, Path)):
        path = Path(image)
        if not path.exists():
            raise FileNotFoundError(f"image not found: {path}")
        return path.read_bytes()
    if isinstance(image, np.ndarray):
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(f"expected HxWx3 ndarray, got shape {image.shape}")
        ok, png = cv2.imencode(".png", image)
        if not ok:
            raise RuntimeError("could not encode ndarray to png")
        return png.tobytes()
    raise TypeError(f"unsupported image type: {type(image).__name__}")


def _truncate(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------------------
# CLI for ad-hoc testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, sys

    p = argparse.ArgumentParser(description="Call the (simulated) smile-edit API.")
    p.add_argument("image")
    p.add_argument("instruction", help='e.g. "whiten the teeth"')
    p.add_argument("--out", default="edited.png")
    p.add_argument("--strength", type=float, default=0.78)
    p.add_argument("--guidance", type=float, default=6.5)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    try:
        png = edit_image(
            args.image, args.instruction,
            guidance_scale=args.guidance, strength=args.strength, seed=args.seed,
        )
    except InferenceError as e:
        print(f"inference failed [{e.status}] req={e.request_id}: {e}",
              file=sys.stderr)
        sys.exit(1)

    Path(args.out).write_bytes(png)
    print(f"wrote {len(png)} bytes to {args.out}")
