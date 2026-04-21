"""
Smile-preview generation — single-file, multi-provider integration.

Providers (selectable via `AI_PROVIDER` env):
  - 'gemini': Gemini 3 Pro Image (Nano Banana Pro) — paid, requires billing on
    Google AI Studio.
  - 'huggingface': HF Inference Providers router → FLUX.1 Kontext via fal-ai —
    ~$0.10/month free credits on HF, then paid.
  - 'cloudflare': Cloudflare Workers AI → Stable Diffusion 1.5 img2img —
    free tier 10,000 neurons/day (~hundreds of images), no card required.

Each provider exposes `call_<provider>(image_bytes, mime_type, prompt) -> bytes`
returning the edited PNG bytes. A thin dispatcher picks the right one.

Flow:
  - Celery task `generate_smile_preview_task` runs the call off-request so the
    web process is never blocked.
  - DRF views:
      POST /api/ai/smile-preview/          -> dispatches task, returns task_id
      GET  /api/ai/smile-preview/<task_id>/ -> polls progress + result_url

Response shape:
  { "task_id": "...", "status": "pending|progress|success|failure",
    "progress": 0-100, "stage": "queued|preparing|generating|saving|done|error",
    "result_url": "...", "error": "..." }
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import uuid
from typing import Iterable, List

import requests
from celery import shared_task
from celery.result import AsyncResult
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# ─── Constants ───

GEMINI_API_BASE = 'https://generativelanguage.googleapis.com/v1beta/models'
GEMINI_DEFAULT_MODEL = 'gemini-3-pro-image-preview'

HUGGINGFACE_DEFAULT_ENDPOINT = 'https://router.huggingface.co/fal-ai/fal-ai/flux-kontext/dev'

CLOUDFLARE_DEFAULT_MODEL = '@cf/runwayml/stable-diffusion-v1-5-img2img'

VALID_SERVICES = {'veneers', 'whitening', 'implant'}

SERVICE_PROMPTS = {
    'veneers': 'apply natural-looking porcelain veneers to the front teeth',
    'whitening': 'apply a professional teeth whitening effect so the teeth look several shades brighter',
    'implant': 'add realistic dental implants to replace any missing or damaged teeth',
}

# InstructPix2Pix / FLUX Kontext — short, direct edit instructions
SERVICE_INSTRUCTIONS = {
    'veneers': 'give the person natural porcelain veneers on the front teeth',
    'whitening': 'make the teeth much whiter and brighter',
    'implant': 'replace any missing teeth with realistic dental implants',
}

# Stable Diffusion 1.5 img2img — needs token-soup positives + explicit negatives.
# SD does not understand natural language instructions; it responds to noun phrases
# and quality tokens. A negative prompt is critical for targeted edits like whitening.
SD_PROMPTS = {
    'veneers': {
        'positive': (
            'perfect flawless porcelain veneers, bright white straight teeth, '
            'hollywood smile, studio dental photograph, highly detailed teeth, sharp focus'
        ),
        'negative': (
            'crooked teeth, yellow teeth, stained teeth, gaps, missing teeth, deformed face'
        ),
    },
    'whitening': {
        'positive': (
            'sparkling pearly white teeth, professional teeth whitening, extremely bright white smile, '
            'clean shiny teeth, hollywood smile, studio dental photograph, highly detailed teeth, sharp focus'
        ),
        'negative': (
            'yellow teeth, stained teeth, dental plaque, discolored teeth, dark teeth, '
            'dirty teeth, brown teeth, deformed face, blurry'
        ),
    },
    'implant': {
        'positive': (
            'complete full set of healthy teeth, new dental implants, perfect smile, '
            'no missing teeth, bright white teeth, studio dental photograph, highly detailed, sharp focus'
        ),
        'negative': (
            'missing teeth, gaps, broken teeth, decayed teeth, deformed face, blurry'
        ),
    },
}


def _build_sd_prompt_pair(services: Iterable[str]) -> tuple[str, str]:
    """Combine service entries into a single (positive, negative) prompt pair."""
    positives, negatives = [], []
    for s in services:
        positives.append(SD_PROMPTS[s]['positive'])
        negatives.append(SD_PROMPTS[s]['negative'])
    return ', '.join(positives), ', '.join(negatives)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _build_prompt(services: Iterable[str], style: str = 'narrative') -> str:
    """Build a prompt. `style='narrative'` for Gemini, `style='instruction'` for InstructPix2Pix."""
    if style == 'instruction':
        parts = [SERVICE_INSTRUCTIONS[s] for s in services]
        return ' and '.join(parts)

    parts = [SERVICE_PROMPTS[s] for s in services]
    joined = ' and '.join(parts)
    return (
        f'Edit this photo to {joined}. '
        "Keep the person's face shape, skin tone, eyes, hair, clothing and background "
        'completely unchanged — only modify the teeth and smile. '
        'Produce a single photorealistic result image.'
    )


# ─── Gemini HTTP client ───

def call_gemini(image_bytes: bytes, mime_type: str, prompt: str) -> bytes:
    """POST image + prompt to Gemini image model; return the generated PNG bytes."""
    api_key = getattr(settings, 'NANOBANANAPRO_API_KEY', '') or ''
    if not api_key:
        raise RuntimeError('NANOBANANAPRO_API_KEY is not configured')

    payload = {
        'contents': [{
            'parts': [
                {'inline_data': {
                    'mime_type': mime_type,
                    'data': base64.b64encode(image_bytes).decode('ascii'),
                }},
                {'text': prompt},
            ],
        }],
    }
    model = getattr(settings, 'NANOBANANAPRO_MODEL', GEMINI_DEFAULT_MODEL) or GEMINI_DEFAULT_MODEL
    response = requests.post(
        f'{GEMINI_API_BASE}/{model}:generateContent',
        params={'key': api_key},
        json=payload,
        timeout=180,
    )
    if not response.ok:
        raise RuntimeError(f'Gemini API error {response.status_code}: {response.text[:500]}')

    data = response.json()
    candidates = data.get('candidates') or []
    if not candidates:
        raise RuntimeError(f'Gemini returned no candidates: {data}')

    for part in candidates[0].get('content', {}).get('parts', []):
        inline = part.get('inline_data') or part.get('inlineData')
        if inline and inline.get('data'):
            return base64.b64decode(inline['data'])

    raise RuntimeError('Gemini response contained no image data')


# ─── Hugging Face HTTP client ───

def call_huggingface(image_bytes: bytes, mime_type: str, prompt: str) -> bytes:
    """POST image + prompt to the HF Inference Providers router; return the generated PNG bytes.

    Uses FLUX.1 Kontext (an image-editing model) via the fal-ai provider by default.
    Returns the edited image bytes after downloading from the provider's CDN.
    """
    token = getattr(settings, 'HUGGINGFACE_API_TOKEN', '') or ''
    if not token:
        raise RuntimeError('HUGGINGFACE_API_TOKEN is not configured')

    endpoint = getattr(settings, 'HUGGINGFACE_ENDPOINT_URL', HUGGINGFACE_DEFAULT_ENDPOINT) or HUGGINGFACE_DEFAULT_ENDPOINT

    data_url = f'data:{mime_type};base64,{base64.b64encode(image_bytes).decode("ascii")}'
    payload = {'prompt': prompt, 'image_url': data_url}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    response = requests.post(endpoint, headers=headers, json=payload, timeout=180)
    if not response.ok:
        raise RuntimeError(f'HuggingFace API error {response.status_code}: {response.text[:500]}')

    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError(f'HuggingFace returned non-JSON: {response.text[:300]}') from exc

    images = body.get('images') or []
    if not images or not images[0].get('url'):
        raise RuntimeError(f'HuggingFace response contained no image URL: {body}')

    img_url = images[0]['url']
    img_response = requests.get(img_url, timeout=60)
    img_response.raise_for_status()
    return img_response.content


# ─── Cloudflare Workers AI HTTP client ───

def call_cloudflare(image_bytes: bytes, prompt: str, negative_prompt: str = '') -> bytes:
    """POST image + (prompt, negative_prompt) to Cloudflare Workers AI; return PNG bytes.

    Uses `@cf/runwayml/stable-diffusion-v1-5-img2img` — text-guided image editing
    on the free tier (10k neurons/day).
    """
    account_id = getattr(settings, 'CLOUDFLARE_ACCOUNT_ID', '') or ''
    api_token = getattr(settings, 'CLOUDFLARE_API_TOKEN', '') or ''
    if not account_id or not api_token:
        raise RuntimeError('CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN must both be configured')

    model = getattr(settings, 'CLOUDFLARE_MODEL', CLOUDFLARE_DEFAULT_MODEL) or CLOUDFLARE_DEFAULT_MODEL
    url = f'https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}'

    payload = {
        'prompt': prompt,
        'negative_prompt': negative_prompt,
        'image_b64': base64.b64encode(image_bytes).decode('ascii'),
        'strength': 0.6,
        'guidance': 11,
        'num_steps': 20,
    }
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json',
    }

    response = requests.post(url, headers=headers, json=payload, timeout=180)
    if not response.ok:
        raise RuntimeError(f'Cloudflare API error {response.status_code}: {response.text[:500]}')

    content_type = response.headers.get('Content-Type', '')
    if content_type.startswith('image/'):
        return response.content

    # Some CF AI responses wrap the image in JSON — handle that too
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError(f'Cloudflare returned unexpected response: {response.text[:300]}') from exc

    if not body.get('success', True):
        errors = body.get('errors') or [{'message': 'unknown error'}]
        raise RuntimeError(f'Cloudflare API error: {errors[0].get("message", body)}')

    result = body.get('result') or {}
    b64 = result.get('image') or result.get('image_b64')
    if b64:
        return base64.b64decode(b64)

    raise RuntimeError(f'Cloudflare response contained no image: {body}')


# ─── Provider dispatch ───

def _generate_image(image_bytes: bytes, mime_type: str, services: List[str]) -> bytes:
    provider = (getattr(settings, 'AI_PROVIDER', 'gemini') or 'gemini').lower()
    if provider == 'huggingface':
        return call_huggingface(image_bytes, mime_type, _build_prompt(services, style='instruction'))
    if provider == 'cloudflare':
        positive, negative = _build_sd_prompt_pair(services)
        return call_cloudflare(image_bytes, positive, negative)
    if provider == 'gemini':
        return call_gemini(image_bytes, mime_type, _build_prompt(services, style='narrative'))
    raise RuntimeError(f'Unknown AI_PROVIDER: {provider!r}. Use "gemini", "huggingface", or "cloudflare".')


# Backward-compat alias — external imports still work after the refactor
call_nanobananapro = call_gemini


# ─── Celery task ───

@shared_task(bind=True, name='ai.generate_smile_preview')
def generate_smile_preview_task(
    self, image_b64: str, mime_type: str, services: List[str],
) -> dict:
    """Long-running job: calls the configured provider, saves result to MEDIA storage."""
    try:
        self.update_state(state='PROGRESS', meta={'progress': 10, 'stage': 'preparing'})

        image_bytes = base64.b64decode(image_b64)

        self.update_state(state='PROGRESS', meta={'progress': 35, 'stage': 'generating'})

        result_bytes = _generate_image(image_bytes, mime_type, services)

        self.update_state(state='PROGRESS', meta={'progress': 85, 'stage': 'saving'})

        filename = f'smile_previews/{uuid.uuid4().hex}.png'
        saved_path = default_storage.save(filename, ContentFile(result_bytes))

        relative = default_storage.url(saved_path).lstrip('/')
        base = getattr(settings, 'BACKEND_PUBLIC_URL', 'http://localhost:8000').rstrip('/')
        result_url = f'{base}/{relative}'

        return {'progress': 100, 'stage': 'done', 'result_url': result_url}
    except Exception as exc:
        logger.exception('Smile preview generation failed')
        raise RuntimeError(str(exc)) from exc


# ─── DRF views ───

class StartSmilePreviewView(APIView):
    """Accept image + services, dispatch Celery task, return task_id immediately."""

    permission_classes = []

    @swagger_auto_schema(
        operation_id='start_smile_preview',
        operation_summary='Start a Nano Banana Pro smile preview',
        operation_description=(
            'Dispatches a background job to generate an edited image of the patient\'s '
            'smile with the selected dental services applied. Returns a task_id to poll.'
        ),
        manual_parameters=[
            openapi.Parameter(
                'image', in_=openapi.IN_FORM, type=openapi.TYPE_FILE, required=True,
                description='Patient photo (jpg/png, <= 10MB).',
            ),
            openapi.Parameter(
                'services', in_=openapi.IN_FORM, type=openapi.TYPE_STRING, required=True,
                description='Comma-separated services: veneers, whitening, implant (any combination).',
            ),
        ],
        responses={202: openapi.Response('Task dispatched', examples={
            'application/json': {'task_id': 'abc-123', 'status': 'pending', 'progress': 0},
        })},
        consumes=['multipart/form-data'],
        tags=['AI'],
    )
    def post(self, request):
        image_file = request.FILES.get('image')
        services_raw = (request.data.get('services') or '').strip()
        services = [s.strip().lower() for s in services_raw.split(',') if s.strip()]

        if image_file is None:
            return Response({'detail': 'image is required'}, status=status.HTTP_400_BAD_REQUEST)
        if image_file.size > MAX_UPLOAD_BYTES:
            return Response({'detail': 'image exceeds 10MB limit'}, status=status.HTTP_400_BAD_REQUEST)
        if not services:
            return Response({'detail': 'services is required'}, status=status.HTTP_400_BAD_REQUEST)
        invalid = set(services) - VALID_SERVICES
        if invalid:
            return Response(
                {'detail': f'invalid services: {", ".join(sorted(invalid))}. '
                           f'Must be any of: {", ".join(sorted(VALID_SERVICES))}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        image_bytes = image_file.read()
        mime_type = (
            image_file.content_type
            or mimetypes.guess_type(image_file.name or '')[0]
            or 'image/jpeg'
        )

        task = generate_smile_preview_task.delay(
            base64.b64encode(image_bytes).decode('ascii'),
            mime_type,
            services,
        )
        return Response(
            {'task_id': task.id, 'status': 'pending', 'progress': 0, 'stage': 'queued'},
            status=status.HTTP_202_ACCEPTED,
        )


class SmilePreviewStatusView(APIView):
    """Poll task state; returns progress and (when done) result_url."""

    permission_classes = []

    @swagger_auto_schema(
        operation_id='smile_preview_status',
        operation_summary='Poll smile preview progress',
        responses={200: openapi.Response('Status', examples={'application/json': {
            'task_id': 'abc-123', 'status': 'progress', 'progress': 35, 'stage': 'generating',
        }})},
        tags=['AI'],
    )
    def get(self, request, task_id: str):
        result = AsyncResult(task_id)
        state = (result.state or 'PENDING').upper()
        body: dict = {'task_id': task_id, 'status': state.lower()}

        if state == 'PENDING':
            body.update(progress=0, stage='queued')
        elif state == 'PROGRESS':
            info = result.info if isinstance(result.info, dict) else {}
            body.update(progress=info.get('progress', 0), stage=info.get('stage', 'processing'))
        elif state == 'SUCCESS':
            info = result.result if isinstance(result.result, dict) else {}
            body.update(progress=100, stage='done', result_url=info.get('result_url'))
        elif state == 'FAILURE':
            body.update(progress=0, stage='error', error=str(result.info) if result.info else 'Task failed')
        else:
            body.update(progress=0, stage=state.lower())

        return Response(body)
