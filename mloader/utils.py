import re
import string
from typing import Optional


def is_oneshot(chapter_name: str, chapter_subtitle: str) -> bool:
    for name in (chapter_name, chapter_subtitle):
        name = name.lower()
        if "one" in name and "shot" in name:
            return True
    return False


def chapter_name_to_int(name: str) -> Optional[int]:
    try:
        return int(name.lstrip("#"))
    except ValueError:
        return None


def escape_path(path: str) -> str:
    return re.sub(r"[^\w]+", " ", path).strip(string.punctuation + " ")
