import logging
import re
import sys
from typing import Tuple

import click

from mloader import __version__ as about
from mloader.exporter import RawExporter, CBZExporter
from mloader.loader import MangaLoader

log = logging.getLogger()


def setup_logging():
    for logger in ("requests", "urllib3"):
        logging.getLogger(logger).setLevel(logging.WARNING)
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


def validate_chapters(ctx, param, value):
    if not value:
        return value
    res = set()
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
            res.add(int(item))
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
@click.pass_context
def main(
    ctx: click.Context,
    out_dir: str,
    chapters: Tuple[int],
    raw: bool,
    quality: str,
    split: bool,
):
    if not chapters:
        click.echo(ctx.get_help())
        return
    setup_logging()
    log.info("Started export")

    for chapter_id in chapters:
        loader = MangaLoader(
            RawExporter if raw else CBZExporter, quality, split
        )
        try:
            loader.download_chapter(chapter_id, out_dir)
        except Exception:
            log.exception("Failed to download_chapter images")
    log.info("SUCCESS")


if __name__ == "__main__":
    click.echo(click.style(about.__doc__, fg="blue"))
    main(prog_name="mloader")
