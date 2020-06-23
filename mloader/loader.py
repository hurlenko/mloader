import logging
from enum import Enum
from itertools import chain
from typing import Type, Union, List, Dict, Set

import click
from requests import Session

from mloader.exporter import ExporterBase, CBZExporter
from mloader.response_pb2 import Response, MangaViewer, TitleDetailView

log = logging.getLogger()

MangaList = Dict[int, Set[int]]


class Language(Enum):
    eng = 0
    spa = 1


class PageType(Enum):
    single = 0
    left = 1
    right = 2
    double = 3


class ChapterType(Enum):
    latest = 0
    sequence = 1
    nosequence = 2


class MangaLoader:
    def __init__(
        self,
        exporter_cls: Type[ExporterBase] = CBZExporter,
        quality: str = "super_high",
        split: bool = False,
    ):
        self.exporter_cls = exporter_cls
        self.quality = quality
        self.split = split
        self._api_url = "https://jumpg-webapi.tokyo-cdn.com"
        self.session = Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; "
                "rv:72.0) Gecko/20100101 Firefox/72.0"
            }
        )

    def _decrypt_image(self, url: str, encryption_hex: str) -> bytearray:
        resp = self.session.get(url)
        data = bytearray(resp.content)
        key = bytes.fromhex(encryption_hex)
        a = len(key)
        for s in range(len(data)):
            data[s] ^= key[s % a]
        return data

    def _load_pages(self, chapter_id: Union[str, int]) -> MangaViewer:
        resp = self.session.get(
            f"{self._api_url}/api/manga_viewer",
            params={
                "chapter_id": chapter_id,
                "split": "yes" if self.split else "no",
                "img_quality": self.quality,
            },
        )
        return Response.FromString(resp.content).success.manga_viewer

    def _get_title_details(self, title_id: Union[str, int]) -> TitleDetailView:
        resp = self.session.get(
            f"{self._api_url}/api/title_detail", params={"title_id": title_id},
        )
        return Response.FromString(resp.content).success.title_detail_view

    def _normalize_ids(
        self, title_ids: List[int], chapter_ids: List[int]
    ) -> MangaList:
        title_ids = set(title_ids)
        chapter_ids = set(chapter_ids)
        mangas = {}
        for cid in chapter_ids:
            viewer = self._load_pages(cid)
            title_id = viewer.title_id
            if title_id in title_ids:
                title_ids.remove(title_id)
                mangas.setdefault(title_id, set()).update(
                    x.chapter_id for x in viewer.chapters
                )
            else:
                mangas.setdefault(title_id, set()).add(cid)

        for tid in title_ids:
            title_details = self._get_title_details(tid)
            mangas[tid] = {
                x.chapter_id
                for x in chain(
                    title_details.first_chapter_list,
                    title_details.last_chapter_list,
                )
            }

        return mangas

    def _download(
        self, manga_list: MangaList, dst: str,
    ):
        for title_id, chapters in manga_list.items():
            title_details = self._get_title_details(title_id)
            title_name = title_details.title_name.name
            log.info("Manga: %s", title_name)
            log.info("Author: %s", title_details.title_name.author)

            for chapter_id in chapters:
                viewer = self._load_pages(chapter_id)
                chapter = next(
                    x for x in viewer.chapters if x.chapter_id == chapter_id
                )
                chapter_name = viewer.chapter_name
                log.info("Chapter: %s %s", chapter_name, chapter.sub_title)
                exporter = self.exporter_cls(dst, title_name, chapter_name)
                pages = [
                    p.manga_page for p in viewer.pages if p.manga_page.image_url
                ]

                with click.progressbar(
                    pages, label=chapter_name, show_pos=True
                ) as pbar:
                    for i, page in enumerate(pbar, 0):
                        image_blob = self._decrypt_image(
                            page.image_url, page.encryption_key
                        )
                        exporter.add_image(image_blob, i)

                exporter.close()

    def download_chapter(self, chapter_id: int, dst: str):
        self._download(self._normalize_ids([100059], []), dst)

    def download_title(self, title_id: int, dst: str):
        pass
