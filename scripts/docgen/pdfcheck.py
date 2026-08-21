"""Utilities to inspect generated PDFs: text search per page + PNG rendering."""
import sys
import pymupdf


def page_texts(path):
    doc = pymupdf.open(path)
    return [doc[i].get_text() for i in range(doc.page_count)]


def grep(path, keywords):
    for i, t in enumerate(page_texts(path), 1):
        hits = [kw for kw in keywords if kw in t]
        if hits:
            print("  page %d: %s" % (i, hits))


def render(path, page_index, out_png, zoom=1.4):
    doc = pymupdf.open(path)
    pg = doc[page_index]
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    pix.save(out_png)
    return out_png


if __name__ == "__main__":
    path = sys.argv[1]
    doc = pymupdf.open(path)
    print(path, "->", doc.page_count, "pages")
