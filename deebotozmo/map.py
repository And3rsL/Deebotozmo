import base64
import logging
import lzma
import struct
from io import BytesIO
from typing import Optional, List

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from deebotozmo import ROOMS_FROM_ECOVACS
from deebotozmo.models import Coordinate

_LOGGER = logging.getLogger(__name__)


def _decompress_7z_base64_data(data):
    _LOGGER.debug("[decompress7zBase64Data] Begin")
    final_array = bytearray()

    # Decode Base64
    data = base64.b64decode(data)

    i = 0
    for idx in data:
        if i == 8:
            final_array += b'\x00\x00\x00\x00'
        final_array.append(idx)
        i += 1

    dec = lzma.LZMADecompressor(lzma.FORMAT_AUTO, None, None)
    decompressed_data = dec.decompress(final_array)

    _LOGGER.debug("[decompress7zBase64Data] Done")
    return decompressed_data


def _draw_position(position: Coordinate, png_str: str, im: Image, pixel_width: int, offset: int):
    icon = Image.open(BytesIO(base64.b64decode(png_str)))
    im.paste(icon, (int(((position.x / pixel_width) + offset)),
                    int(((position.y / pixel_width) + offset))),
             icon.convert('RGBA'))


def _calc_coordinate(value: Optional[int], pixel_width: int, offset: int):
    try:
        if value is not None:
            return (int(value) / pixel_width) + offset
    except:
        pass

    return 0


