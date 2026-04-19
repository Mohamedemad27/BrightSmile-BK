from rest_framework.renderers import JSONRenderer


class EnvelopeJSONRenderer(JSONRenderer):
    """
    Wrap all successful API responses in a consistent envelope:
    {
      "data": ...,
      "error": null,
      "message": ""
    }
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            payload = {"data": None, "error": None, "message": ""}
            return super().render(payload, accepted_media_type, renderer_context)

        # Keep standardized paginated shape untouched:
        # {"data": [...], "meta": {...}}
        if isinstance(data, dict) and "data" in data and "meta" in data and "error" not in data:
            return super().render(data, accepted_media_type, renderer_context)

        if isinstance(data, dict) and {"data", "error", "message"}.issubset(data.keys()):
            return super().render(data, accepted_media_type, renderer_context)

        payload = {"data": data, "error": None, "message": ""}
        return super().render(payload, accepted_media_type, renderer_context)
