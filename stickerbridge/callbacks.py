import logging
import traceback

from nio import AsyncClient, MatrixRoom, RoomMessageText, InviteMemberEvent

from bot_commands import Command
from chat_functions import send_text_to_room
from telegram_exporter import TelegramExporter


class Callbacks:
    def __init__(self, client: AsyncClient, command_prefix: str, config: dict, tg_exporter: TelegramExporter):
        self.client = client
        self.command_prefix = command_prefix
        self.config = config
        self.tg_exporter = tg_exporter

    async def sync(self, response):
        with open('data/next_batch', 'w') as next_batch_token:
            next_batch_token.write(response.next_batch)

    async def message(self, room: MatrixRoom, event: RoomMessageText) -> None:

        # Ignore messages from ourselves
        if event.sender == self.client.user:
            return

        # Do not respond to m.notice (https://spec.matrix.org/v1.3/client-server-api/#mnotice)
        if event.source['content']['msgtype'] == 'm.notice':
            return

        if event.body.startswith(self.command_prefix) or room.member_count <= 2:
            command_string = event.body.replace(self.command_prefix, '').strip()
            command = Command(self.client, room, command_string, self.tg_exporter)
            try:
                await command.process()
            except Exception as e:
                logging.error(traceback.format_exc())
                await send_text_to_room(self.client, room.room_id, 'Sorry, there was an internal error:\n' + str(e))

    async def autojoin_room(self, room: MatrixRoom, event: InviteMemberEvent):

        # Only react to invites for us
        if not event.state_key == self.client.user_id:
            return

        await self.client.join(room.room_id)
        text = (
            f"Hi, I'm a {self.config['matrix_bot_name']}.\n"
            "Type '!sb help' to display available commands.\n\n"
            "Please do note this bot would not work in encrypted rooms."
        )
        await send_text_to_room(self.client, room.room_id, text)
