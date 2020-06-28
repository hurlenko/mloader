import logging
from enum import Enum
from functools import lru_cache
from itertools import chain, count
from typing import Type, Union, Dict, Set, Collection, Optional

import click
from requests import Session

from mloader.exporter import ExporterBase, CBZExporter
from mloader.response_pb2 import Response, MangaViewer, TitleDetailView

log = logging.getLogger()

MangaList = Dict[int, Set[int]]


class ChapterType(Enum):
    latest = 0
    sequence = 1
    nosequence = 2


class PageType(Enum):
    single = 0
    left = 1
    right = 2
    double = 3


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

    @lru_cache(None)
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

    @lru_cache(None)
    def _get_title_details(self, title_id: Union[str, int]) -> TitleDetailView:
        resp = self.session.get(
            f"{self._api_url}/api/title_detail", params={"title_id": title_id},
        )
        return Response.FromString(resp.content).success.title_detail_view

    def _normalize_ids(
        self, title_ids: Collection[int], chapter_ids: Collection[int],
    ) -> MangaList:
        if not any((title_ids, chapter_ids)):
            raise ValueError("Expected at least one title or chapter id")
        title_ids = set(title_ids or [])
        chapter_ids = set(chapter_ids or [])
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

    def _download(self, manga_list: MangaList, dst: str):
        manga_num = len(manga_list)
        for title_index, (title_id, chapters) in enumerate(
            manga_list.items(), 1
        ):
            title = self._get_title_details(title_id).title

            title_name = title.name
            log.info(f"{title_index}/{manga_num}) Manga: {title_name}")
            log.info("    Author: %s", title.author)

            chapter_num = len(chapters)
            for chapter_index, chapter_id in enumerate(sorted(chapters), 1):
                viewer = self._load_pages(chapter_id)
                chapter = viewer.pages[-1].last_page.current_chapter
                next_chapter = viewer.pages[-1].last_page.next_chapter
                next_chapter = (
                    next_chapter if next_chapter.chapter_id != 0 else None
                )
                chapter_name = viewer.chapter_name
                log.info(
                    f"    {chapter_index}/{chapter_num}) "
                    f"Chapter {chapter_name}: {chapter.sub_title}"
                )
                exporter = self.exporter_cls(dst, title, chapter, next_chapter)
                pages = [
                    p.manga_page for p in viewer.pages if p.manga_page.image_url
                ]

                with click.progressbar(
                    pages, label=chapter_name, show_pos=True
                ) as pbar:
                    page_counter = count()
                    for page_index, page in zip(page_counter, pbar):
                        # Todo use asyncio + async requests 3
                        image_blob = self._decrypt_image(
                            page.image_url, page.encryption_key
                        )
                        if PageType(page.type) == PageType.double:
                            page_index = range(page_index, next(page_counter))
                        exporter.add_image(image_blob, page_index)

                exporter.close()

    def download(
        self,
        *,
        title_ids: Optional[Collection[int]] = None,
        chapter_ids: Optional[Collection[int]] = None,
        dst: str = ".",
    ):
        self._download(self._normalize_ids(title_ids, chapter_ids), dst)
