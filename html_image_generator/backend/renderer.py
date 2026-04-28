from jinja2 import Environment, BaseLoader
from playwright.sync_api import sync_playwright
import tempfile
import os
from pathlib import Path


def render_html_to_image(
    html_template: str,
    values: dict,
    output_path: str,
    width: int = 1200,
    height: int = 630,
):
    env = Environment(loader=BaseLoader(), autoescape=False)
    rendered_html = env.from_string(html_template).render(**values)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(rendered_html)
        tmp_path = tmp.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(Path(tmp_path).as_uri(), wait_until="networkidle")

            is_jpeg = output_path.lower().endswith((".jpg", ".jpeg"))
            kwargs = {
                "path": output_path,
                "clip": {"x": 0, "y": 0, "width": width, "height": height},
                "type": "jpeg" if is_jpeg else "png",
            }
            if is_jpeg:
                kwargs["quality"] = 92

            page.screenshot(**kwargs)
            browser.close()
    finally:
        os.unlink(tmp_path)
