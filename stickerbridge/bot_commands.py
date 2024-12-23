from nio import AsyncClient, MatrixRoom

from chat_functions import send_text_to_room
from matrix_reuploader import MatrixReuploader
from telegram_exporter import TelegramExporter


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
        self.args = self.command.split()[1:]

    async def process(self):
        if self.command.startswith("help"):
            await self._show_help()
        elif self.command.startswith("import"):
            await self._import_stickerpack()
        else:
            await self._unknown_command()

    async def _show_help(self):
        text = (
            "I am the bot that imports stickers from Telegram and upload them to Matrix rooms\n\n"
            "List of commands:\n"
            "help - Show this help message.\n"
            "import <url|pack_name> [import_name] - Use this to import Telegram stickers from given link. import_name is pack_name if not provided"
        )
        await send_text_to_room(self.client, self.room.room_id, text)

    async def _import_stickerpack(self):
        if not self.args:
            text = (
                "You need to enter stickerpack name.\n"
                "Type command 'help' for more information."
            )
            await send_text_to_room(self.client, self.room.room_id, text)
            return

        pack_name = self.args[0]
        import_name = self.args[1] if len(self.args) > 1 else pack_name
        reuploader = MatrixReuploader(self.client, self.room, exporter=self.tg_exporter)
        async for status in reuploader.import_stickerset_to_room(
            pack_name, import_name
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
                MatrixReuploader.STATUS_PACK_EMPTY: (
                    f"Warning: Telegram pack {pack_name} find out empty or not existing."
                ),
            }
            text = switch.get(status, "Warning: Unknown status")
            await send_text_to_room(self.client, self.room.room_id, text)

    async def _unknown_command(self):
        await send_text_to_room(
            self.client,
            self.room.room_id,
            f"Unknown command '{self.command}'. Try the 'help' command for more information.",
        )
