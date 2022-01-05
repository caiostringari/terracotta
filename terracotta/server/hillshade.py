"""server/hillshade.py

Flask route to handle /hillshade calls.
"""

from typing import Any, Mapping, Dict, Tuple
import json

from marshmallow import (
    Schema,
    fields,
    validate,
    # validates_schema,
    pre_load,
    ValidationError,
    EXCLUDE,
)
from flask import request, send_file, Response

from matplotlib.pyplot import colormaps

from terracotta.server.flask_api import TILE_API

# from terracotta.cmaps import AVAILABLE_CMAPS


class HillshadeQuerySchema(Schema):
    keys = fields.String(required=True, description="Keys identifying dataset, in order")
    tile_z = fields.Int(required=True, description="Requested zoom level")
    tile_y = fields.Int(required=True, description="y coordinate")
    tile_x = fields.Int(required=True, description="x coordinate")


class HillshadeOptionSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    # only matplotlib colormaps are allowed
    colormap = fields.String(
        description="Colormap to apply to image (see /colormap)",
        validate=validate.OneOf(colormaps()),
        missing="Greys_r",
    )

    azimuth_degree = fields.Number(
        description="The azimuth (0-360, degrees clockwise from North) of the light source.",
        missing=315,
    )

    altitude_degree = fields.Number(
        description="The altitude (0-90, degrees up from horizontal) of the light source.",
        missing=45,
    )

    vertical_exaggeration = fields.Number(
        description="The amount to exaggerate the elevation values by when calculating illumination. This can be used either to correct for differences in units between the x-y coordinate system and the elevation coordinate system (e.g. decimal degrees vs. meters) or to exaggerate or de-emphasize topography.",
        missing=1,
    )

    blend_mode = fields.String(
        description='Blend mode. One of: "hsv", "overlay", "soft"',
        validate=validate.OneOf(["hsv", "overlay", "soft"]),
        missing="soft",
    )

    tile_size = fields.List(
        fields.Integer(),
        validate=validate.Length(equal=2),
        example="[256,256]",
        description="Pixel dimensions of the returned PNG image as JSON list.",
    )

    @pre_load
    def decode_json(self, data: Mapping[str, Any], **kwargs: Any) -> Dict[str, Any]:
        data = dict(data.items())
        for var in ("colormap", "azimuth_degree", "altitude_degree", "vertical_exaggeration", "blend_mode"):
            val = data.get(var)
            if val:
                try:
                    data[var] = json.loads(val)
                except json.decoder.JSONDecodeError as exc:
                    msg = f"Could not decode value {val} for {var} as JSON"
                    raise ValidationError(msg) from exc

        return data


@TILE_API.route(
    "/hillshade/<path:keys>/<int:tile_z>/<int:tile_x>/<int:tile_y>.png",
    methods=["GET"],
)
def get_hillshade(tile_z: int, tile_y: int, tile_x: int, keys: str) -> Response:
    """Return multi-band PNG image of requested tile
    ---
    get:
        summary: /hillshade (tile)
        description: Return multi-band PNG image of requested XYZ tile
        parameters:
            - in: path
              schema: HillshadeQuerySchema
            - in: query
              schema: HillshadeOptionSchema
        responses:
            200:
                description:
                    PNG image of requested tile
            400:
                description:
                    Invalid query parameters
            404:
                description:
                    No dataset found for given key combination
    """
    tile_xyz = (tile_x, tile_y, tile_z)
    return _get_hillshade(keys, tile_xyz)


class HillshadePreviewSchema(Schema):
    keys = fields.String(required=True, description="Keys identifying dataset, in order")


@TILE_API.route("/hillshade/<path:keys>/preview.png", methods=["GET"])
def get_hillshade_preview(keys: str) -> Response:
    """Return multi-band PNG preview image of requested dataset
    ---
    get:
        summary: /hillshade (preview)
        description: Return muilt-band PNG preview image of requested dataset
        parameters:
            - in: path
              schema: HillshadePreviewSchema
            - in: query
              schema: HillshadeOptionSchema
        responses:
            200:
                description:
                    PNG image of requested tile
            400:
                description:
                    Invalid query parameters
            404:
                description:
                    No dataset found for given key combination
    """
    return _get_hillshade(keys)


def _get_hillshade(keys: str, tile_xyz: Tuple[int, int, int] = None) -> Response:
    from terracotta.handlers.hillshade import hillshade

    parsed_keys = [key for key in keys.split("/") if key]

    option_schema = HillshadeOptionSchema()
    options = option_schema.load(request.args)

    image = hillshade(parsed_keys, tile_xyz=tile_xyz, **options)

    return send_file(image, mimetype="image/png")
