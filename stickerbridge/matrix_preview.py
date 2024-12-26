from nio import MatrixRoom, AsyncClient

from chat_functions import has_permission, is_stickerpack_existing, send_sticker_to_room, update_room_image, update_room_name, update_room_topic, send_text_to_room_as_text

async def _parse_args(args: list) -> dict[str, str]:

    parsed_args = {
        "space": None,
        "artist" : None,
        "artist_url": None,
        "tg_url": None,
        "preview_url": None,
        "update_room": False
    }

    if len(args) == 0:
        return parsed_args

    for index, arg in enumerate(args):
        if not arg.startswith("-"):
            continue
        if arg in ["-tu", "--tg-url", "-a", "--artist", "-au", "--artist-url", "-s", "--space", "-pu", "--preview-url"]:
            parameter = ""
            value = ""

            try:
                parameter = args[index]
                value = args[index + 1]
            except IndexError:
                continue

            if parameter in ["-tu", "--tg-url"]:
                if not value.startswith("https://t.me/addstickers/"):
                    value = f"https://t.me/addstickers/{value}"
                parsed_args["tg_url"] = value

            elif parameter in ["-a", "--artist"]:
                parsed_args["artist"] = value

            elif parameter in ["-au", "--artist-url"]:
                if not value.startswith("http"):
                    continue
                parsed_args["artist_url"] = value

            elif parameter in ["-s", "--space"]:
                if not value.startswith("#") or not ":" in value:
                    continue
                parsed_args["space"] = value

            elif parameter in ["-pu", "--preview-url"]:
                if not value.startswith("http"):
                    continue
                parsed_args["preview_url"] = value
        if arg in ["-upd", "--update-room"]:
            parsed_args["update_room"] = True

    return parsed_args


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

    async def generate_stickerset_preview_to_room(self, pack_name: str, flags: list):
        if not await self._has_permission_to_update():
            yield self.STATUS_NO_PERMISSION
            return

        if not await is_stickerpack_existing(self.client, self.room.room_id, pack_name):
            yield self.STATUS_PACK_NOT_EXISTS
            return

        parsed_args = await _parse_args(flags)

        yield self.STATUS_UPDATING_ROOM_STATE

        stickerpack = await self.client.room_get_state_event(self.room.room_id, 'im.ponies.room_emotes', pack_name)
        first_item = dict(list(stickerpack.content["images"].items())[:1])
        _first_item = first_item.popitem()

        topic = []
        message = []

        message.append(f"Stickerpack: {stickerpack.content['pack']['display_name']}")

        if parsed_args["space"]:
            topic.append(f"Space: {parsed_args['space']}")

        if parsed_args["artist"] or parsed_args["artist_url"]:
            if parsed_args["artist"] and parsed_args["artist_url"]:
                topic.append(f"Stickerpack by {parsed_args['artist']}: {parsed_args['artist_url']}")
                message.append(f"Artist: {parsed_args['artist']}: {parsed_args['artist_url']}")
            elif parsed_args["artist"]:
                topic.append(f"Stickerpack by {parsed_args['artist']}")
                message.append(f"Artist: {parsed_args['artist']}")
            elif parsed_args["artist_url"]:
                topic.append(f"Stickerpack by {parsed_args['artist_url']}")
                message.append(f"Artist: {parsed_args['artist_url']}")

        if parsed_args["tg_url"]:
            message.append(f"Telegram: {parsed_args['tg_url']}")
        if parsed_args["preview_url"]:
            topic.append(f"Preview: {parsed_args['tg_url']}")

        topic = " | ".join(topic)
        message = "\n".join(message)

        if parsed_args["update_room"]:
            await update_room_image(self.client, self.room.room_id, _first_item[1]['url'])
            await update_room_name(self.client, self.room.room_id, stickerpack.content["pack"]["display_name"])
            await update_room_topic(self.client, self.room.room_id, topic)

        # Sending stickers. min: 1, maximum: 5
        for stick in list(stickerpack.content["images"].items())[:5]:
            await send_sticker_to_room(self.client, self.room.room_id, {"body": stick[0], "url": stick[1]['url'], "info": {"mimetype":"image/png"}})
        await send_text_to_room_as_text(self.client, self.room.room_id, message)
