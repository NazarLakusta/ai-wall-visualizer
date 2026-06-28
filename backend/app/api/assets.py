from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/{file_path:path}")
async def serve_asset(file_path: str):
    base = Path(settings.storage_path).resolve()
    target = (base / file_path).resolve()
    if not str(target).startswith(str(base)) or not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target)
