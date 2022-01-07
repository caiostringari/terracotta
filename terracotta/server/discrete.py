"""server/discrete.py

Flask route to handle /discrete calls.
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


class DiscreteQuerySchema(Schema):
    keys = fields.String(required=True, description="Keys identifying dataset, in order")
    tile_z = fields.Int(required=True, description="Requested zoom level")
    tile_y = fields.Int(required=True, description="y coordinate")
    tile_x = fields.Int(required=True, description="x coordinate")


class DiscreteOptionSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    # only matplotlib colormaps are allowed
    colormap = fields.String(
        description="Colormap to apply to image (see /colormap)",
        validate=validate.OneOf(colormaps()),
        missing="viridis",
    )

    n_classes = fields.Number(
        description="Number of classes to use. Defaults to 16.",
        missing=16,
    )

    vmin = fields.Number(
        description="Minimum value to consider for rendering. If missing, uses data's minimum value.",
        missing=None,
    )

    vmax = fields.Number(
        description="Maximum value to consider for rendering. If missing, uses data's maximum value.",
        missing=None,
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
        for var in ("colormap", "n_classes", "vmin", "vmax"):
            val = data.get(var)
            if val:
                try:
                    data[var] = json.loads(val)
                except json.decoder.JSONDecodeError as exc:
                    msg = f"Could not decode value {val} for {var} as JSON"
                    raise ValidationError(msg) from exc

        return data


@TILE_API.route(
    "/discrete/<path:keys>/<int:tile_z>/<int:tile_x>/<int:tile_y>.png",
    methods=["GET"],
)
def get_discrete(tile_z: int, tile_y: int, tile_x: int, keys: str) -> Response:
    """Return multi-band PNG image of requested tile
    ---
    get:
        summary: /discrete (tile)
        description: Return multi-band PNG image of requested XYZ tile
        parameters:
            - in: path
              schema: DiscreteQuerySchema
            - in: query
              schema: DiscreteOptionSchema
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
    return _get_discrete(keys, tile_xyz)


class DiscretePreviewSchema(Schema):
    keys = fields.String(required=True, description="Keys identifying dataset, in order")


@TILE_API.route("/discrete/<path:keys>/preview.png", methods=["GET"])
def get_discrete_preview(keys: str) -> Response:
    """Return multi-band PNG preview image of requested dataset
    ---
    get:
        summary: /discrete (preview)
        description: Return muilt-band PNG preview image of requested dataset
        parameters:
            - in: path
              schema: DiscretePreviewSchema
            - in: query
              schema: DiscreteOptionSchema
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
    return _get_discrete(keys)


def _get_discrete(keys: str, tile_xyz: Tuple[int, int, int] = None) -> Response:
    from terracotta.handlers.discrete import discrete

    parsed_keys = [key for key in keys.split("/") if key]

    option_schema = DiscreteOptionSchema()
    options = option_schema.load(request.args)

    image = discrete(parsed_keys, tile_xyz=tile_xyz, **options)

    return send_file(image, mimetype="image/png")
