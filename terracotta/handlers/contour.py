"""handlers/hillshade.py

Handle /contour API endpoint.
"""
import tempfile

from typing import Sequence, Mapping, Union, Tuple, TypeVar
from typing.io import BinaryIO

import matplotlib as mpl
mpl.use("Agg")

from matplotlib import colors
import matplotlib.pyplot as plt

import numpy as np
from skimage import measure

from terracotta import get_settings, get_driver, image, xyz
from terracotta.profile import trace

Number = TypeVar("Number", int, float)
# RGBA = Tuple[Number, Number, Number, Number]


@trace("contour_handler")
def contour(
    keys: Union[Sequence[str], Mapping[str, str]],
    tile_xyz: Tuple[int, int, int] = None,
    *,
    color: Tuple[int, int, int] = None,
    interval: int = None,
    tile_size: Tuple[int, int] = None
) -> BinaryIO:
    """Return singleband image rendered as hillshade PNG"""

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
            preserve_values=True,
        )

    # compute the contours
    intervals = np.arange(metadata["range"][0], metadata["range"][1], interval)
    contours = []
    for v in intervals:
        ctns = measure.find_contours(np.ma.masked_invalid(tile_data), v)
        for ctn in ctns:
            contours.append(ctn)

    # render
    fig, ax = plt.subplots(figsize=(2.56,2.56), dpi=100, **{"tight_layout": True, "frameon": False})
    for contour in contours:
        ax.plot(contour[:, 1], contour[:, 0], linewidth=1, color=colors.rgb2hex(color))
    ax.set_axis_off()
    ax.set_xlim(0, 255)
    ax.set_ylim(0, 255)
    ax.margins(0,0)
    ax.set_xticks([])
    ax.set_yticks([])

    # write to a temporary file

    with tempfile.NamedTemporaryFile() as tmp:
        plt.savefig(tmp,  bbox_inches='tight', pad_inches=0)
        rgba = plt.imread(tmp)

    # rgb is between 0 and 1, scale it to 0-255. store as uint8.
    r = image.to_uint8(rgba[:, :, 0], 0, 1)
    g = image.to_uint8(rgba[:, :, 1], 0, 1)
    b = image.to_uint8(rgba[:, :, 2], 0, 1)
    a = rgba[:, :, 3]

    out = np.ma.stack([r, g, b], axis=-1)
    out[np.ma.masked_equal(a, 0).mask] = 0

    return image.array_to_png(out)
