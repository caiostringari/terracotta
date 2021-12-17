"""server/countour.py

Flask route to handle /countour calls.
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


class ContourQuerySchema(Schema):
    keys = fields.String(
        required=True, description="Keys identifying dataset, in order"
    )
    tile_z = fields.Int(required=True, description="Requested zoom level")
    tile_y = fields.Int(required=True, description="y coordinate")
    tile_x = fields.Int(required=True, description="x coordinate")


class ContourOptionSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    color = fields.List(
        fields.Number(), validate=validate.Length(equal=3), required=False,
        description='A list with three RGB values in the 0.-1. range.',
        missing=[0., 0., 0.],
    )

    interval = fields.Number(
        description="Interval (in CRS units) to find contours. Default is 5.",
        missing=5,
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
        for var in ("color", "interval"):
            val = data.get(var)
            if val:
                try:
                    data[var] = json.loads(val)
                except json.decoder.JSONDecodeError as exc:
                    msg = f"Could not decode value {val} for {var} as JSON"
                    raise ValidationError(msg) from exc

        return data


@TILE_API.route(
    "/contour/<path:keys>/<int:tile_z>/<int:tile_x>/<int:tile_y>.png",
    methods=["GET"],
)
def get_contour(tile_z: int, tile_y: int, tile_x: int, keys: str) -> Response:
    """Return multi-band PNG image of requested tile
    ---
    get:
        summary: /contour (tile)
        description: Return multi-band PNG image of requested XYZ tile
        parameters:
            - in: path
              schema: ContourQuerySchema
            - in: query
              schema: ContourOptionSchema
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
    return _get_contour(keys, tile_xyz)


class ContourPreviewSchema(Schema):
    keys = fields.String(
        required=True, description="Keys identifying dataset, in order"
    )


@TILE_API.route("/contour/<path:keys>/preview.png", methods=["GET"])
def get_contour_preview(keys: str) -> Response:
    """Return multi-band PNG preview image of requested dataset
    ---
    get:
        summary: /contour (preview)
        description: Return muilt-band PNG preview image of requested dataset
        parameters:
            - in: path
              schema: ContourPreviewSchema
            - in: query
              schema: ContourOptionSchema
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
    return _get_contour(keys)


def _get_contour(keys: str, tile_xyz: Tuple[int, int, int] = None) -> Response:
    from terracotta.handlers.contour import contour

    parsed_keys = [key for key in keys.split("/") if key]

    option_schema = ContourOptionSchema()
    options = option_schema.load(request.args)

    image = contour(parsed_keys, tile_xyz=tile_xyz, **options)

    return send_file(image, mimetype="image/png")
