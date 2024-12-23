import tempfile
import os

from nio import MatrixRoom, AsyncClient

from chat_functions import has_permission, is_stickerpack_existing, send_text_to_room, upload_image, upload_stickerpack
from sticker_types import Sticker, MatrixStickerset
from telegram_exporter import TelegramExporter


class MatrixPreview:

    STATUS_OK = 0
    STATUS_NO_PERMISSION = 1

    STATUS_PACK_NOT_EXISTS = 2

    STATUS_UPDATING_ROOM_STATE = 3

    def __init__(self, client: AsyncClient, room: MatrixRoom):

        self.client = client
        self.room = room

    async def _has_permission_to_update(self) -> bool:
        return await has_permission(self.client, self.room.room_id, 'state_default')

    async def generate_stickerset_preview_to_room(self, pack_name: str):
        if not await self._has_permission_to_update():
            yield self.STATUS_NO_PERMISSION
            return

        name = pack_name
        if pack_name.lower() == "default":
            name = ""

        if not await is_stickerpack_existing(self.client, self.room.room_id, name):
            yield self.STATUS_PACK_NOT_EXISTS
            return

        stickerpack = await self.client.room_get_state_event(self.room.room_id, 'im.ponies.room_emotes', name)

        # {'pack': {'display_name': 'https://t.me/addstickers/kentai_radiquum'}, 'images': {'🤗': {'url': 'mxc://wah.su/OzamJbZNgcIIDeMXofMnmkBO', 'usage': ['sticker']}, '🤗-1': {...}}}

        print(stickerpack)
        # yield self.STATUS_DOWNLOADING
        # converted_stickerset = await self.exporter.get_stickerset(pack_name)
        # yield self.STATUS_UPLOADING
        # for sticker in converted_stickerset:
        #     with tempfile.NamedTemporaryFile('w+b', delete=False) as file:
        #         file.write(sticker.image_data)
        #         sticker_mxc = await upload_image(self.client, file.name)

        #         file.close()
        #         os.unlink(file.name)

        #     stickerset.add_sticker(sticker_mxc, sticker.alt_text)

        # if not stickerset.count():
        #     yield self.STATUS_PACK_EMPTY
        #     return

        yield self.STATUS_UPDATING_ROOM_STATE

        

        # await upload_stickerpack(self.client, self.room.room_id, stickerset, name)

        yield self.STATUS_OK
