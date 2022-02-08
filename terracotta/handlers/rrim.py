"""handlers/rrim.py

Handle /rrim API endpoint.
"""

from typing import Sequence, Mapping, Union, Tuple, TypeVar
from weakref import CallableProxyType
from typing.io import BinaryIO

from matplotlib.pyplot import get_cmap
from matplotlib.colors import (LightSource, Normalize)

import cv2
import numpy as np
import rasterio
import rvt.vis

# import collections

from terracotta import get_settings, update_settings, get_driver, image, xyz
from terracotta.profile import trace


Number = TypeVar("Number", int, float)
# RGBA = Tuple[Number, Number, Number, Number]

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

def colorScheme(size):
        """
        Function to compute color scheme from HSV to RGB
        Function from Xin Yao : https://github.com/susurrant/

        Args:
            size (tupple of integers): (a, b, c); a gives the saturation, b the brithness
                                    and c correspond to the number of bands of the image; this is set to 3

        Returns:[ro]
            RRIM_map (x * y * 3 uint8 array) : RGB array
        """
        
        img_hsv = np.zeros(size, dtype=np.uint8)
        
        # saturation
        saturation_values = np.linspace(0, 255, size[0])
        for i in range(0, size[0]):
            img_hsv[i, :, 1] = np.ones(size[1], dtype=np.uint8) * np.uint8(saturation_values[i])

        # value
        V_values = np.linspace(0, 255, size[1])
        for i in range(0, size[1]):
            img_hsv[:, i, 2] = np.ones(size[0], dtype=np.uint8) * np.uint8(V_values[i])

        # print(img_hsv)
        # output_fname = r"C:\Users\agraham\terracotta_cs\rrim_test\rrim_test.tif"
        # print(output_fname)
        # cv2.imwrite(output_fname, cv2.cvtColor(img_hsv, cv2.COLOR_HSV2BGR))
        return cv2.cvtColor(img_hsv, cv2.COLOR_HSV2BGR)

def crop_center(img, cropx, cropy):
    y, x, *_ = img.shape
    startx = x // 2 - (cropx // 2)
    starty = y // 2 - (cropy // 2)    
    return img[starty:starty + cropy, startx:startx + cropx, ...]

def insert_at(big_arr, small_arr, pos):
    x1 = pos[0]
    y1 = pos[1]
    x2 = x1 + small_arr.shape[0]
    y2 = y1 + small_arr.shape[1]

    assert x2  <= big_arr.shape[0], "the position will make the small matrix exceed the boundaries at x"
    assert y2  <= big_arr.shape[1], "the position will make the small matrix exceed the boundaries at y"

    big_arr[x1:x2,y1:y2] = small_arr

    return big_arr

