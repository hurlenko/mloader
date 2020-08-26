import re
import string
import zipfile
from abc import ABCMeta, abstractmethod
from enum import Enum
from itertools import chain
from pathlib import Path
from typing import Union, Optional

from mloader.response_pb2 import Title, Chapter


class Language(Enum):
    eng = 0
    spa = 1


class ExporterBase(metaclass=ABCMeta):
    def __init__(
        self,
        destination: str,
        title: Title,
        chapter: Chapter,
        next_chapter: Optional[Chapter] = None,
    ):
        self.destination = destination
        self.title_name = self.escape_path(title.name).title()
        self.is_oneshot = self._is_oneshot(chapter.name, chapter.sub_title)
        self.is_extra = chapter.name == "ex"

        self._extra_info = []

        if self.is_oneshot:
            self._extra_info.append("[Oneshot]")

        if self.is_extra:
            self._extra_info.append(f"[{self.escape_path(chapter.sub_title)}]")

        self._chapter_prefix = self._format_chapter_prefix(
            self.title_name,
            chapter.name,
            title.language,
            next_chapter and next_chapter.name,
        )
        self._chapter_suffix = self._format_chapter_suffix()
        self.chapter_name = " ".join(
            (self._chapter_prefix, self._chapter_suffix)
        )

    def _is_oneshot(self, chapter_name: str, chapter_subtitle: str) -> bool:
        for name in (chapter_name, chapter_subtitle):
            name = name.lower()
            if "one" in name and "shot" in name:
                return True
        return False

    def _chapter_name_to_int(self, name: str) -> Optional[int]:
        try:
            return int(name.lstrip("#"))
        except ValueError:
            return None

    def _format_chapter_prefix(
        self,
        title_name: str,
        chapter_name: str,
        language: int,
        next_chapter_name: Optional[str] = None,
    ) -> str:
        # https://github.com/Daiz/manga-naming-scheme
        components = [title_name]
        if Language(language) != Language.eng:
            components.append(f"[{Language(language).name}]")
        components.append("-")
        suffix = ""
        prefix = ""
        if self.is_oneshot:
            chapter_num = 0
        elif self.is_extra and next_chapter_name:
            suffix = "x1"
            chapter_num = self._chapter_name_to_int(next_chapter_name)
            if chapter_num is not None:
                chapter_num -= 1
                prefix = "c" if chapter_num < 1000 else "d"
        else:
            chapter_num = self._chapter_name_to_int(chapter_name)
            if chapter_num is not None:
                prefix = "c" if chapter_num < 1000 else "d"

        if chapter_num is None:
            chapter_num = self.escape_path(chapter_name)

        components.append(f"{prefix}{chapter_num:0>3}{suffix}")
        components.append("(web)")
        return " ".join(components)

    def _format_chapter_suffix(self) -> str:
        return " ".join(chain(self._extra_info, ["[Viz]"]))

    def format_page_name(self, page: Union[int, range], ext=".jpg") -> str:
        if isinstance(page, range):
            page = f"p{page.start:0>3}-{page.stop:0>3}"
        else:
            page = f"p{page:0>3}"

        ext = ext.lstrip('.')

        return f"{self._chapter_prefix} - {page} {self._chapter_suffix}.{ext}"

    def escape_path(self, path: str) -> str:
        return re.sub(r"[^\w]+", " ", path).strip(string.punctuation + " ")

    def close(self):
        pass

    @abstractmethod
    def add_image(self, image_data: bytes, index: Union[int, range]):
        pass


class RawExporter(ExporterBase):
    def __init__(
        self,
        destination: str,
        title: Title,
        chapter: Chapter,
        next_chapter: Optional[Chapter] = None,
    ):
        super().__init__(destination, title, chapter, next_chapter)
        self.path = Path(self.destination, self.title_name)
        self.path.mkdir(parents=True, exist_ok=True)

    def add_image(self, image_data: bytes, index: Union[int, range]):
        filename = Path(self.format_page_name(index))
        self.path.joinpath(filename).write_bytes(image_data)


class CBZExporter(ExporterBase):
    def __init__(
        self,
        destination: str,
        title: Title,
        chapter: Chapter,
        next_chapter: Optional[Chapter] = None,
        compression=zipfile.ZIP_DEFLATED,
    ):
        super().__init__(destination, title, chapter, next_chapter)
        self.path = Path(self.destination, self.title_name)
        self.path.mkdir(parents=True, exist_ok=True)
        self.path = self.path.joinpath(self.chapter_name).with_suffix(".cbz")
        self.archive = zipfile.ZipFile(
            self.path, mode="w", compression=compression
        )

    def add_image(self, image_data: bytes, index: Union[int, range]):
        path = Path(self.chapter_name, self.format_page_name(index))
        self.archive.writestr(path.as_posix(), image_data)

    def close(self):
        self.archive.close()
