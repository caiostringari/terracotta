"""handlers/hillshade.py

Handle /hillshade API endpoint.
"""


from typing import Sequence, Mapping, Union, Tuple, TypeVar

from numpy.lib.shape_base import tile
from typing.io import BinaryIO

from io import BytesIO

from PIL import Image

from skimage.util import img_as_ubyte

import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm
from matplotlib.pyplot import matshow

import numpy as np

from terracotta import get_settings, get_driver, xyz, image
from terracotta.profile import trace

Number = TypeVar("Number", int, float)


def scaler(data, vmin, vmax):
    return (data - vmin) / (vmax - vmin)


@trace("discrete_handler")
def discrete(
    keys: Union[Sequence[str], Mapping[str, str]],
    tile_xyz: Tuple[int, int, int] = None,
    *,
    colormap: str,
    tile_size: Tuple[int, int] = None,
    n_classes: Number = None,
    vmin: Number = None,
    vmax: Number = None,
) -> BinaryIO:
    """Return singleband image rendered as discrete colors in PNG format"""

    settings = get_settings()
    if tile_size is None:
        tile_size = settings.DEFAULT_TILE_SIZE

    driver = get_driver(settings.DRIVER_PATH, provider=settings.DRIVER_PROVIDER)

    with driver.connect():
        metadata = driver.get_metadata(keys)
        tile_data = xyz.get_tile_data(
            driver,
            keys,
            tile_xyz,
            tile_size=tile_size,
            preserve_values=False,
        )

    try:
        cmap = plt.get_cmap(colormap, n_classes)
    except Exception:
        cmap = plt.get_cmap("viridis", n_classes)  # defaults to viridis

    if not vmin:
        vmin = metadata["range"][0]
    if not vmax:
        vmax = metadata["range"][1]

    # manipulate tile data
    # print(tile_data)
    data = tile_data.copy()
    data[np.where(data <= vmin)] = vmin
    data[np.where(data >= vmax)] = vmax
    data = scaler(data, vmin, vmax)
    rgb = cmap(data)

    # encode for terracotta - 0-255
    r = image.to_uint8(rgb[:, :, 0], 0, 1)
    g = image.to_uint8(rgb[:, :, 1], 0, 1)
    b = image.to_uint8(rgb[:, :, 2], 0, 1)

    out = np.ma.stack([r, g, b], axis=-1)
    out[np.ma.masked_invalid(tile_data).mask] = 0  # zero means transparent

    # todo: pure white also means transparent

    return image.array_to_png(out[:, :, 0:3])
