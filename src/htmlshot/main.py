from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from htmlshot.api import include_routes
from htmlshot.config import PROJECT_ROOT, load_settings
from htmlshot.services.render import Renderer
from htmlshot.services.template import TemplateService

settings = load_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycles.

    Initializes the headless browser rendering engine, scans and loads
    all available templates into the application state on startup, and
    gracefully terminates the browser instance upon application shutdown.

    Args:
        app: The FastAPI application instance being started or stopped.

    Yields:
        None: Control is yielded to the running application.
    """
    await Renderer.start()
    templates = TemplateService(PROJECT_ROOT / "src" / "htmlshot" / "templates")
    templates.discover()
    app.state.templates = templates
    yield
    await Renderer.close()


app = FastAPI(
    lifespan=lifespan,
    title=settings.title,
    description="Sevice to make images from HTML",
)

include_routes(app)

if __name__ == "__main__":
    uvicorn.run(
        "htmlshot.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )


