import re
import string
import zipfile
from abc import ABCMeta, abstractmethod
from pathlib import Path

from mloader.response_pb2 import Title, Chapter


class ExporterBase(metaclass=ABCMeta):
    def __init__(self, destination: str, title: Title, chapter: Chapter):
        self.destination = destination
        self.title = title
        self.chapter = chapter
        self.title_name = self.escape_path(title.name)
        self.chapter_name = self.escape_path(chapter.name)

    def format_title_name(self, index: int, ext=".png") -> str:
        return f"{self.title_name}-{index:0>3}.{ext.lstrip('.')}"

    def format_page_name(self, index: int, ext=".png") -> str:
        return f"{self.title_name}-{index:0>3}.{ext.lstrip('.')}"

    def escape_path(self, path: str) -> str:
        return re.sub(r"[^\w]+", " ", path).strip(string.punctuation + " ")

    def close(self):
        pass

    @abstractmethod
    def add_image(self, image_data: bytes, index: int):
        pass


class RawExporter(ExporterBase):
    def __init__(self, destination: str, title: Title, chapter: Chapter):
        super().__init__(destination, title, chapter)
        self.path = Path(self.destination, self.title_name, self.chapter_name)
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
        self.path = self.path.joinpath(
            f"{self.title_name}-{self.chapter_name}"
        ).with_suffix(".cbz")
        self.archive = zipfile.ZipFile(
            self.path, mode="w", compression=compression
        )

    def add_image(self, image_data: bytes, index: int):
        path = Path(self.title_name, self.format_page_name(index))
        self.archive.writestr(path.as_posix(), image_data)

    def close(self):
        self.archive.close()
