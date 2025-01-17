from nio import MatrixRoom, AsyncClient
import yaml
import os

from chat_functions import has_permission, is_stickerpack_existing, get_stickerpack, send_sticker_to_room, update_room_image, update_room_name, update_room_topic, send_text_to_room_as_text

async def _parse_args(args: list, stickerpack) -> dict[str, str]:

    if os.path.exists('config.yaml'):
        with open("config.yaml", 'r') as config_file:
            config_params = yaml.safe_load(config_file)

    parsed_args = {
        "space": config_params['preview']['space'] or None,
        "artist" : None,
        "artist_url": None,
        "tg_url": None,
        "preview_url": config_params['preview']['preview_url_base'] or None,
        "update_room": config_params['preview']['update_room'] or False
    }

    if len(args) == 0:
        return parsed_args, config_params

    for index, arg in enumerate(args):
        if not arg.startswith("-"):
            continue
        if arg in ["-tu", "--tg-url", "-a", "--artist", "-au", "--artist-url", "-s", "--space", "-pu", "--preview-url"]:
            parameter = ""
            value = ""

            try:
                parameter = args[index]
                value = args[index + 1]
                if value.startswith("-"):
                    raise IndexError
            except IndexError:
                value = None

            if parameter in ["-tu", "--tg-url"]:
                if value is None and stickerpack['pack'].get('pack_id', None) is not None:
                    value = stickerpack['pack']['pack_id']
                if value is not None and not value.startswith("https://t.me/addstickers/"):
                    value = f"https://t.me/addstickers/{value}"
                parsed_args["tg_url"] = value

            elif parameter in ["-a", "--artist"]:
                if value is None and stickerpack['pack'].get('author', None) is not None and stickerpack['pack']['author'].get('name', None) is not None:
                    value = stickerpack['pack']['author']['name']
                if value is not None:
                    parsed_args["artist"] = value

            elif parameter in ["-au", "--artist-url"]:
                if value is None and stickerpack['pack'].get('author', None) is not None and stickerpack['pack']['author'].get('url', None) is not None:
                    value = stickerpack['pack']['author']['url']
                if value is not None:
                    if not value.startswith("http"):
                        value = f"https://{value}"
                    parsed_args["artist_url"] = value

            elif parameter in ["-s", "--space"]:
                if value is not None and (not value.startswith("#") or not ":" in value):
                        value = None
                        print("wrong space name format! ignoring...")
                parsed_args["space"] = value

            elif parameter in ["-pu", "--preview-url"]:
                if value is not None and not value.startswith("http"):
                    value = None
                parsed_args["preview_url"] = value

        if arg in ["-upd", "--update-room"]:
            parsed_args["update_room"] = not config_params['preview']['update_room']

    return parsed_args, config_params


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

        stickerpack = await get_stickerpack(self.client, self.room.room_id, pack_name)
        parsed_args, config_params = await _parse_args(flags, stickerpack)

        yield self.STATUS_UPDATING_ROOM_STATE

        first_item = dict(list(stickerpack["images"].items())[:1])
        _first_item = first_item.popitem()

        topic = []
        message = []

        message.append(f"Stickerpack: {stickerpack['pack']['display_name']}")

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
            if parsed_args["preview_url"] == config_params['preview']['preview_url_base'] and stickerpack['pack'].get('pack_id', None) is not None:
                parsed_args["preview_url"] = f"{parsed_args['preview_url']}{stickerpack['pack'].get('pack_id', None)}"
            if parsed_args["preview_url"] != config_params['preview']['preview_url_base'] and parsed_args["preview_url"] is not None:
                topic.append(f"Preview: {parsed_args['preview_url']}")

        topic = " | ".join(topic)
        message = "\n".join(message)

        if parsed_args["update_room"]:
            await update_room_image(self.client, self.room.room_id, _first_item[1]['url'])
            await update_room_name(self.client, self.room.room_id, stickerpack["pack"]["display_name"])
            await update_room_topic(self.client, self.room.room_id, topic)

        # Sending stickers. min: 1, maximum: 5
        for stick in list(stickerpack["images"].items())[:5]:
            await send_sticker_to_room(self.client, self.room.room_id, {"body": stick[0], "url": stick[1]['url'], "info": {"mimetype":"image/png"}})
        await send_text_to_room_as_text(self.client, self.room.room_id, message)
