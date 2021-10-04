import logging
from collections import namedtuple
from functools import lru_cache
from itertools import chain, count
from typing import Union, Dict, Set, Collection, Optional, Callable

import click
from requests import Session

from mloader.constants import PageType
from mloader.exporter import ExporterBase
from mloader.response_pb2 import (
    Response,
    MangaViewer,
    TitleDetailView,
    Chapter,
    Title,
)
from mloader.utils import chapter_name_to_int

log = logging.getLogger()

MangaList = Dict[int, Set[int]]  # Title ID: Set[Chapter ID]


class MangaLoader:
    def __init__(
        self,
        exporter: Callable[[Title, Chapter, Optional[Chapter]], ExporterBase],
        quality: str = "super_high",
        split: bool = False,
    ):
        self.exporter = exporter
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
            f"{self._api_url}/api/title_detail", params={"title_id": title_id}
        )
        return Response.FromString(resp.content).success.title_detail_view

    def _normalize_ids(
        self,
        title_ids: Collection[int],
        chapter_ids: Collection[int],
        min_chapter: int,
        max_chapter: int,
        last_chapter: bool = False,
    ) -> MangaList:
        # mloader allows you to mix chapters and titles(collections of chapters)
        # This method tries to merge them while trying to avoid unnecessary
        # http requests
        if not any((title_ids, chapter_ids)):
            raise ValueError("Expected at least one title or chapter id")
        title_ids = set(title_ids or [])
        chapter_ids = set(chapter_ids or [])
        mangas = {}
        chapter_meta = namedtuple("ChapterMeta", "id name")
        for cid in chapter_ids:
            viewer = self._load_pages(cid)
            title_id = viewer.title_id
            # Fetching details for this chapter also downloads all other
            # visible chapters for the same title.
            if title_id in title_ids:
                title_ids.remove(title_id)
                mangas.setdefault(title_id, []).extend(
                    chapter_meta(c.chapter_id, c.name) for c in viewer.chapters
                )
            else:
                mangas.setdefault(title_id, []).append(
                    chapter_meta(viewer.chapter_id, viewer.chapter_name)
                )

        for tid in title_ids:
            details = self._get_title_details(tid)
            mangas[tid] = [
                chapter_meta(chapter.chapter_id, chapter.name)
                for chapter in chain(
                    details.first_chapter_list, details.last_chapter_list
                )
            ]

        for tid in mangas:
            if last_chapter:
                chapters = mangas[tid][-1:]
            else:
                chapters = [
                    c
                    for c in mangas[tid]
                    if min_chapter
                    <= (chapter_name_to_int(c.name) or 0)
                    <= max_chapter
                ]

            mangas[tid] = set(c.id for c in chapters)

        return mangas

    def _download(self, manga_list: MangaList):
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
                exporter = self.exporter(
                    title=title, chapter=chapter, next_chapter=next_chapter
                )
                pages = [
                    p.manga_page for p in viewer.pages if p.manga_page.image_url
                ]

                with click.progressbar(
                    pages, label=chapter_name, show_pos=True
                ) as pbar:
                    page_counter = count()
                    for page_index, page in zip(page_counter, pbar):
                        if PageType(page.type) == PageType.double:
                            page_index = range(page_index, next(page_counter))
                        if not exporter.skip_image(page_index):
                            # Todo use asyncio + async requests 3
                            image_blob = self._decrypt_image(
                                page.image_url, page.encryption_key
                            )
                            exporter.add_image(image_blob, page_index)

                exporter.close()

    def download(
        self,
        *,
        title_ids: Optional[Collection[int]] = None,
        chapter_ids: Optional[Collection[int]] = None,
        min_chapter: int,
        max_chapter: int,
        last_chapter: bool = False,
    ):
        manga_list = self._normalize_ids(
            title_ids, chapter_ids, min_chapter, max_chapter, last_chapter
        )
        self._download(manga_list)
