from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None

try:
    import mediapipe as mp  # type: ignore
except Exception:  # pragma: no cover
    mp = None


class AiProcessingError(Exception):
    """Base exception for AI processing errors."""


class FaceNotDetectedError(AiProcessingError):
    """Raised when no face is detected in the image."""


class FaceMeshError(AiProcessingError):
    """Raised when face mesh landmarks cannot be computed."""


@dataclass(frozen=True)
class Box:
    x1: int
    y1: int
    x2: int
    y2: int

    def to_dict(self) -> Dict[str, int]:
        return {'x1': self.x1, 'y1': self.y1, 'x2': self.x2, 'y2': self.y2}

    def is_valid(self) -> bool:
        return self.x2 > self.x1 and self.y2 > self.y1


class AiService:
    """
    AI image processing service.

    Responsibilities:
    - Decode image
    - Detect face
    - Extract mouth region using face mesh landmarks
    """

    _thread_local = threading.local()

    # Mouth padding ratios (from notebook)
    _MOUTH_PAD_X = 0.04
    _MOUTH_PAD_Y = 0.04

    # Cache lips indices once (static)
    _FACE_MESH = None
    _LIPS_IDX = []

    if mp is not None and getattr(mp, 'solutions', None) is not None:
        _FACE_MESH = mp.solutions.face_mesh
        _LIPS_IDX = sorted(
            {
                idx
                for pair in _FACE_MESH.FACEMESH_LIPS
                for idx in pair
            }
        )

    @classmethod
    def _ensure_ai_deps(cls) -> None:
        if cv2 is None:
            raise AiProcessingError('OpenCV is not available on this environment.')
        if mp is None or getattr(mp, 'solutions', None) is None:
            raise AiProcessingError('MediaPipe is not available on this environment.')
        if cls._FACE_MESH is None or not cls._LIPS_IDX:
            raise AiProcessingError('MediaPipe face mesh is not available on this environment.')

    @classmethod
    def analyze_smile(cls, image_file) -> Dict[str, object]:
        cls._ensure_ai_deps()
        image_rgb, width, height = cls._read_image(image_file)

        face_box = cls.detect_face(image_rgb, width, height)
        mouth_box, mouth_crop = cls.extract_mouth(image_rgb, width, height)

        return {
            'status': 'success',
            'image_size': {'width': width, 'height': height},
            'face_box': face_box.to_dict(),
            'mouth_box': mouth_box.to_dict(),
            'mouth_crop_available': mouth_crop is not None,
        }

    @classmethod
    def detect_face(cls, image_rgb: np.ndarray, width: int, height: int) -> Box:
        face_detector = cls._get_face_detector()
        result = face_detector.process(image_rgb)

        if not result.detections:
            raise FaceNotDetectedError('No face detected in the image.')

        detection = result.detections[0]
        bbox = detection.location_data.relative_bounding_box

        fx1 = max(0, int(bbox.xmin * width))
        fy1 = max(0, int(bbox.ymin * height))
        fx2 = min(width, int((bbox.xmin + bbox.width) * width))
        fy2 = min(height, int((bbox.ymin + bbox.height) * height))

        face_box = Box(x1=fx1, y1=fy1, x2=fx2, y2=fy2)
        if not face_box.is_valid():
            raise FaceNotDetectedError('Detected face box is invalid.')

        return face_box

    @classmethod
    def extract_mouth(
        cls,
        image_rgb: np.ndarray,
        width: int,
        height: int,
    ) -> Tuple[Box, np.ndarray | None]:
        landmarks = cls.get_landmarks(image_rgb)

        lip_xs = [landmarks[i].x * width for i in cls._LIPS_IDX]
        lip_ys = [landmarks[i].y * height for i in cls._LIPS_IDX]

        lx_min, lx_max = min(lip_xs), max(lip_xs)
        ly_min, ly_max = min(lip_ys), max(lip_ys)

        lip_w = lx_max - lx_min
        lip_h = ly_max - ly_min

        mx1 = max(0, int(lx_min - lip_w * cls._MOUTH_PAD_X))
        my1 = max(0, int(ly_min - lip_h * cls._MOUTH_PAD_Y))
        mx2 = min(width, int(lx_max + lip_w * cls._MOUTH_PAD_X))
        my2 = min(height, int(ly_max + lip_h * cls._MOUTH_PAD_Y))

        mouth_box = Box(x1=mx1, y1=my1, x2=mx2, y2=my2)
        if not mouth_box.is_valid():
            raise FaceMeshError('Mouth region could not be computed.')

        mouth_crop = image_rgb[my1:my2, mx1:mx2].copy() if mouth_box.is_valid() else None

        return mouth_box, mouth_crop

    @classmethod
    def get_landmarks(cls, image_rgb: np.ndarray):
        face_mesh = cls._get_face_mesh()
        result = face_mesh.process(image_rgb)

        if not result.multi_face_landmarks:
            raise FaceMeshError('Face mesh failed. Try a clearer frontal image.')

        return result.multi_face_landmarks[0].landmark

    @classmethod
    def _read_image(cls, image_file) -> Tuple[np.ndarray, int, int]:
        cls._ensure_ai_deps()
        if image_file is None:
            raise AiProcessingError('No image provided.')

        data = image_file.read()
        if not data:
            raise AiProcessingError('Empty image file.')

        image_array = np.frombuffer(data, np.uint8)
        image_bgr = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if image_bgr is None:
            raise AiProcessingError('Unsupported or corrupted image file.')

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        height, width = image_rgb.shape[:2]
        return image_rgb, width, height

    @classmethod
    def _get_face_detector(cls):
        cls._ensure_ai_deps()
        face_detector = getattr(cls._thread_local, 'face_detector', None)
        if face_detector is None:
            mp_fd = mp.solutions.face_detection
            face_detector = mp_fd.FaceDetection(
                model_selection=1,
                min_detection_confidence=0.5,
            )
            cls._thread_local.face_detector = face_detector
        return face_detector

    @classmethod
    def _get_face_mesh(cls):
        cls._ensure_ai_deps()
        face_mesh = getattr(cls._thread_local, 'face_mesh', None)
        if face_mesh is None:
            face_mesh = cls._FACE_MESH.FaceMesh(
                static_image_mode=True,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
            )
            cls._thread_local.face_mesh = face_mesh
        return face_mesh
