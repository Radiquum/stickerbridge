from nio import AsyncClient, MatrixRoom

from chat_functions import send_text_to_room
from matrix_reuploader import MatrixReuploader
from telegram_exporter import TelegramExporter


class Command:
    def __init__(self, client: AsyncClient, room: MatrixRoom, command: str, tg_exporter: TelegramExporter):
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
            "import <pack_name> - Use this to import Telegram stickers from given link"
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
        reuploader = MatrixReuploader(self.client, self.room, exporter=self.tg_exporter)
        async for status in reuploader.import_stickerset_to_room(pack_name):
            text = 'Warning: Unknown status'
            if status == MatrixReuploader.STATUS_DOWNLOADING:
                text = f'Downloading stickerpack {pack_name}...'
            if status == MatrixReuploader.STATUS_UPLOADING:
                text = f'Uploading stickerpack {pack_name}...'
            if status == MatrixReuploader.STATUS_UPDATING_ROOM_STATE:
                text = f'Updating room state...️'

            if status == MatrixReuploader.STATUS_OK:
                text = 'Done 😄'
            if status == MatrixReuploader.STATUS_NO_PERMISSION:
                text = (
                    'I do not have permissions to create any stickerpack in this room\n'
                    'Please, give me mod 🙏'
                )
            if status == MatrixReuploader.STATUS_PACK_EXISTS:
                text = (
                    f"Stickerpack '{pack_name}' already exists.\n"
                    'Please delete it first.'
                )
            if status == MatrixReuploader.STATUS_PACK_EMPTY:
                text = (
                    f'Warning: Telegram pack {pack_name} find out empty or not existing.'
                )
            await send_text_to_room(self.client, self.room.room_id, text)

    async def _unknown_command(self):
        await send_text_to_room(
            self.client,
            self.room.room_id,
            f"Unknown command '{self.command}'. Try the 'help' command for more information.",
        )
