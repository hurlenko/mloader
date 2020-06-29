# Mangaplus Downloader

[![Latest Github release](https://img.shields.io/github/tag/hurlenko/mloader.svg)](https://github.com/hurlenko/mloader/releases/latest)
![Python](https://img.shields.io/badge/python-v3.6+-blue.svg)
![License](https://img.shields.io/badge/license-GPLv3-blue.svg)

## **mloader** - download manga from mangaplus.shueisha.co.jp

## 🚩 Table of Contents

- [Installation](#-installation)
- [Usage](#-usage)
- [Command line interface](#%EF%B8%8F-command-line-interface)

## 💾 Installation

The recommended installation method is using `pip`:

```bash
pip install mloader
```

After installation, the `mloader` command will be available. Check the [command line](%EF%B8%8F-command-line-interface) section for supported commands.

## 📙 Usage

Copy the url of the chapter or title you want to download and pass it to `mloader`.

You can use `--title` and `--chapter` command line argument to download by title and chapter id.

You can download individual chapters or full title (but only available chapters).

Chapters can be saved as `CBZ` archives (default) or separate images by passing the `--raw` parameter.

## 🖥️ Command line interface

Currently `mloader` supports these commands

```bash
Usage: mloader [OPTIONS] [URLS]...

Options:
  -o, --out <directory>           Save directory (not a file)  [default:
                                  mloader_downloads]
  -r, --raw                       Save raw images  [default: False]
  -q, --quality [super_high|high|low]
                                  Image quality  [default: super_high]
  -s, --split                     Split combined images  [default: False]
  -c, --chapter INTEGER           Chapter id
  -t, --title INTEGER             Title id
  --help                          Show this message and exit.
```