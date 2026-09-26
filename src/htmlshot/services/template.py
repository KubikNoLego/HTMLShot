import json
from pathlib import Path
from loguru import logger
from htmlshot.schemas.template import TemplateManifest

class TemplateService:
    """Manages template discovery, indexing, and lookup from the templates root folder."""

    def __init__(self, templates_dir: Path):
        """Initialize the template service with the target directory.

        Args:
            templates_dir: The filesystem path where template subdirectories are located.
        """
        self.templates_dir = templates_dir
        self._templates: dict[str, TemplateManifest] = {}

    def discover(self) -> None:
        """Scan the templates directory and populate the registry with valid template manifests.

        Iterates over each directory under `templates_dir`. If a `manifest.json` file is present,
        loads and parses the JSON manifest. Otherwise, looks for an entrypoint HTML file (*.htm*)
        and constructs a default manifest with matching defaults. Verifies that the designated
        entrypoint template file actually exists before registering. Any corrupt manifests
        or missing entrypoints are logged as warnings or errors and skipped.
        """
        self._templates.clear()

        if not self.templates_dir.exists():
            logger.warning(f"Templates directory {self.templates_dir} does not exist.")
            return

        for item in self.templates_dir.iterdir():
            if not item.is_dir():
                continue

            manifest_file = item / "manifest.json"
            try:
                if manifest_file.exists():
                    data = json.loads(manifest_file.read_text())
                else:
                    entrypoint = next((f.name for f in item.glob("*.htm*")), "index.html")
                    data = {"name": item.name, "entrypoint": entrypoint}

                manifest = TemplateManifest(
                    id=item.name,
                    dir_path=str(item),
                    **data)

                if not manifest.template_file_path.exists():
                    logger.warning(f"Template file {manifest.template_file_path} does not exist for template {manifest.id}.")
                    continue

                self._templates[manifest.id] = manifest
                logger.info(f"Discovered template: {manifest.id} at {item}")
            except Exception as e:
                logger.error(f"Error reading manifest for template {item.name}: {e}")

    def get(self, template_id: str) -> TemplateManifest | None:
        """Retrieve a registered template manifest by its unique identifier.

        Args:
            template_id: The identifier (subdirectory name) of the template.

        Returns:
            The matching TemplateManifest if registered, or None if not found.
        """
        return self._templates.get(template_id)

    def list_all(self) -> list[TemplateManifest]:
        """Return a list of all currently discovered and validated template manifests.

        Returns:
            A list containing all TemplateManifest instances stored in the registry.
        """
        return list(self._templates.values())

    def exists(self, template_id: str) -> bool:
        """Check whether a template with the specified identifier is currently registered.

        Args:
            template_id: The identifier of the template to verify.

        Returns:
            True if the template exists in the registry, False otherwise.
        """
        return template_id in self._templates


