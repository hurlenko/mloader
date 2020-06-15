import logging
import re
import string
import sys
import zipfile
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Tuple, Type, Union

import click
import requests

from mloader import __version__ as about
from mloader.response_pb2 import Response

log = logging.getLogger()


def setup_logging():
    handlers = [logging.StreamHandler(sys.stdout)]
    logging.basicConfig(
        handlers=handlers,
        format=(
            "{asctime:^} | {levelname: ^8} | "
            "{filename: ^14} {lineno: <4} | {message}"
        ),
        style="{",
        datefmt="%d.%m.%Y %H:%M:%S",
        level=logging.INFO,
    )


class ExporterBase(metaclass=ABCMeta):
    def __init__(self, destination: str, title: str, chapter: str):
        self.destination = destination
        self.title = self.escape_path(title)
        self.chapter = self.escape_path(chapter)

    def format_image_name(self, index: int, ext=".png") -> str:
        return f"{self.title}-{index:0>3}.{ext}"

    def escape_path(self, path: str) -> str:
        return re.sub(r"[^\w]+", " ", path).strip(string.punctuation + " ")

    def close(self):
        pass

    @abstractmethod
    def add_image(self, image_data: bytes, index: int):
        pass


class RawExporter(ExporterBase):
    def __init__(self, destination: str, title: str, chapter: str):
        super().__init__(destination, title, chapter)
        self.path = Path(self.destination, self.title, self.chapter)
        self.path.mkdir(parents=True, exist_ok=True)

    def add_image(self, image_data: bytes, index: int):
        filename = Path(self.format_image_name(index))
        self.path.joinpath(filename).write_bytes(image_data)


class CBZExporter(ExporterBase):
    def __init__(
        self,
        destination: str,
        title: str,
        chapter: str,
        compression=zipfile.ZIP_DEFLATED,
    ):
        super().__init__(destination, title, chapter)
        self.path = Path(self.destination, self.title)
        self.path.mkdir(parents=True, exist_ok=True)
        self.path = self.path.joinpath(
            f"{self.title}-{self.chapter}"
        ).with_suffix(".cbz")
        self.archive = zipfile.ZipFile(
            self.path, mode="w", compression=compression
        )

    def add_image(self, image_data: bytes, index: int):
        self.archive.writestr(self.format_image_name(index), image_data)

    def close(self):
        self.archive.close()


class MangaLoader:
    def __init__(self, exporter_cls: Type[ExporterBase] = RawExporter):
        self.exporter_cls = exporter_cls
        self.session = requests.session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; "
                "rv:72.0) Gecko/20100101 Firefox/72.0"
            }
        )
        self._api_url = "https://jumpg-webapi.tokyo-cdn.com/api/manga_viewer"

    def _decrypt_image(self, url: str, encryption_hex: str) -> bytearray:
        resp = self.session.get(url)
        data = bytearray(resp.content)
        key = bytes.fromhex(encryption_hex)
        a = len(key)
        for s in range(len(data)):
            data[s] ^= key[s % a]
        return data

    def _load_pages(
        self, chapter_id: Union[str, int], quality: str, split: bool
    ) -> Response:
        resp = self.session.get(
            self._api_url,
            params={
                "chapter_id": chapter_id,
                "split": "yes" if split else "no",
                "img_quality": quality,
            },
        )
        response_proto = Response()
        return response_proto.FromString(resp.content)

    def _format_filename(self, title, chapter):
        return f"{title}-{chapter}"

    def download_chapter(
        self,
        chapter_id: Union[str, int],
        dst: str,
        quality: str = "super_high",
        split: bool = False,
    ):
        response = self._load_pages(chapter_id, quality, split)
        viewer = response.success.mangaviewer
        pages = [p.mangaPage for p in viewer.pages if p.mangaPage.image_url]
        title = viewer.titleName
        chapter_name = viewer.chapterName
        exporter: ExporterBase = self.exporter_cls(dst, title, chapter_name)
        log.info("Manga: %s", title)
        log.info("Chapter: %s", chapter_name)
        log.info("Found pages: %s", len(pages))
        with click.progressbar(
            pages, label=chapter_name, show_pos=True,
        ) as pbar:
            for i, page in enumerate(pbar, 1):
                image_blob = self._decrypt_image(
                    page.image_url, page.encryption_key
                )
                exporter.add_image(image_blob, i)

        exporter.close()


def validate_chapters(ctx, param, value):
    if not value:
        return value
    res = []
    for item in value:
        if "title" in value:
            raise click.BadParameter(
                f"Title downloads are not supported: {item}. "
                f"Use chapter links - <site>/viewer/<chapter_id>"
            )
        match = re.search(r"viewer/(\d+)", item)
        if match:
            item = match.group(1)
        try:
            res.append(int(item))
        except ValueError:
            raise click.BadParameter(
                "Chapter must be an integer or a link in format "
                "<site>/viewer/<chapter_id>"
            )

    return res


@click.command(short_help=about.__description__)
@click.option(
    "--out",
    "-o",
    "out_dir",
    type=click.Path(exists=False, writable=True),
    metavar="<directory>",
    default="mangaplus_downloads",
    show_default=True,
    help="Save directory (not a file)",
    envvar="MLOADER_EXTRACT_OUT_DIR",
)
@click.option(
    "--raw",
    "-r",
    is_flag=True,
    default=False,
    show_default=True,
    help="Save raw images",
    envvar="MLOADER_RAW",
)
@click.option(
    "--quality",
    "-q",
    default="super_high",
    type=click.Choice(["super_high", "high", "low"]),
    show_default=True,
    help="Image quality",
    envvar="MLOADER_QUALITY",
)
@click.option(
    "--split",
    "-s",
    is_flag=True,
    default=False,
    show_default=True,
    help="Split combined images",
    envvar="MLOADER_SPLIT",
)
@click.argument("chapters", nargs=-1, callback=validate_chapters)
def main(
    out_dir: str, chapters: Tuple[int], raw: bool, quality: str, split: bool
):
    setup_logging()
    log.info("Started export")

    for chapter_id in chapters:
        loader = MangaLoader(RawExporter if raw else CBZExporter)
        try:
            loader.download_chapter(chapter_id, out_dir, quality, split)
        except Exception:
            log.exception("Failed to download_chapter images")
    log.info("SUCCESS")
