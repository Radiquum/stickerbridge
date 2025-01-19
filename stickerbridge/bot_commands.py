from nio import AsyncClient, MatrixRoom

from chat_functions import send_text_to_room
from matrix_reuploader import MatrixReuploader
from matrix_preview import MatrixPreview
from telegram_exporter import TelegramExporter

async def _parse_args(args: list[str], command: str) -> tuple[str, str, list[str]]:
        _pack_name = ""
        _parsed_args = []
        _import_name = []
        _is_import_name = False
        for index, arg in enumerate(args):
            if index == 0 and not arg.startswith("-"): # pack name should always be telegram pack shortName or full url
                if arg.startswith("http"):
                    _pack_name = arg.split("/")[-1]
                else:
                    _pack_name = arg
                continue

            if index == 1 and not arg.startswith("-") and arg.startswith("\""): # import name should always be 2nd arg
                arg = arg[1:]
                _is_import_name = True
            elif index == 1 and not arg.startswith("-") and command.split()[0].lower() != "preview":
                _import_name.append(arg)
                continue

            if _is_import_name and not arg.startswith("-") and arg.endswith("\""):
                if _is_import_name:
                    arg = arg.strip("\"")
                    _import_name.append(arg)
                _is_import_name = False
                continue

            if _is_import_name and not arg.startswith("-"):
                _import_name.append(arg)
                continue

            _parsed_args.append(arg) # everything else are a flag
            continue

        if len(_import_name) == 0: # finalizing the import name
            _import_name = _pack_name
        else:
            _import_name = " ".join(_import_name)

        return _pack_name, _import_name, _parsed_args

