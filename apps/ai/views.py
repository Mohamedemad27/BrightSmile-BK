from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services.ai_service import AiProcessingError, AiService, FaceMeshError, FaceNotDetectedError


class AnalyzeSmileView(APIView):
    """
    Analyze smile image:
    - Face detection
    - Mouth region extraction (lips bounding box)
    """

    @swagger_auto_schema(
        operation_id='analyze_smile',
        operation_description='Detect face and mouth region from a dental image.',
        manual_parameters=[
            openapi.Parameter(
                name='image',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description='Image file (jpg/png).',
            )
        ],
        responses={
            200: openapi.Response(
                description='Analysis successful',
                examples={
                    'application/json': {
                        'status': 'success',
                        'image_size': {'width': 1200, 'height': 900},
                        'face_box': {'x1': 100, 'y1': 120, 'x2': 800, 'y2': 780},
                        'mouth_box': {'x1': 300, 'y1': 520, 'x2': 620, 'y2': 650},
                        'mouth_crop_available': True,
                    }
                },
            ),
            400: openapi.Response(
                description='Invalid request or image',
                examples={'application/json': {'status': 'error', 'message': 'Image file is required.'}},
            ),
            422: openapi.Response(
                description='Face or mouth detection failed',
                examples={'application/json': {'status': 'error', 'message': 'No face detected in the image.'}},
            ),
        },
        consumes=['multipart/form-data'],
        tags=['AI'],
    )
    def post(self, request):
        image_file = request.FILES.get('image')
        if image_file is None:
            return Response(
                {'status': 'error', 'message': 'Image file is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = AiService.analyze_smile(image_file)
            return Response(payload, status=status.HTTP_200_OK)
        except FaceNotDetectedError as exc:
            return Response(
                {'status': 'error', 'message': str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except FaceMeshError as exc:
            return Response(
                {'status': 'error', 'message': str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except AiProcessingError as exc:
            return Response(
                {'status': 'error', 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
