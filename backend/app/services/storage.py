import shutil
import uuid
from pathlib import Path

from app.config import settings


class StorageService:
    def __init__(self, base_path: str | None = None):
        self.base = Path(base_path or settings.storage_path)
        self.projects_dir = self.base / "projects"
        self.textures_dir = self.base / "textures"
        self.broadcasts_dir = self.base / "broadcasts"
        self.test_dir = self.base / "test"
        for d in (self.projects_dir, self.textures_dir, self.broadcasts_dir, self.test_dir):
            d.mkdir(parents=True, exist_ok=True)

    def project_dir(self, project_id: int) -> Path:
        path = self.projects_dir / str(project_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def texture_dir(self, store_id: int) -> Path:
        path = self.textures_dir / str(store_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def broadcast_dir(self, store_id: int) -> Path:
        path = self.broadcasts_dir / str(store_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_broadcast_image(self, store_id: int, broadcast_id: int, filename: str, data: bytes) -> str:
        ext = Path(filename).suffix.lower() or ".jpg"
        dest = self.broadcast_dir(store_id) / f"{broadcast_id}{ext}"
        dest.write_bytes(data)
        return str(dest.relative_to(self.base))

    def save_upload(self, project_id: int, filename: str, data: bytes) -> str:
        dest = self.project_dir(project_id) / filename
        dest.write_bytes(data)
        return str(dest.relative_to(self.base))

    def copy_test_project(self, project_id: int) -> dict[str, str]:
        dest = self.project_dir(project_id)
        files: dict[str, str] = {}

        originals = [
            self.test_dir / name
            for name in ("original.jpg", "original.png", "original.jpeg")
            if (self.test_dir / name).exists()
        ]
        if originals:
            src = max(originals, key=lambda p: p.stat().st_size)
            dest_name = src.name
            shutil.copy2(src, dest / dest_name)
            files["original_image"] = str((dest / dest_name).relative_to(self.base))

        mapping = {
            "mask.png": "mask_image",
            "illumination.png": "illumination_image",
            "specular.png": "specular_image",
        }
        for fname, key in mapping.items():
            src = self.test_dir / fname
            if src.exists():
                shutil.copy2(src, dest / fname)
                files[key] = str((dest / fname).relative_to(self.base))

        if "original_image" in files and "illumination_image" not in files:
            from PIL import Image

            orig_path = dest / Path(files["original_image"]).name
            img = Image.open(orig_path)
            illum = self.test_dir / "illumination.png"
            if illum.exists():
                shutil.copy2(illum, dest / "illumination.png")
            else:
                Image.new("L", img.size, 255).save(dest / "illumination.png")
            files["illumination_image"] = str((dest / "illumination.png").relative_to(self.base))

        return files

    def delete_project_files(self, project_id: int) -> None:
        path = self.projects_dir / str(project_id)
        if path.exists():
            shutil.rmtree(path)

    def absolute_path(self, relative: str) -> Path:
        return self.base / relative

    def unique_filename(self, original: str) -> str:
        ext = Path(original).suffix.lower() or ".jpg"
        return f"{uuid.uuid4().hex}{ext}"