class Command:
    def __init__(
        self,
        client: AsyncClient,
        room: MatrixRoom,
        command: str,
        tg_exporter: TelegramExporter,
    ):
        self.client = client
        self.room = room
        self.command = command.lower()
        self.tg_exporter = tg_exporter
        self.args = command.split()[1:]

    async def process(self):
        if self.command.startswith("help"):
            await self._show_help()
        elif self.command.startswith("import"):
            await self._import_stickerpack()
        elif self.command.startswith("preview"):
            await self._generate_preview()
        else:
            await self._unknown_command()

    async def _show_help(self):
        text = (
            "I am the bot that imports stickers from Telegram and upload them to Matrix rooms\n\n"
            "List of commands:\n"
            "help - Show this help message.\n"
            "import <url|pack_name> [\"import name\"] - Use this to import a Telegram stickerpack.\n"
            "\tFlags:\n"
            "\t\t-p  | --primary - Use this flag if you want to upload pack as a default pack for this room\n"
            "\t\t-j  | --json - Use this flag if you want create maunium compatable json file with downloaded stickers\n"
            "\t\t-a  | --artist <artist> - Use this flag if you want to include sticker pack artist to json file\n"
            "\t\t-au | --artist-url <artist_url> - Use this flag if you want to add artist url to json file\n"
            "\t\t-r  | --rating <safe|questionable|explicit|s|q|e|sfw|nsfw> - Use this flag if you want add rating to json file\n"
            "\t\t-upd | --update-room - Update pack if it already exists\n"
            "\t\tIF boolean flags are true in config, and are provided, they are applied as a False.\n"
            "preview [pack_name] - Use this to create a preview for a Telegram stickers. If pack_name is not provided, then preview is generated for a primary pack.\n"
            "\tFlags:\n"
            "\t\t-tu | --tg-url [telegram_url|telegram_shortname] - Use this flag if you want to include stickerpack url in the last message\n"
            "\t\t-a | --artist [artist] - Use this flag if you want to include stickerpack artist in the last message and room topic\n"
            "\t\t-au | --artist-url [artist_url] - Use this flag if you want to add artist url in to the last message and room topic\n"
            "\t\t-s | --space [#space:homeserver] - Use this flag if you want to include space name in the room topic\n"
            "\t\t-pu | --preview-url [website_url] - Use this flag if you want to include stickerpack preview url in the room topic\n"
            "\t\t-upd | --update-room - Use this flag if you want to update room avatar, name and topic\n"
            "\t\tIF flags are provided, without parameters, then parameters are taken from the pack content if were provided on import or config!\n"
            "\t\tIF boolean flags are true in config, and are provided, they are applied as a False.\n"
        )
        await send_text_to_room(self.client, self.room.room_id, text)

    async def _import_stickerpack(self):
        if not self.args:
            text = (
                "You need to enter stickerpack name or url.\n"
                "Type command 'help' for more information."
            )
            await send_text_to_room(self.client, self.room.room_id, text)
            return

        pack_name, import_name, flags = await _parse_args(self.args, self.command)

        # TODO?: add --help flag

        #
        #   Flags:
        #       -p  | --primary - Use this flag if you want to upload pack as a default pack for this room
        #       -j  | --json - Use this flag if you want create maunium compatable json file with downloaded stickers
        #       -a  | --artist <artist> - Use this flag if you want to include stickerpack artist to json file
        #       -au | --artist-url <artist_url> - Use this flag if you want to add artist url to json file
        #       -r  | --rating <safe|questionable|explicit|s|q|e|sfw|nsfw> - Use this flag if you want add rating to json file
        #       IF boolean flags are true in config, and are provided, they are applied as a False.
        #

        reuploader = MatrixReuploader(self.client, self.room, exporter=self.tg_exporter)
        async for status in reuploader.import_stickerset_to_room(
            pack_name, import_name, flags
        ):
            switch = {
                MatrixReuploader.STATUS_DOWNLOADING: f"Downloading stickerpack {pack_name}...",
                MatrixReuploader.STATUS_UPLOADING: f"Uploading stickerpack {pack_name}...",
                MatrixReuploader.STATUS_UPDATING_ROOM_STATE: f"Updating room state...",
                MatrixReuploader.STATUS_OK: "Done",
                MatrixReuploader.STATUS_NO_PERMISSION: (
                    "I do not have permissions to create any stickerpack in this room\n"
                    "Please, give me mod 🙏"
                ),
                MatrixReuploader.STATUS_PACK_EXISTS: (
                    f"Stickerpack '{pack_name}' already exists.\n"
                    "Please delete it first."
                ),
                MatrixReuploader.STATUS_PACK_UPDATE: (
                    f"Updating Stickerpack '{pack_name}'.\n"
                ),
                MatrixReuploader.STATUS_PACK_EMPTY: (
                    f"Warning: Telegram pack {pack_name} find out empty or not existing."
                ),
            }
            text = switch.get(status, "Warning: Unknown status")
            await send_text_to_room(self.client, self.room.room_id, text)

    async def _generate_preview(self):
        pack_name, _, flags = await _parse_args(self.args, self.command)
        if pack_name == "":
            await send_text_to_room(
            self.client,
            self.room.room_id,
            f"Previewing primary pack")

        # TODO?: add --help flag

        #
        #   Flags:
        #       -tu | --tg-url [telegram_url|telegram_shortname] - Use this flag if you want to include stickerpack url in the last message.
        #       -a | --artist [artist] - Use this flag if you want to include stickerpack artist in the last message and room topic
        #       -au | --artist-url [artist_url] - Use this flag if you want to add artist url in to the last message and room topic
        #       -s | --space [#space:homeserver] - Use this flag if you want to include space name in the room topic
        #       -pu | --preview-url [website_url] - Use this flag if you want to include stickerpack preview url in the room topic
        #       -upd | --update-room - Use this flag if you want to update room avatar, name and topic
        #       IF flags are provided, without parameters, then parameters are taken from the pack content if were provided on import or config!
        #       IF boolean flags are true in config, and are provided, they are applied as a False.

        previewer = MatrixPreview(self.client, self.room)
        async for status in previewer.generate_stickerset_preview_to_room(pack_name, flags):
            switch = {
                MatrixPreview.STATUS_NO_PERMISSION: (
                    "I do not have permissions to update this room\n"
                    "Please, give me mod 🙏"
                ),
                MatrixPreview.STATUS_PACK_NOT_EXISTS: (
                    f"Stickerpack '{pack_name}' does not exists.\n"
                    "Please create it first."
                ),
                MatrixPreview.STATUS_UPDATING_ROOM_STATE: f"Updating room state...",
            }
            text = switch.get(status, "Warning: Unknown status")
            await send_text_to_room(self.client, self.room.room_id, text)

    async def _unknown_command(self):
        await send_text_to_room(
            self.client,
            self.room.room_id,
            f"Unknown command '{self.command}'. Try the 'help' command for more information.",
        )
