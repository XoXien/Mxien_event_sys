"""Give changed styles and scripts new URLs when a project ZIP is upgraded."""

import hashlib
from functools import lru_cache
from pathlib import Path

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@lru_cache(maxsize=256)
def _content_version(filename, modified, size):
    # The file metadata forms the cache key; only changed files need to be read again.
    return hashlib.sha256(Path(filename).read_bytes()).hexdigest()[:16]


@register.simple_tag
def asset(path):
    url = static(path)
    filename = finders.find(path)
    if filename:
        info = Path(filename).stat()
        version = _content_version(filename, info.st_mtime_ns, info.st_size)
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}v={version}"
    return url
