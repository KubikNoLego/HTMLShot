from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from htmlshot.schemas.template import TemplateManifest
from htmlshot.services.cache import make_cache_key, render_cache
from htmlshot.services.render import ImageRender, Renderer

router = APIRouter()


def _resolve_template(request: Request, template_id: str) -> TemplateManifest:
    """Retrieve a template manifest by ID or raise an HTTP 404 error.

    Queries the application's TemplateService stored in the application state
    for a manifest matching the provided template identifier.

    Args:
        request: The incoming FastAPI request instance containing app state.
        template_id: The unique identifier of the requested template.

    Returns:
        The matching TemplateManifest instance.

    Raises:
        HTTPException: If no template matching the provided ID is registered.
    """
    manifest = request.app.state.templates.get(template_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    return manifest


@router.post("/render")
async def render(request: Request, template: str, context: dict[str, Any]):
    """Render a template to an image, utilizing the memory LRU cache when possible.

    First checks whether an identical rendering request (same template ID, context data,
    image format, and quality settings) is already present in the LRU cache. If cached,
    returns the cached image bytes with an `X-Cache: hit` response header. Otherwise,
    renders the template to HTML, takes a headless browser screenshot via Playwright,
    stores the binary result into the cache, and returns it with an `X-Cache: miss` header.

    Args:
        request: The incoming FastAPI request holding the application state.
        template: The unique identifier of the template to be rendered.
        context: A dictionary of key-value variables to interpolate into the template.

    Returns:
        A FastAPI Response with the raw image bytes, the appropriate image content-type,
        and cache status headers.

    Raises:
        HTTPException: If the specified template cannot be found.
    """
    manifest = _resolve_template(request, template)

    key = make_cache_key(manifest.id, context,
                         manifest.default_format, manifest.default_quality)
    cached = render_cache.get(key)
    media_type = "image/" + (manifest.default_format or "webp")
    if cached is not None:
        return Response(content=cached, media_type=media_type,
                        headers={"X-Cache": "hit"})

    html = await ImageRender.for_template(manifest).render(context)
    image = await Renderer.render_html(
        html,
        manifest.page_size,
        image_format=manifest.default_format,
        quality=manifest.default_quality,
        base_path=manifest.template_file_path,
    )
    render_cache.set(key, image)
    return Response(content=image, media_type=media_type,
                    headers={"X-Cache": "miss"})


@router.post("/render/raw")
async def render_raw(html: str, width: int, height: int):
    """Render arbitrary raw HTML content directly to a WebP image.

    Takes a standalone HTML string and viewport dimensions, renders the HTML inside
    the headless browser without loading template manifests or utilizing cache,
    and returns the resulting WebP image.

    Args:
        html: The complete HTML markup string to render.
        width: The browser viewport width in pixels.
        height: The browser viewport height in pixels.

    Returns:
        A FastAPI Response containing the generated WebP image bytes.
    """
    image = await Renderer.render_html(html, {"width": width, "height": height})
    return Response(content=image, media_type="image/webp")


