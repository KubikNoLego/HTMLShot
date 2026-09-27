from pathlib import Path

from pydantic import BaseModel, Field


class ViewportConfig(BaseModel):
    width: int = Field(gt=0, default=800, description="Viewport width in pixels")
    height: int = Field(gt=0, default=600, description="Viewport height in pixels")


class TemplateManifest(BaseModel):
    id: str
    name: str = ""
    entrypoint: str = "index.html"
    viewport: ViewportConfig = ViewportConfig()
    description: str = ""
    dir_path: str = ""
    default_format: str | None = None
    default_quality: int | None = None

    @property
    def template_dir(self) -> Path:
        """Return the filesystem path to the template's root directory."""
        return Path(self.dir_path)

    @property
    def template_file_path(self) -> Path:
        """Return the absolute or relative path to the template entrypoint file."""
        return self.template_dir / self.entrypoint

    @property
    def loader_name(self) -> str:
        """Return the relative template path formatted for the Jinja2 loader."""
        return f"{self.template_dir.name}/{self.entrypoint}"

    @property
    def page_size(self) -> dict[str, int]:
        """Return the viewport width and height as a dictionary for Playwright."""
        return {"width": self.viewport.width, "height": self.viewport.height}

