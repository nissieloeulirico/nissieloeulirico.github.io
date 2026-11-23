#!/usr/bin/env python3
"""Copy WordPress-hosted images referenced by this site's HTML/CSS into the repo.

Only the author's own WordPress media host is accepted. Existing page content is
preserved; image URLs are replaced with local /assets/wordpress-images/ paths.
"""
from __future__ import annotations

import hashlib
import mimetypes
import re
import time
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://nissieloeulirico.wordpress.com"
DEST = ROOT / "assets" / "wordpress-images"
ALLOWED_HOST = "nissieloeulirico.wordpress.com"

# Match image URLs in src, srcset, data-orig-file, inline styles and CSS.
IMAGE_URL = re.compile(
    r'(?P<url>(?:https?:)?//nissieloeulirico\\.wordpress\\.com/wp-content/uploads/[^\\s"\\'<>),]+?'
    r'\\.(?:png|jpe?g|webp|gif)(?:\\?[^\\s"\\'<>),]+)?'
    r'|/wp-content/uploads/[^\\s"\\'<>),]+?\\.(?:png|jpe?g|webp|gif)(?:\\?[^\\s"\\'<>),]+)?)',
    re.IGNORECASE,
)

def canonical_url(raw: str) -> str:
    if raw.startswith("//"):
        url = "https:" + raw
    elif raw.startswith("/"):
        url = urljoin(BASE, raw)
    else:
        url = raw
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != ALLOWED_HOST:
        raise ValueError(f"Host de imagem não autorizado: {url}")
    return url

def local_name(url: str) -> str:
    parts = urlsplit(url)
    suffix = Path(parts.path).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        suffix = mimetypes.guess_extension("image/jpeg") or ".jpg"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    return f"{digest}{suffix}"

def download(url: str, target: Path) -> None:
    if target.exists() and target.stat().st_size:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for attempt in range(4):
        try:
            request = Request(url, headers={"User-Agent": "NissielSiteImageMigration/1.0"})
            with urlopen(request, timeout=90) as response:
                data = response.read()
            if not data:
                raise RuntimeError(f"Arquivo vazio: {url}")
            target.write_bytes(data)
            return
        except (URLError, HTTPError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Falha ao baixar {url}: {last_error}")

def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    files = [
        p for p in ROOT.rglob("*")
        if p.is_file()
        and p.suffix.lower() in {".html", ".htm", ".css"}
        and ".git" not in p.parts
        and ".github" not in p.parts
        and "assets/wordpress-images" not in p.as_posix()
    ]
    downloaded: set[str] = set()
    rewritten = 0

    for file in files:
        original = file.read_text(encoding="utf-8")
        def replace(match: re.Match[str]) -> str:
            nonlocal rewritten
            raw = match.group("url")
            url = canonical_url(raw)
            name = local_name(url)
            target = DEST / name
            download(url, target)
            downloaded.add(name)
            rewritten += 1
            return "/assets/wordpress-images/" + name

        updated = IMAGE_URL.sub(replace, original)
        if updated != original:
            file.write_text(updated, encoding="utf-8")

    print(f"Arquivos HTML/CSS examinados: {len(files)}")
    print(f"Referências locais criadas: {rewritten}")
    print(f"Imagens únicas copiadas: {len(downloaded)}")
    print(f"Diretório: {DEST.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
