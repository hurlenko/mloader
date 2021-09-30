from enum import Enum


class Language(Enum):
    eng = 0
    spa = 1
    fre = 2
    ind = 3
    por = 4
    rus = 5
    tha = 6


class ChapterType(Enum):
    latest = 0
    sequence = 1
    nosequence = 2


class PageType(Enum):
    single = 0
    left = 1
    right = 2
    double = 3
