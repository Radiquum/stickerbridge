import tempfile
import os
import json
import yaml
import hashlib
import logging
from tqdm.auto import tqdm

from nio import MatrixRoom, AsyncClient

from chat_functions import has_permission, is_stickerpack_existing, get_stickerpack, upload_image, upload_stickerpack
from sticker_types import Sticker, MatrixStickerset, MauniumStickerset
from telegram_exporter import TelegramExporter

async def _parse_args(args: list) -> dict[str, str]:

    if os.path.exists('config.yaml'):
        with open("config.yaml", 'r') as config_file:
            config_params = yaml.safe_load(config_file)

    parsed_args = {
        "default": config_params['import']['primary'] or False,
        "json": config_params['import']['json'] or False,
        "artist" : None,
        "artist_url" : None,
        "rating" : None,
        "update_pack": config_params['import']['update_pack'] or False
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
        if arg in ["-p", "--primary", "-j", "--json", "-upd", "--update-pack"]:
            if arg in ["-p", "--primary"]:
                parsed_args["default"] = not parsed_args["default"]
            if arg in ["-j", "--json"]:
                parsed_args["json"] = not parsed_args["json"]
            if arg in ["-upd", "--update-pack"]:
                parsed_args["update_pack"] = not parsed_args["update_pack"]

    return parsed_args


class MatrixReuploader:

    STATUS_OK = 0
    STATUS_NO_PERMISSION = 1
    STATUS_PACK_EXISTS = 2
    STATUS_PACK_EMPTY = 3

    STATUS_DOWNLOADING = 4
    STATUS_UPLOADING = 5
    STATUS_UPDATING_ROOM_STATE = 6
    STATUS_PACK_UPDATE = 7

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

        pack_location = pack_name
        if parsed_args["default"]:
            pack_location = ""

        exists = await is_stickerpack_existing(self.client, self.room.room_id, pack_location)
        stickerpack = None;
        if exists:
            if parsed_args["update_pack"]:
                stickerpack = await get_stickerpack(self.client, self.room.room_id, pack_location)
                if parsed_args["rating"] is None:
                    parsed_args["rating"] = stickerpack["pack"].get("rating", None)
                if parsed_args["artist"] is None and stickerpack["pack"].get("artist", None) is not None:
                    parsed_args["artist"] = stickerpack["pack"]["artist"].get("name", None)
                if parsed_args["artist_url"] is None and stickerpack["pack"].get("url", None) is not None:
                    parsed_args["artist_url"] = stickerpack["pack"]["artist"].get("url", None)
                yield self.STATUS_PACK_UPDATE
            else:
                yield self.STATUS_PACK_EXISTS
                return

        yield self.STATUS_DOWNLOADING
        converted_stickerset = await self.exporter.get_stickerset(pack_name)
        yield self.STATUS_UPLOADING

        stickerset = MatrixStickerset(import_name, pack_name, parsed_args["rating"], {"name": parsed_args["artist"], "url": parsed_args["artist_url"]})
        json_stickerset = MauniumStickerset(import_name, pack_name, parsed_args["rating"], {"name": parsed_args["artist"], "url": parsed_args["artist_url"]}, self.room.room_id)

        with tqdm(total=len(converted_stickerset)) as tqdm_object:
            for sticker in converted_stickerset:
                with tempfile.NamedTemporaryFile('w+b', delete=False) as file:
                    file.write(sticker.image_data)
                    hash = hashlib.md5(sticker.image_data).hexdigest()
                    name = f"{pack_name}__{sticker.alt_text}__{os.path.basename(file.name)}"

                    sticker_mxc = None
                    if stickerpack is not None and stickerpack.get('images', None) is not None:
                        for stick in stickerpack['images'].values():
                            if stick.get('hash', None) is not None and stick["hash"] == hash:
                                sticker_mxc = stick["url"]
                                break

                    if sticker_mxc is None:
                        sticker_mxc = await upload_image(self.client, file.name, name)
                    file.close()
                    os.unlink(file.name)

                stickerset.add_sticker(sticker_mxc, sticker.alt_text, hash)
                if parsed_args["json"]:
                    json_stickerset.add_sticker(sticker_mxc, sticker.alt_text, sticker.width, sticker.height, sticker.size, sticker.mimetype)
                tqdm_object.update(1)

        if not stickerset.count():
            yield self.STATUS_PACK_EMPTY
            return

        yield self.STATUS_UPDATING_ROOM_STATE

        await upload_stickerpack(self.client, self.room.room_id, stickerset, pack_location)

        if parsed_args["json"]:
            if not os.path.exists(f"{os.getcwd()}/data/stickersets/"):
                os.mkdir(f"{os.getcwd()}/data/stickersets/")
            with open(f"{os.getcwd()}/data/stickersets/" + json_stickerset.id + ".json", "w", encoding="utf-8") as f:
                f.write(json.dumps(json_stickerset.json()))

        yield self.STATUS_OK
