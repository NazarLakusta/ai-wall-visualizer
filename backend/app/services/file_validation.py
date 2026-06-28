ALLOWED_IMAGE_TYPES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
}

ALLOWED_TEXTURE_TYPES = {
    **ALLOWED_IMAGE_TYPES,
    b"RIFF": "image/webp",
}


def detect_mime(data: bytes, allowed: dict[bytes, str]) -> str | None:
    for magic, mime in allowed.items():
        if data.startswith(magic):
            return mime
    if data[:4] == b"RIFF" and len(data) > 12 and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_image_upload(data: bytes, max_bytes: int) -> str:
    if len(data) > max_bytes:
        raise ValueError(f"File too large (max {max_bytes // (1024*1024)} MB)")
    mime = detect_mime(data, ALLOWED_IMAGE_TYPES)
    if not mime:
        raise ValueError("Invalid image format. Allowed: JPG, PNG")
    return mime


def validate_texture_upload(data: bytes, max_bytes: int) -> str:
    if len(data) > max_bytes:
        raise ValueError(f"File too large (max {max_bytes // (1024*1024)} MB)")
    mime = detect_mime(data, ALLOWED_TEXTURE_TYPES)
    if not mime:
        raise ValueError("Invalid texture format. Allowed: JPG, PNG, WEBP")
    return mime
