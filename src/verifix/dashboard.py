"""Build one self-contained interface for Lambda and GitHub Pages.

Keeping JavaScript out of Python string literals prevents escape corruption.
No runtime CDN, font, or build-service dependency is required.
"""
from pathlib import Path

WEB_DIR = Path(__file__).with_name("web")


def build_dashboard() -> str:
    template = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    return template.replace("/* INLINE_CSS */", (WEB_DIR / "app.css").read_text(encoding="utf-8")).replace(
        "/* INLINE_JS */", (WEB_DIR / "app.js").read_text(encoding="utf-8")
    )
