import re
import string
import zipfile
from abc import ABCMeta, abstractmethod
from enum import Enum
from pathlib import Path

from mloader.response_pb2 import Title, Chapter


class Language(Enum):
    eng = 0
    spa = 1


class PageType(Enum):
    single = 0
    left = 1
    right = 2
    double = 3


class ExporterBase(metaclass=ABCMeta):
    def __init__(self, destination: str, title: Title, chapter: Chapter):
        self.destination = destination
        self.title_name = self.escape_path(title.name).title()
        self.is_oneshot = self._is_oneshot(chapter.name, chapter.sub_title)

        self._chapter_prefix = self._format_chapter_prefix(
            self.title_name, chapter.name, title.language
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

    def _format_chapter_prefix(
        self, title_name: str, chapter_name: str, language: int
    ) -> str:
        # https://github.com/Daiz/manga-naming-scheme
        components = [title_name]
        if Language(language) != Language.eng:
            components.append(f"[{Language(language).name}]")
        components.append("-")
        if self.is_oneshot:
            chapter_num = "000"
        else:
            try:
                chapter_num = int(chapter_name.lstrip("#"))
            except ValueError:
                chapter_num = chapter_name
            else:
                prefix = "c" if chapter_num < 1000 else "d"
                chapter_num = f"{prefix}{chapter_num:0>3}"
        components.append(chapter_num)
        components.append("(web)")
        return " ".join(components)

    def _format_chapter_suffix(self) -> str:
        components = []
        if self.is_oneshot:
            components.append("[Oneshot]")
        components.append("[Viz]")
        return " ".join(components)

    def format_page_name(self, page: int, ext=".png") -> str:
        return " ".join(
            (
                self._chapter_prefix,
                f"p{page:0>3}",
                self._chapter_suffix,
                f".{ext.lstrip('.')}",
            )
        )

    def escape_path(self, path: str) -> str:
        return re.sub(r"[^\w]+", " ", path).strip(string.punctuation + " ")

    def close(self):
        pass

    @abstractmethod
    def add_image(self, image_data: bytes, index: int):
        # Todo format merged pages as p001-002
        pass


class RawExporter(ExporterBase):
    def __init__(self, destination: str, title: Title, chapter: Chapter):
        super().__init__(destination, title, chapter)
        self.path = Path(self.destination, self.title_name)
        self.path.mkdir(parents=True, exist_ok=True)

    def add_image(self, image_data: bytes, index: int):
        filename = Path(self.format_page_name(index))
        self.path.joinpath(filename).write_bytes(image_data)


class CBZExporter(ExporterBase):
    def __init__(
        self,
        destination: str,
        title: Title,
        chapter: Chapter,
        compression=zipfile.ZIP_DEFLATED,
    ):
        super().__init__(destination, title, chapter)
        self.path = Path(self.destination, self.title_name)
        self.path.mkdir(parents=True, exist_ok=True)
        self.path = self.path.joinpath(self.chapter_name).with_suffix(".cbz")
        self.archive = zipfile.ZipFile(
            self.path, mode="w", compression=compression
        )

    def add_image(self, image_data: bytes, index: int):
        path = Path(self.chapter_name, self.format_page_name(index))
        self.archive.writestr(path.as_posix(), image_data)

    def close(self):
        self.archive.close()
