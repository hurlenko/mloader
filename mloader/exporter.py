import zipfile
from abc import ABCMeta, abstractmethod
from itertools import chain
from pathlib import Path
from typing import Union, Optional

from mloader.constants import Language
from mloader.response_pb2 import Title, Chapter
from mloader.utils import escape_path, is_oneshot, chapter_name_to_int


class ExporterBase(metaclass=ABCMeta):
    def __init__(
        self,
        destination: str,
        title: Title,
        chapter: Chapter,
        next_chapter: Optional[Chapter] = None,
        add_chapter_title: bool = False,
        add_chapter_subdir: bool = False
    ):
        self.destination = destination
        self.add_chapter_title = add_chapter_title
        self.add_chapter_subdir = add_chapter_subdir
        self.title_name = escape_path(title.name).title()
        self.is_oneshot = is_oneshot(chapter.name, chapter.sub_title)
        self.is_extra = self._is_extra(chapter.name)

        self._extra_info = []

        if self.is_oneshot:
            self._extra_info.append("[Oneshot]")

        if self.add_chapter_title:
            self._extra_info.append(f"[{escape_path(chapter.sub_title)}]")

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

    def _is_extra(self, chapter_name: str) -> bool:
        return chapter_name.strip("#") == "ex"

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
            chapter_num = chapter_name_to_int(next_chapter_name)
            if chapter_num is not None:
                chapter_num -= 1
                prefix = "c" if chapter_num < 1000 else "d"
        else:
            chapter_num = chapter_name_to_int(chapter_name)
            if chapter_num is not None:
                prefix = "c" if chapter_num < 1000 else "d"

        if chapter_num is None:
            chapter_num = escape_path(chapter_name)

        components.append(f"{prefix}{chapter_num:0>3}{suffix}")
        components.append("(web)")
        return " ".join(components)

    def _format_chapter_suffix(self) -> str:
        return " ".join(chain(self._extra_info, ["[Unknown]"]))

    def format_page_name(self, page: Union[int, range], ext=".jpg") -> str:
        if isinstance(page, range):
            page = f"p{page.start:0>3}-{page.stop:0>3}"
        else:
            page = f"p{page:0>3}"

        ext = ext.lstrip(".")

        return f"{self._chapter_prefix} - {page} {self._chapter_suffix}.{ext}"

    def close(self):
        pass

    @abstractmethod
    def add_image(self, image_data: bytes, index: Union[int, range]):
        pass

    @abstractmethod
    def skip_image(self, index: Union[int, range]) -> bool:
        pass


class RawExporter(ExporterBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.path = Path(self.destination, self.title_name)
        self.path.mkdir(parents=True, exist_ok=True)
        if self.add_chapter_subdir:
            self.path = self.path.joinpath(self.chapter_name)
            self.path.mkdir(parents=True, exist_ok=True)

    def add_image(self, image_data: bytes, index: Union[int, range]):
        filename = Path(self.format_page_name(index))
        self.path.joinpath(filename).write_bytes(image_data)

    def skip_image(self, index: Union[int, range]) -> bool:
        filename = Path(self.format_page_name(index))
        return self.path.joinpath(filename).exists()


class CBZExporter(ExporterBase):
    def __init__(self, compression=zipfile.ZIP_DEFLATED, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.path = Path(self.destination, self.title_name)
        self.path.mkdir(parents=True, exist_ok=True)
        self.path = self.path.joinpath(self.chapter_name).with_suffix(".cbz")
        self.skip_all_images = self.path.exists()
        if not self.skip_all_images:
            self.archive = zipfile.ZipFile(
                self.path, mode="w", compression=compression
            )

    def add_image(self, image_data: bytes, index: Union[int, range]):
        if self.skip_all_images:
            return
        path = Path(self.chapter_name, self.format_page_name(index))
        self.archive.writestr(path.as_posix(), image_data)

    def skip_image(self, index: Union[int, range]) -> bool:
        return self.skip_all_images

    def close(self):
        if self.skip_all_images:
            return
        self.archive.close()
