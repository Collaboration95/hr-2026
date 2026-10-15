"""Shared, deliberately small in-memory engine interface."""
from dataclasses import dataclass
import numpy as np

BAND_NAMES = ('treecover2000', 'lossyear', 'datamask')
QUERY_VERSION = 'hansen-centers.v1'
PERIODS = {'2021-2023': (21, 23), '2024-2025': (24, 25)}

@dataclass
class Dataset:
    bands: np.ndarray
    masks: np.ndarray
    metadata: dict

    def validate(self):
        if self.bands.ndim != 3 or self.bands.shape[0] != 3:
            raise ValueError('bands must have shape [3,height,width]')
        if self.bands.dtype != np.uint8:
            raise ValueError('bands must be raw uint8 integers')
        if self.masks.dtype != np.bool_ or self.masks.shape != self.bands.shape:
            raise ValueError('masks must be bool with the same shape as bands')
        if list(self.bands.shape[1:]) != self.metadata.get('shape'):
            raise ValueError('metadata shape does not match bands')
        if min(self.bands.shape[1:]) < 1:
            raise ValueError('empty grids are unsupported')
        for i, maximum in enumerate((100, 25, 2)):
            if np.any(self.bands[i] > maximum):
                raise ValueError(f'{BAND_NAMES[i]} raw value outside 0..{maximum}')
        return self
