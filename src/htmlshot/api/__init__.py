
from fastapi import FastAPI


def include_routes(app: FastAPI) -> None:
    """Register all application API routers with the FastAPI application.

    Mounts the render-related routes (HTML and raw rendering endpoints)
    and template management routes onto the provided FastAPI instance.

    Args:
        app: The FastAPI application instance to attach routers to.
    """
    from .render import router as render_router
    from .templates import router as templates_router
    app.include_router(render_router)
    app.include_router(templates_router)

