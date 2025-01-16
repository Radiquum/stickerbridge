import asyncio
import os
import shutil
import tempfile

import yaml
import logging

from nio import AsyncClient, SyncResponse, RoomMessageText, InviteEvent, InviteMemberEvent

from callbacks import Callbacks
from chat_functions import upload_avatar
from telegram_exporter import TelegramExporter


async def main():
    os.makedirs('data', exist_ok=True)
    if not os.path.exists('config.yaml'):
        shutil.copy('config.yaml.example', 'config.yaml')
        logging.warning('Please fill in config.yaml file, then restart the bot')
        return
    with open("config.yaml", 'r') as config_file:
        config = yaml.safe_load(config_file)

    logging.basicConfig(level=os.environ.get("LOGLEVEL", config['log_level']))

    client = AsyncClient(config['matrix_homeserver'], config['matrix_username'])
    client.device_id = config['matrix_bot_name']

    tg_exporter = TelegramExporter(config['telegram_api_id'], config['telegram_api_hash'], config['telegram_bot_token'],
                                   'data/telegram_secrets')
    await tg_exporter.connect()

    callbacks = Callbacks(client, config['command_prefix'], config, tg_exporter)
    client.add_response_callback(callbacks.sync, SyncResponse)
    client.add_event_callback(callbacks.message, RoomMessageText)
    client.add_event_callback(callbacks.autojoin_room, InviteMemberEvent)

    if config['matrix_login_type'] == 'password':
        if not config['matrix_password']:
            logging.warning('Please fill in config.yaml file, then restart the bot')
            raise ValueError(f'No Password')
        login_response = await client.login(config['matrix_password'])
    elif config['matrix_login_type'] == 'access_token':
        if not config['matrix_token'] or not config['matrix_deviceid']:
            logging.warning('Please fill in config.yaml file, then restart the bot')
            raise ValueError(f'No access_token or Device ID')
        login_response = client.restore_login(config['matrix_username'], config['matrix_deviceid'], config['matrix_token'])
    else:
        raise ValueError(f'Unknown login type: "{config["matrix_login_type"]}" only "password" and "access_token" are supported')

    logging.info(login_response)

    if os.path.exists('data/next_batch'):
        with open("data/next_batch", "r") as next_batch_token:
            client.next_batch = next_batch_token.read()
    else:
        await upload_avatar(client, 'avatar.png')
        await client.set_displayname(config['matrix_bot_name'])

    await client.sync_forever(30000)


if __name__ == '__main__':
    asyncio.run(main())
