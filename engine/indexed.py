"""Window reads that preserve global native-grid center arithmetic exactly.

Full-grid preload remains the simple default. These optional readers support
bounded memory and quantify indexed-query tradeoffs; no speedup is presumed.
"""
from pathlib import Path
import numpy as np
from rasterio.windows import Window
from .model import Dataset
from .query import select_cells, summarize_selected
from .source import open_sources, sha256_file


def evaluate_reader(reader, geometry, missing_bands=()):
    rows, cols = select_cells(reader.metadata, geometry)
    height, width = reader.metadata['shape']
    inside = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
    r, c = rows[inside], cols[inside]
    if len(r):
        r0, r1, c0, c1 = int(r.min()), int(r.max())+1, int(c.min()), int(c.max())+1
        bands, masks = reader.read_window(r0, r1, c0, c1)
        values = bands[:, r-r0, c-c0]
        validity = masks[:, r-r0, c-c0]
    else:
        values = np.empty((3, 0), dtype=np.uint8)
        validity = np.empty((3, 0), dtype=bool)
    return summarize_selected(values, validity, len(rows), int((~inside).sum()), missing_bands)


class SourceWindowReader:
    def __init__(self, root=None):
        self._context = open_sources(root)
        self._readers, self.metadata = self._context.__enter__()
        self._closed = False

    def read_window(self, r0, r1, c0, c1):
        if self._closed:
            raise ValueError('source reader is closed')
        height, width = self.metadata['shape']
        if not (0 <= r0 < r1 <= height and 0 <= c0 < c1 <= width):
            raise ValueError('window must be nonempty and in coverage')
        window = Window(c0, r0, c1-c0, r1-r0)
        bands = np.stack([src.read(1, window=window) for src in self._readers])
        masks = np.stack([src.read_masks(1, window=window) != 0 for src in self._readers])
        # Validate observed values, including masked cells; metadata keeps the
        # original transform because selection was already performed globally.
        Dataset(bands, masks, dict(self.metadata, shape=[r1-r0, c1-c0])).validate()
        return bands, masks

    def close(self):
        if not self._closed:
            self._context.__exit__(None, None, None)
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class CompactWindowReader:
    def __init__(self, path):
        # The codec's bounded/checksummed index parser is reused deliberately.
        # This private helper is pinned by the same-repository format tests.
        from .codecs import _read_index, HEADER
        self.path = Path(path)
        index = _read_index(self.path)
        payload = self.path / 'payload.bin'
        if payload.is_symlink() or not payload.is_file() or payload.stat().st_size != index['payload_bytes']:
            raise ValueError('compact payload is missing, truncated, or not a regular file')
        with payload.open('rb') as stream:
            if stream.read(len(HEADER)) != HEADER:
                raise ValueError('compact payload header mismatch')
        if sha256_file(payload) != index['payload_sha256']:
            raise ValueError('compact full payload checksum mismatch')
        self.metadata = index['metadata']

    def read_window(self, r0, r1, c0, c1):
        from .codecs import read_window
        bands, masks, _shifted_metadata = read_window(self.path, r0, r1, c0, c1)
        # Do NOT use shifted metadata to decide center membership.
        return bands, masks

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
