from mloader.loader import MangaLoader
from mloader.exporter import ExporterBase

def test():
    mloader = MangaLoader(ExporterBase)
    details = mloader._get_title_details('100191')
    print(details)

if __name__ == '__main__':
    test()
