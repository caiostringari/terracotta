"""xyz.py

Utilities to work with XYZ Mercator tiles.
"""

from typing import Sequence, Union, Mapping, Tuple, Any

import mercantile

from terracotta import exceptions
from terracotta.drivers.base import Driver

# tile resolution for each level starting at level 0.
TILE_RESOLUTION = [
    156412,
    78206,
    39103,
    19551,
    9776,
    4888,
    2444,
    1222,
    610.984,
    305.492,
    152.746,
    76.373,
    38.187,
    19.093,
    9.547,
    4.773,
    2.387,
    1.193,
    0.596,
    0.298,
    0.149,
]


# TODO: add accurate signature if mypy ever supports conditional return types
def get_tile_data(driver: Driver,
                  keys: Union[Sequence[str], Mapping[str, str]],
                  tile_xyz: Tuple[int, int, int] = None,
                  *, tile_size: Tuple[int, int] = (256, 256),
                  preserve_values: bool = False,
                  asynchronous: bool = False,
                  # 
                  buffer: int = 0) -> Any:
    """Retrieve raster image from driver for given XYZ tile and keys"""

    if tile_xyz is None:
        # read whole dataset
        return driver.get_raster_tile(
            keys, tile_size=tile_size, preserve_values=preserve_values,
            asynchronous=asynchronous
        )

    # determine bounds for given tile
    metadata = driver.get_metadata(keys)
    wgs_bounds = metadata['bounds']

    tile_x, tile_y, tile_z = tile_xyz

    if not tile_exists(wgs_bounds, tile_x, tile_y, tile_z):
        raise exceptions.TileOutOfBoundsError(
            f'Tile {tile_z}/{tile_x}/{tile_y} is outside image bounds'
        )

    mercator_tile = mercantile.Tile(x=tile_x, y=tile_y, z=tile_z)
    target_bounds = mercantile.xy_bounds(mercator_tile)
    
    tile_data =  driver.get_raster_tile(
        keys, tile_bounds=target_bounds, tile_size=tile_size,
        preserve_values=preserve_values, asynchronous=asynchronous
    )
    
    if buffer > 0:
        buffer_meters = TILE_RESOLUTION[tile_z]*buffer
        target_bounds_buffer = (target_bounds.left - buffer_meters, 
                                target_bounds.bottom - buffer_meters,
                                target_bounds.right + buffer_meters, 
                                target_bounds.top + buffer_meters)

        tile_data_buffered = driver.get_raster_tile(
            # adjust this tie size to be larger with radius pixels added to 256
            keys, tile_bounds=target_bounds_buffer, tile_size=[tile_size[0]+buffer*2, tile_size[1]+buffer*2],
            preserve_values=preserve_values, asynchronous=asynchronous
        )

        tile_data = tile_data_buffered

    return tile_data
    # return driver.get_raster_tile(
    #     keys, tile_bounds=target_bounds, tile_size=tile_size,
    #     preserve_values=preserve_values, asynchronous=asynchronous
    # )


def tile_exists(bounds: Sequence[float], tile_x: int, tile_y: int, tile_z: int) -> bool:
    """Check if an XYZ tile is inside the given physical bounds."""
    mintile = mercantile.tile(bounds[0], bounds[3], tile_z)
    maxtile = mercantile.tile(bounds[2], bounds[1], tile_z)

    return mintile.x <= tile_x <= maxtile.x and mintile.y <= tile_y <= maxtile.y
