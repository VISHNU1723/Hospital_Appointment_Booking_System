
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


class FileValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        content_type = request.headers.get("content-type", "").lower()

        # Apply these checks only to multipart file uploads.
        if request.method in {"POST", "PUT", "PATCH"} and (
            content_type.startswith("multipart/form-data")
        ):
            content_length = request.headers.get("content-length")

            if content_length:
                try:
                    if int(content_length) > MAX_FILE_SIZE:
                        return JSONResponse(
                            status_code=413,
                            content={"detail": "File upload exceeds the 5 MB limit"},
                        )
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid Content-Length header"},
                    )

            # Check the file's media type after parsing the multipart request.
            form = await request.form()
            for _, value in form.multi_items():
                if hasattr(value, "filename") and value.filename:
                    if value.content_type not in ALLOWED_CONTENT_TYPES:
                        return JSONResponse(
                            status_code=415,
                            content={
                                "detail": (
                                    "Unsupported file type. "
                                    "Allowed types: JPEG, PNG, WEBP"
                                )
                            },
                        )

        return await call_next(request)
