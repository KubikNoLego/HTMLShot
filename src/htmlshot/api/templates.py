from typing import Any

from fastapi import APIRouter, HTTPException, Request

from htmlshot.schemas.template import TemplateManifest
from htmlshot.services.render import ImageRender

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


@router.get("/templates")
def get_templates(request: Request):
    """Retrieve metadata for all currently registered templates.

    Scans the template registry via the TemplateService held in application state
    and returns a summary list including template ID, display name, default viewport
    dimensions, and textual description.

    Args:
        request: The incoming FastAPI request holding the application state.

    Returns:
        A dictionary containing a "templates" key with a list of template metadata objects.
    """
    service = request.app.state.templates
    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "viewport": t.viewport.model_dump(),
                "description": t.description,
            }
            for t in service.list_all()
        ]
    }


@router.post("/preview")
async def preview(request: Request, template: str, context: dict[str, Any]):
    """Render a template with context variables and return the resulting HTML.

    Retrieves the specified template manifest, populates its Jinja2 template
    with the supplied context dictionary, inlines CSS and external assets as needed,
    and returns the processed HTML document string without performing screenshot rendering.

    Args:
        request: The incoming FastAPI request containing the application state.
        template: The unique identifier of the template to render.
        context: A dictionary of key-value variables to interpolate into the template.

    Returns:
        The generated HTML content as a string.

    Raises:
        HTTPException: If the specified template cannot be found.
    """
    manifest = _resolve_template(request, template)
    return await ImageRender.for_template(manifest).render(context)