class Map:
    COLORS = {
        0x01: "#badaff",  # floor
        0x02: "#4e96e2",  # wall
        0x03: "#1a81ed",  # carpet
        "tracemap": "#FFFFFF"
    }

    ROOM_COLORS = [
        (238, 225, 235, 255),
        (239, 236, 221, 255),
        (228, 239, 223, 255),
        (225, 234, 239, 255),
        (238, 223, 216, 255),
        (240, 228, 216, 255),
        (233, 139, 157, 255),
        (239, 200, 201, 255),
        (201, 2019, 239, 255)
    ]

    ROBOT_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAYAAAAGCAIAAABvrngfAAAACXBIWXMAAAsTAAALEwEAmpwYAAAF0WlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDUgNzkuMTYzNDk5LCAyMDE4LzA4LzEzLTE2OjQwOjIyICAgICAgICAiPiA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPiA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIiB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIiB4bWxuczpzdEV2dD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlRXZlbnQjIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgQ0MgMjAxOSAoV2luZG93cykiIHhtcDpDcmVhdGVEYXRlPSIyMDIwLTA1LTI0VDEyOjAzOjE2KzAyOjAwIiB4bXA6TWV0YWRhdGFEYXRlPSIyMDIwLTA1LTI0VDEyOjAzOjE2KzAyOjAwIiB4bXA6TW9kaWZ5RGF0ZT0iMjAyMC0wNS0yNFQxMjowMzoxNiswMjowMCIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDo0YWM4NWY5MC1hNWMwLTE2NDktYTQ0MC0xMWM0NWY5OGQ1MDYiIHhtcE1NOkRvY3VtZW50SUQ9ImFkb2JlOmRvY2lkOnBob3Rvc2hvcDo3Zjk3MTZjMi1kZDM1LWJiNDItYjMzZS1hYjYwY2Y4ZTZlZDYiIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDpiMzhiNGZlMS1lOGNkLTJjNDctYmQwZC1lNmZiNzRhMjFkMDciIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIj4gPHhtcE1NOkhpc3Rvcnk+IDxyZGY6U2VxPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0iY3JlYXRlZCIgc3RFdnQ6aW5zdGFuY2VJRD0ieG1wLmlpZDpiMzhiNGZlMS1lOGNkLTJjNDctYmQwZC1lNmZiNzRhMjFkMDciIHN0RXZ0OndoZW49IjIwMjAtMDUtMjRUMTI6MDM6MTYrMDI6MDAiIHN0RXZ0OnNvZnR3YXJlQWdlbnQ9IkFkb2JlIFBob3Rvc2hvcCBDQyAyMDE5IChXaW5kb3dzKSIvPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiIHN0RXZ0Omluc3RhbmNlSUQ9InhtcC5paWQ6NGFjODVmOTAtYTVjMC0xNjQ5LWE0NDAtMTFjNDVmOThkNTA2IiBzdEV2dDp3aGVuPSIyMDIwLTA1LTI0VDEyOjAzOjE2KzAyOjAwIiBzdEV2dDpzb2Z0d2FyZUFnZW50PSJBZG9iZSBQaG90b3Nob3AgQ0MgMjAxOSAoV2luZG93cykiIHN0RXZ0OmNoYW5nZWQ9Ii8iLz4gPC9yZGY6U2VxPiA8L3htcE1NOkhpc3Rvcnk+IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiA8P3hwYWNrZXQgZW5kPSJyIj8+AP7+NwAAAFpJREFUCJllzEEKgzAQhtFvMkSsEKj30oUXrYserELA1obhd+nCd4BnksZ53X4Cnr193ov59Iq+o2SA2vz4p/iKkgkRouTYlbhJ/jBqww03avPBTNI4rdtx9ScfWyYCg52e0gAAAABJRU5ErkJggg=="
    CHARGER_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAOCAYAAAAWo42rAAAAdUlEQVQoU2NkQAP/nzD8BwkxyjAwIkuhcEASRCmEKYKZhGwq3ER0ReiKSVOIyzRkU8EmwhUyKzAwSNyHyL9QZGD4+wDMBLmVEasimFHIiuEKpcHBhwmeQryBMJFohcjuw2s1SBKHZ8BWo/gauyshvobJEYoZAEOSPXnhzwZnAAAAAElFTkSuQmCC"

    def __init__(self, draw_rooms: bool):
        self._draw_rooms: bool = draw_rooms
        self._robot_position: Optional[Coordinate] = None
        self._charger_position: Optional[Coordinate] = None

        self.buffer = np.zeros((64, 100, 100))
        self.mapPieces = np.empty(64, np.dtype('U100'))
        self.isMapUpdated = False
        self.base64Image = None
        self.rooms = []
        self.traceValues = []
        self.draw_charger = False
        self.draw_robot = False
        self.resize_factor = 3

    # ---------------------------- EVENT HANDLING ----------------------------

    def handle(self, event_name: str, event_data: dict):
        if event_name == "minormap":
            self._handle_minor_map(event_data)
        elif event_name == "majormap":
            self._handle_major_map(event_data)
        elif event_name == "mapset":
            self._handle_map_set(event_data)
        elif event_name == "mapsubset":
            self._handle_map_sub_set(event_data)
        elif event_name == "pos":
            self._handle_position(event_data)
        elif event_name == "maptrace":
            self._handle_map_trace(event_data)
        elif event_name == "cachedmapinfo":
            self._handle_cached_map(event_data)
        else:
            _LOGGER.debug(f"Unknown event: {event_name} with {event_data}")

    def _handle_position(self, event):
        response = event["body"]["data"]

        self._update_position(response.get("chargePos", {}), True)
        self._update_position(response.get("deebotPos", {}), False)

    def _handle_minor_map(self, event):
        response = event["body"]["data"]
        self._add_map_piece(response["pieceIndex"], response["pieceValue"])

    def _handle_map_sub_set(self, event):
        response = event["body"]["data"]
        subtype = int(response["subtype"])
        value = response["value"]

        self.rooms.append(
            {
                "subtype": ROOMS_FROM_ECOVACS[subtype],
                "id": int(response["mssid"]),
                "values": value,
            }
        )

    def _handle_map_trace(self, event):
        response = event["body"]["data"]
        totalCount = int(response["totalCount"])
        traceStart = int(response["traceStart"])
        pointCount = 200

        # No trace value avaiable
        if "traceValue" in response:
            if traceStart == 0:
                self.traceValues = []

            self._update_trace_points(response["traceValue"])

            if (traceStart + pointCount) < totalCount:
                self.exc_command(
                    "getMapTrace",
                    {"pointCount": pointCount, "traceStart": traceStart + pointCount},
                )

    def _handle_major_map(self, event):
        _LOGGER.debug("_handle_major_map begin")
        response = event["body"]["data"]

        values = response["value"].split(",")

        for i in range(64):
            if self._is_update_piece(i, values[i]):
                _LOGGER.debug("MapPiece" + str(i) + " needs to be updated")
                self.exc_command(
                    "getMinorMap",
                    {"mid": response["mid"], "type": "ol", "pieceIndex": i},
                )

    def _handle_cached_map(self, event):
        response = event["body"]["data"]

        try:
            mapid = None
            for mapstatus in response["info"]:
                if mapstatus["using"] == 1:
                    mapid = mapstatus["mid"]

                    # IF MAP CHANGED WE SHOULD REFRESH ROOMS
                    if self.inuse_mapid != mapid:
                        self.inuse_mapid = mapid
                        self.refresh_rooms()

                    _LOGGER.debug("Using Map: " + str(mapid))

            self.rooms = []
            self.exc_command("getMapSet", {"mid": mapid, "type": "ar"})
        except:
            _LOGGER.warning(
                "MapID not found -- did you finish your first auto cleaning?"
            )

    def _handle_map_set(self, event):
        response = event["body"]["data"]

        mid = response["mid"]
        msid = response["msid"]
        typemap = response["type"]

        for s in response["subsets"]:
            self.exc_command(
                "getMapSubSet",
                {"mid": mid, "msid": msid, "type": typemap, "mssid": s["mssid"]},
            )

    # ---------------------------- METHODS ----------------------------

    def _add_map_piece(self, map_piece, b64):
        _LOGGER.debug(f"[AddMapPiece] {map_piece} {b64}")

        decoded = _decompress_7z_base64_data(b64)
        piece = np.reshape(list(decoded), (100, 100))

        self.buffer[map_piece] = piece
        _LOGGER.debug("[AddMapPiece] Done")

    def _update_position(self, new_values: dict, is_charger: bool):
        current_value: Coordinate = self._charger_position if is_charger else self._robot_position
        name = "charger" if is_charger else "robot"
        x = new_values.get("x")
        y = new_values.get("y")

        if x is None or y is None:
            _LOGGER.warning("Could not pars position event")
            return

        if current_value:
            if (current_value.x != x) or (current_value.y != y):
                _LOGGER.debug(f"Updating {name} position: {x}, {y}")
                current_value = Coordinate(x=x, y=y)
                self.isMapUpdated = False
        else:
            _LOGGER.debug(f"Setting {name} position: {x}, {y}")
            current_value = Coordinate(x=x, y=y)
            self.isMapUpdated = False
            self.draw_robot = True

        if is_charger:
            self._charger_position = current_value
        else:
            self._robot_position = current_value

    def _drawing_rooms(self, im: Image, draw: ImageDraw, pixel_width: int, offset: int):
        num = 0
        _LOGGER.debug("Draw rooms")

        for room in self.rooms:
            _LOGGER.debug(f"Draw room: {num}")
            coords = room['values'].split(';')
            list_cord = []
            sum_x = 0
            sum_y = 0

            for cord in coords:
                xy: List[int] = cord.split(',')

                x = _calc_coordinate(xy[0], pixel_width, offset)
                y = _calc_coordinate(xy[1], pixel_width, offset)

                list_cord.append(x)
                list_cord.append(y)

                # Sum for center point
                sum_x = sum_x + x
                sum_y = sum_y + y

            draw.line(list_cord, fill=(255, 0, 0), width=1)

            center_x = sum_x / len(coords)
            center_y = sum_y / len(coords)

            ImageDraw.floodfill(im, xy=(center_x, center_y), value=Map.ROOM_COLORS[num % len(Map.ROOM_COLORS)])
            draw.line(list_cord, fill=(0, 0, 0, 0), width=1)
            num += 1

    def _is_update_piece(self, index: int, map_piece):
        _LOGGER.debug(f"[_is_update_piece] Check {index} {map_piece}")
        value = f"{index}-{map_piece}"

        if self.mapPieces[index] != value:
            self.mapPieces[index] = value

            if str(map_piece) != '1295764014':
                self.isMapUpdated = False
                return True
            else:
                return False

        _LOGGER.debug("[_is_update_piece] No need to update")

    def _update_trace_points(self, data):
        _LOGGER.debug("[_update_trace_points] Begin")
        trace_points = _decompress_7z_base64_data(data)
        h = "h" * 1

        for i in range(0, len(trace_points), 5):
            byte_position_x = struct.unpack('<' + h, trace_points[i:i + 2])
            byte_position_y = struct.unpack('<' + h, trace_points[i + 2:i + 4])

            # Add To List
            position_x = (int(byte_position_x[0] / 5)) + 400
            position_y = (int(byte_position_y[0] / 5)) + 400

            self.traceValues.append(position_x)
            self.traceValues.append(position_y)

        _LOGGER.debug("[_update_trace_points] finish")

    def get_base64_map(self):
        if self.isMapUpdated:
            _LOGGER.debug("[get_base64_map] No need to update")
            return self.base64Image

        _LOGGER.debug("[get_base64_map] Begin")

        pixel_width = 50
        offset = 400
        im = Image.new("RGBA", (6400, 6400))
        draw = ImageDraw.Draw(im)

        if self._draw_rooms:
            self._drawing_rooms(im, draw, pixel_width, offset)

        _LOGGER.debug("[get_base64_map] Draw Map")
        image_x = 0
        image_y = 0

        for i in range(64):
            if i > 0:
                if i % 8 != 0:
                    image_y += 100
                else:
                    image_x += 100
                    image_y = 0

            for y in range(100):
                for x in range(100):
                    point_x = image_x + x
                    point_y = image_y + y
                    if (point_x > 6400) or (point_y > 6400):
                        _LOGGER.error(f"[get_base64_map] Map Limit 6400!! X: {point_x} Y: {point_y}")

                    type = self.buffer[i][x][y]
                    if type in [0x01, 0x02, 0x03]:
                        if im.getpixel((point_x, point_y)) == (0, 0, 0, 0):
                            draw.point((point_x, point_y), fill=Map.COLORS[type])

        # Draw Trace Route
        if len(self.traceValues) > 0:
            _LOGGER.debug("[get_base64_map] Draw Trace")
            draw.line(self.traceValues, fill=Map.COLORS['tracemap'], width=1)

        del draw

        if self.draw_robot:
            _LOGGER.debug("[get_base64_map] Draw robot")
            _draw_position(self._robot_position, Map.ROBOT_PNG, im, pixel_width, offset)

        if self.draw_charger:
            _LOGGER.debug("[get_base64_map] Draw charge station")
            _draw_position(self._charger_position, Map.CHARGER_PNG, im, pixel_width, offset)

        _LOGGER.debug("[get_base64_map] Crop Image")
        image_box = im.getbbox()
        cropped = im.crop(image_box)
        del im

        _LOGGER.debug("[get_base64_map] Flipping Image")
        cropped = ImageOps.flip(cropped)

        _LOGGER.debug("[get_base64_map] Map current Size: X: " + str(cropped.size[0]) + ' Y: ' + str(cropped.size[1]))
        if cropped.size[0] > 400 or cropped.size[1] > 400:
            _LOGGER.debug("[get_base64_map] Resize disabled.. map over 400")
        else:
            _LOGGER.debug("[get_base64_map] Resize * " + str(self.resize_factor))
            cropped = cropped.resize((cropped.size[0] * self.resize_factor, cropped.size[1] * self.resize_factor),
                                     Image.NEAREST)

        _LOGGER.debug("[get_base64_map] Saving to buffer")
        buffered = BytesIO()
        cropped.save(buffered, format="PNG")
        del cropped

        self.isMapUpdated = True
        self.base64Image = base64.b64encode(buffered.getvalue())
        _LOGGER.debug("[GetBase64Map] Finish")

        return self.base64Image
