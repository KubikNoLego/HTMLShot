"""Tests for template manifest Pydantic models and viewport configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from htmlshot.schemas.template import TemplateManifest, ViewportConfig



class TestViewportConfig:
    def test_defaults(self):
        viewport = ViewportConfig()
        assert viewport.width == 800
        assert viewport.height == 600

    @pytest.mark.parametrize("width", [0, -10])
    def test_non_positive_width_rejected(self, width):
        with pytest.raises(ValidationError):
            ViewportConfig(width=width)

    def test_non_positive_height_rejected(self):
        with pytest.raises(ValidationError):
            ViewportConfig(height=0)


class TestTemplateManifest:
    @staticmethod
    def _manifest(**kwargs) -> TemplateManifest:
        data = {"id": "demo", "dir_path": "/tmp/templates/demo"}
        data.update(kwargs)
        return TemplateManifest(**data)

    def test_defaults(self):
        manifest = self._manifest()
        assert manifest.entrypoint == "index.html"
        assert manifest.css == "style.css"
        assert manifest.name == ""
        assert manifest.description == ""
        assert manifest.default_format is None
        assert manifest.default_quality is None

    def test_path_properties(self):
        manifest = self._manifest(entrypoint="index.htm")
        assert manifest.template_dir == Path("/tmp/templates/demo")
        assert manifest.template_file_path == Path("/tmp/templates/demo/index.htm")
        assert manifest.css_file_path == Path("/tmp/templates/demo/style.css")

    def test_loader_name_is_dir_relative(self):
        manifest = self._manifest(entrypoint="index.htm")
        assert manifest.loader_name == "demo/index.htm"

    def test_page_size_from_viewport(self):
        manifest = self._manifest(viewport={"width": 320, "height": 180})
        assert manifest.page_size == {"width": 320, "height": 180}

    def test_viewport_defaults_in_page_size(self):
        assert self._manifest().page_size == {"width": 800, "height": 600}

