from nio import MatrixRoom, AsyncClient

from chat_functions import has_permission, is_stickerpack_existing, send_sticker_to_room, update_room_image

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

        if not await is_stickerpack_existing(self.client, self.room.room_id, pack_name):
            yield self.STATUS_PACK_NOT_EXISTS
            return

        yield self.STATUS_UPDATING_ROOM_STATE

        stickerpack = await self.client.room_get_state_event(self.room.room_id, 'im.ponies.room_emotes', pack_name)
        first_item = dict(list(stickerpack.content["images"].items())[:1])
        _first_item = first_item.popitem()
        await update_room_image(self.client, self.room.room_id, {"url": _first_item[1]['url']})

        for stick in list(stickerpack.content["images"].items())[:5]:
            await send_sticker_to_room(self.client, self.room.room_id, {"body": stick[0], "url": stick[1]['url'], "info": {"mimetype":"image/png"}})

        yield self.STATUS_OK
