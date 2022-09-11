import tempfile

from nio import MatrixRoom, AsyncClient

from chat_functions import has_permission, is_stickerpack_existing, send_text_to_room, upload_image, upload_stickerpack
from sticker_types import Sticker, MatrixStickerset
from telegram_exporter import TelegramExporter


class MatrixReuploader:

    RESULT_OK = 0
    RESULT_NO_PERMISSION = 1
    RESULT_PACK_EXISTS = 2
    RESULT_PACK_EMPTY = 3

    STATUS_DOWNLOADING = 1
    STATUS_UPLOADING = 2
    STATUS_UPDATING_ROOM_STATE = 3

    def __init__(self, client: AsyncClient, room: MatrixRoom, exporter: TelegramExporter = None,
                 pack: list[Sticker] = None):

        if not exporter and not pack:
            raise ValueError('Either exporter or the pack must be set')

        self.client = client
        self.room = room
        self.exporter = exporter
        self.pack = pack

        self.result = -1

    async def _has_permission_to_upload(self) -> bool:
        return await has_permission(self.client, self.room.room_id, 'state_default')

    async def import_stickerset_to_room(self, pack_name: str):
        if not await self._has_permission_to_upload():
            self.result = self.RESULT_NO_PERMISSION
            return

        stickerset = MatrixStickerset(pack_name)
        if await is_stickerpack_existing(self.client, self.room.room_id, stickerset.name()):
            self.result = self.RESULT_PACK_EXISTS
            return

        yield self.STATUS_DOWNLOADING
        converted_stickerset = await self.exporter.get_stickerset(stickerset.name())
        yield self.STATUS_UPLOADING
        for sticker in converted_stickerset:
            with tempfile.NamedTemporaryFile('w+b') as file:
                file.write(sticker.image_data)
                sticker_mxc = await upload_image(self.client, file.name, sticker.mime_type)
            stickerset.add_sticker(sticker_mxc, sticker.alt_text)

        if not stickerset.count():
            self.result = self.RESULT_PACK_EMPTY
            return

        yield self.STATUS_UPDATING_ROOM_STATE
        await upload_stickerpack(self.client, self.room.room_id, stickerset)

        self.result = self.RESULT_OK
