import tempfile
import os
import json

from nio import MatrixRoom, AsyncClient

from chat_functions import has_permission, is_stickerpack_existing, upload_image, upload_stickerpack
from sticker_types import Sticker, MatrixStickerset, MauniumStickerset
from telegram_exporter import TelegramExporter

async def _parse_args(args: list) -> dict[str, str]:

    parsed_args = {
        "default": False,
        "json": False,
        "artist" : "",
        "artist_url" : "",
        "rating" : ""
    }

    if len(args) == 0:
        return parsed_args

    for index, arg in enumerate(args):
        if not arg.startswith("-"):
            continue
        if arg in ["-a", "--artist", "-au", "--artist-url", "-r", "--rating"]:
            parameter = ""
            value: str = ""

            try:
                parameter = args[index]
                value = args[index + 1]
            except IndexError:
                continue

            if parameter in ["-r", "--rating"]:
                if value.lower() not in ["s", "safe", "sfw", "q", "questionable", 'e', 'explicit', "nsfw"]:
                    continue
                if value.lower() in ["s", "safe", "sfw"]:
                    value = "Safe"
                elif value.lower() in ["q", "questionable"]:
                    value = "Questionable"
                elif value.lower() in ['e', 'explicit', 'nsfw']:
                    value = "Explicit"
                parsed_args["rating"] = value
            elif parameter in ["-a", "--artist"]:
                parsed_args["artist"] = value
            elif parameter in ["-au", "--artist-url"]:
                if not value.startswith("http"):
                    continue
                parsed_args["artist_url"] = value
        if arg in ["-p", "--primary", "-j", "--json"]:
            if arg in ["-p", "--primary"]:
                parsed_args["default"] = True
            if arg in ["-j", "--json"]:
                parsed_args["json"] = True

    return parsed_args


class MatrixReuploader:

    STATUS_OK = 0
    STATUS_NO_PERMISSION = 1
    STATUS_PACK_EXISTS = 2
    STATUS_PACK_EMPTY = 3

    STATUS_DOWNLOADING = 4
    STATUS_UPLOADING = 5
    STATUS_UPDATING_ROOM_STATE = 6

    def __init__(self, client: AsyncClient, room: MatrixRoom, exporter: TelegramExporter = None,
                 pack: list[Sticker] = None):

        if not exporter and not pack:
            raise ValueError('Either exporter or the pack must be set')

        self.client = client
        self.room = room
        self.exporter = exporter
        self.pack = pack

    async def _has_permission_to_upload(self) -> bool:
        return await has_permission(self.client, self.room.room_id, 'state_default')

    async def import_stickerset_to_room(self, pack_name: str, import_name: str, args: list[str]):
        if not await self._has_permission_to_upload():
            yield self.STATUS_NO_PERMISSION
            return

        parsed_args = await _parse_args(args)

        stickerset = MatrixStickerset(import_name)
        json_stickerset = MauniumStickerset(import_name, pack_name, parsed_args["rating"], {"name": parsed_args["artist"], "url": parsed_args["artist_url"]}, self.room.room_id)
        if await is_stickerpack_existing(self.client, self.room.room_id, stickerset.name()):
            yield self.STATUS_PACK_EXISTS
            return

        yield self.STATUS_DOWNLOADING
        converted_stickerset = await self.exporter.get_stickerset(pack_name)
        yield self.STATUS_UPLOADING
        for sticker in converted_stickerset:
            with tempfile.NamedTemporaryFile('w+b', delete=False) as file:
                file.write(sticker.image_data)
                sticker_mxc = await upload_image(self.client, file.name)

                file.close()
                os.unlink(file.name)

            stickerset.add_sticker(sticker_mxc, sticker.alt_text)
            if parsed_args["json"]:
                json_stickerset.add_sticker(sticker_mxc, sticker.alt_text, sticker.width, sticker.height, sticker.size, sticker.mimetype)

        if not stickerset.count():
            yield self.STATUS_PACK_EMPTY
            return

        yield self.STATUS_UPDATING_ROOM_STATE

        pack_location = pack_name
        if parsed_args["default"]:
            pack_location = ""

        await upload_stickerpack(self.client, self.room.room_id, stickerset, pack_location)

        if parsed_args["json"]:
            if not os.path.exists(f"{os.getcwd()}/data/stickersets/"):
                os.mkdir(f"{os.getcwd()}/data/stickersets/")
            with open(f"{os.getcwd()}/data/stickersets/" + json_stickerset.id + ".json", "w", encoding="utf-8") as f:
                f.write(json.dumps(json_stickerset.json()))

        yield self.STATUS_OK
