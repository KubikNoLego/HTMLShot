"""Tests for HTTP API endpoints using TestClient without launching the browser."""

import pytest

from htmlshot.services.cache import render_cache


class TestTemplatesEndpoint:
    def test_lists_discovered_templates(self, client, make_template):
        make_template("demo")
        response = client.get("/templates")
        assert response.status_code == 200
        templates = response.json()["templates"]
        assert len(templates) == 1
        item = templates[0]
        assert item["id"] == "demo"
        assert item["name"] == "Тестовый шаблон"
        assert item["viewport"] == {"width": 320, "height": 180}
        assert item["description"] == "Временный шаблон для тестов"

    def test_empty_list(self, client):
        response = client.get("/templates")
        assert response.status_code == 200
        assert response.json() == {"templates": []}


class TestPreviewEndpoint:
    def test_renders_html_with_context(self, client, make_template):
        make_template("demo")
        response = client.post(
            "/preview", params={"template": "demo"},
            json={"username": "Кубик"},
        )
        assert response.status_code == 200
        # FastAPI сериализует строку в JSON — получаем HTML-строку
        html = response.json()
        assert "<span class=\"username\">Кубик</span>" in html
        assert 'href="data:text/css;base64,' in html

    def test_unknown_template_returns_404(self, client):
        response = client.post(
            "/preview", params={"template": "nope"}, json={})
        assert response.status_code == 404
        assert "nope" in response.json()["detail"]

    def test_missing_context_returns_422(self, client, make_template):
        make_template("demo")
        response = client.post("/preview", params={"template": "demo"})
        assert response.status_code == 422

    def test_missing_template_param_returns_422(self, client, make_template):
        make_template("demo")
        response = client.post("/preview", json={})
        assert response.status_code == 422


class TestRenderEndpoint:
    def test_miss_then_hit(self, client, make_template, renderer_stub):
        make_template("demo")
        payload = {"username": "Кубик"}

        first = client.post("/render", params={"template": "demo"}, json=payload)
        assert first.status_code == 200
        assert first.headers["X-Cache"] == "miss"
        assert first.headers["content-type"].startswith("image/webp")
        assert first.content == b"fake-image-bytes"
        assert len(renderer_stub.calls) == 1

        second = client.post("/render", params={"template": "demo"}, json=payload)
        assert second.headers["X-Cache"] == "hit"
        assert second.content == b"fake-image-bytes"
        # рендер вызван один раз — второй ответ из кэша
        assert len(renderer_stub.calls) == 1
        assert render_cache.hits == 1

    def test_different_context_misses_cache(self, client, make_template, renderer_stub):
        make_template("demo")
        client.post("/render", params={"template": "demo"}, json={"username": "A"})
        response = client.post(
            "/render", params={"template": "demo"}, json={"username": "B"})
        assert response.headers["X-Cache"] == "miss"
        assert len(renderer_stub.calls) == 2

    def test_unknown_template_returns_404(self, client, renderer_stub):
        response = client.post("/render", params={"template": "nope"}, json={})
        assert response.status_code == 404
        assert renderer_stub.calls == []

    def test_renderer_receives_viewport_and_format(self, client, make_template,
                                                   renderer_stub):
        make_template("demo")
        client.post("/render", params={"template": "demo"}, json={"username": "A"})
        call = renderer_stub.calls[0]
        assert call["size"] == {"width": 320, "height": 180}
        assert call["image_format"] is None
        assert call["quality"] is None
        assert call["base_path"].name == "index.htm"

    def test_media_type_follows_manifest_format(self, client, make_template,
                                                renderer_stub):
        manifest = {"entrypoint": "index.htm",
                    "default_format": "png", "default_quality": 90}
        make_template("png_card", manifest=manifest)
        response = client.post(
            "/render", params={"template": "png_card"}, json={"username": "A"})
        assert response.headers["content-type"].startswith("image/png")
        assert renderer_stub.calls[0]["image_format"] == "png"
        assert renderer_stub.calls[0]["quality"] == 90

    def test_missing_context_returns_422(self, client, make_template, renderer_stub):
        make_template("demo")
        response = client.post("/render", params={"template": "demo"})
        assert response.status_code == 422
        assert renderer_stub.calls == []


class TestRenderRawEndpoint:
    def test_renders_arbitrary_html(self, client, renderer_stub):
        response = client.post(
            "/render/raw",
            params={"html": "<h1>Привет</h1>", "width": 640, "height": 360},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/webp")
        assert response.content == b"fake-image-bytes"
        call = renderer_stub.calls[0]
        assert call["html"] == "<h1>Привет</h1>"
        assert call["size"] == {"width": 640, "height": 360}
        assert call["image_format"] is None

    def test_missing_params_return_422(self, client, renderer_stub):
        response = client.post("/render/raw", params={"html": "<p>x</p>"})
        assert response.status_code == 422
        assert renderer_stub.calls == []