@trace("rrim_handler")
def rrim(
    keys: Union[Sequence[str], Mapping[str, str]],
    tile_xyz: Tuple[int, int, int] = None,
    *,
    # colormap: str,
    
    # RRIM parameters
    nodatavalue : int,
    svf_n_dir : int,
    svf_r_max : int,
    svf_noise : int,
    saturation : int,
    brithness : int,
    blend_mode : str,
    # resampling_method,

    tile_size: Tuple[int, int] = None
) -> BinaryIO:
    """Return singleband image rendered as rrim PNG"""

    # try:
    #     cmap = get_cmap(colormap)
    # except Exception:
    #     cmap = get_cmap("Greys_r")  # defaults to grey
    # update_settings(RESAMPLING_METHOD=resampling_method)

    settings = get_settings()
    if tile_size is None:
        tile_size = settings.DEFAULT_TILE_SIZE

    driver = get_driver(settings.DRIVER_PATH, provider=settings.DRIVER_PROVIDER)
    # DEFAULT_TILE_SIZE: Tuple[int, int] = (256, 256)
    print(tile_xyz)
    print('buffer size in meters...')
    print(TILE_RESOLUTION[tile_xyz[2]]*svf_r_max)

    TILE_RESOLUTION[tile_xyz[2]]*svf_r_max
    with driver.connect():
        metadata = driver.get_metadata(keys)

    # tile_size = (100, 100)

    tile_data = xyz.get_tile_data(
            driver,
            keys,
            tile_xyz,
            tile_size=[tile_size[0], tile_size[1]],
            preserve_values=False,
            buffer = svf_r_max
        )
    
    print('tile data shape:')
    print(tile_data.shape)
    
    try:
        _, _, tile_z = tile_xyz
        dx = TILE_RESOLUTION[tile_z]
        dy = TILE_RESOLUTION[tile_z]
    except Exception:
        dx = 1
        dy = 1

    # compute the RRIM

    # build the color map/scheme
    color_size=(saturation, brithness, 3)

    # load the DEM
    # DEM = rd.LoadGDAL(demname, no_data = nodatavalue)
    DEM = np.asarray(tile_data)
    # print("HERE")
    # print(DEM)

    dict_slope_aspect = rvt.vis.slope_aspect(dem = DEM, 
                                             resolution_x = dx, 
                                             resolution_y = dy,
                                             output_units = "degree", 
                                             ve_factor = 1, 
                                             # no_data=nodatavalue, # problem with dem[dem == no_data] = np.nan
                                             no_data = None)# ,
                                             # fill_no_data = False, keep_original_no_data = False)
    
    slopedata = dict_slope_aspect["slope"]

    dict_svf = rvt.vis.sky_view_factor(dem = DEM, resolution = dx,
        #dict_svf = rvt.vis.sky_view_factor_compute(height_arr = DEM, 
                                       compute_svf = False, compute_asvf = False, compute_opns = True,
                                       svf_n_dir = svf_n_dir, svf_r_max = svf_r_max, svf_noise = svf_noise,
                                       no_data = nodatavalue) #, 
                                       #no_data = None, 
                                       #fill_no_data = False, keep_original_no_data = False)

    pos_opns_arr = dict_svf["opns"]  # positive openness

    # Fonction to compute the negative openness
    DEM_neg_opns = DEM * -1  # dem * -1 for neg opns
    # we don't need to calculate svf and asvf (compute_svf=False, compute_asvf=False)
    dict_svf = rvt.vis.sky_view_factor(dem = DEM_neg_opns, resolution = dx, 
    #dict_svf = rvt.vis.sky_view_factor_compute(height_arr = DEM_neg_opns,
                                    compute_svf = False, compute_asvf = False, compute_opns = True,
                                    svf_n_dir = svf_n_dir, svf_r_max = svf_r_max, svf_noise = svf_noise,
                                    no_data = nodatavalue)#,
                                    #no_data = None, 
                                    # fill_no_data = False, keep_original_no_data = False)
    neg_opns_arr = dict_svf["opns"] # negative openness
    # Invert negative openness as proposed by Chiba et al.?
    # How to do it?
    #neg_opns_arr = (1 - neg_opns_arr / neg_opns_arr.max()) * neg_opns_arr.max()
    #neg_opns_arr = neg_opns_arr - 360

    # Compute the differential openness
    openness = (pos_opns_arr - neg_opns_arr) / 2

    # print(color_size)
    RRIM_map = colorScheme(color_size)
    result = np.zeros((slopedata.shape[0], slopedata.shape[1], 3), dtype = np.uint8)
    
    # Compute the color given by the slope
    inc = np.uint8(abs(slopedata))
    inc[inc > (color_size[0]-1)] = color_size[0] - 1

    # Compute the grey given by the openness
    openness_val = np.uint8((openness + color_size[1]) / 2)
    openness_val[openness_val < 0] = 0
    openness_val[openness_val >= color_size[1]] = color_size[1] - 1
  
    # build the RGB tuples
    result = RRIM_map[inc, openness_val]
    # print(result.shape)

    result = crop_center(result, tile_size[0], tile_size[1])
 
    # print(result.shape)
    tile_data_crop = xyz.get_tile_data(
            driver,
            keys,
            tile_xyz,
            tile_size=[tile_size[0], tile_size[1]],
            preserve_values=False,
        )
    result[np.ma.masked_invalid(tile_data_crop).mask] = 0

    # print(result.shape)
    # result = crop_center(result, 256, 256)
    # print(result)
    print(type(result))
    # Update the progress-bar

    # # compute the shadding
    # norm = Normalize(vmin=metadata["range"][0], vmax=metadata["range"][1], clip=False)
    # ls = LightSource(azdeg=azimuth_degree, altdeg=altitude_degree)
    # rgb = ls.shade(
    #     np.ma.masked_invalid(tile_data),
    #     cmap=cmap,
    #     blend_mode=blend_mode,
    #     vert_exag=vertical_exaggeration,
    #     dx=dx,
    #     dy=dy,
    #     norm = norm
    # )

    # # rgb is between 0 and, scale it to 0-255. store as uint8.
    b = result[:, :, 0]
    g = result[:, :, 1]
    r = result[:, :, 2]

    result = np.ma.stack([r, g, b], axis=-1)
    return image.array_to_png(result)
