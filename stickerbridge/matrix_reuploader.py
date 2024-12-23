import tempfile
import os

from nio import MatrixRoom, AsyncClient

from chat_functions import has_permission, is_stickerpack_existing, send_text_to_room, upload_image, upload_stickerpack
from sticker_types import Sticker, MatrixStickerset
from telegram_exporter import TelegramExporter


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

    async def import_stickerset_to_room(self, pack_name: str, import_name: str, isDefault: bool):
        if not await self._has_permission_to_upload():
            yield self.STATUS_NO_PERMISSION
            return

        name = import_name
        if import_name.startswith("http"):
            name = import_name.split("/")[-1]

        stickerset = MatrixStickerset(name)
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

        if not stickerset.count():
            yield self.STATUS_PACK_EMPTY
            return

        yield self.STATUS_UPDATING_ROOM_STATE

        pack_location = import_name
        if isDefault:
            pack_location = ""
        elif pack_location.startswith("http"):
            pack_location = pack_location.split("/")[-1]

        await upload_stickerpack(self.client, self.room.room_id, stickerset, pack_location)

        yield self.STATUS_OK
