import argparse
import asyncio
import os
import sys
import yaml
import shutil
import logging

from nio import AsyncClient, RoomVisibility
from telegram_exporter import TelegramExporter

class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)


parser = ArgParser()
parser.add_argument('--config', '-c', help='Path to config.yaml', default='config.yaml')
parser.add_argument('--cli-config', '-cc', help='Path to cli.yaml', default='cli.yaml')
subparsers = parser.add_subparsers(help='Available commands')

import_cmd = subparsers.add_parser('import', help='Import a Telegram stickerpack.')
import_cmd.add_argument('pack_name', type=str, help='Sticker pack url or shortname')
import_cmd.add_argument('import_name', type=str, help='Sticker pack display name', nargs='?')

import_cmd.add_argument('--primary', '-p', action='store_true', help='Upload pack as a default pack for this room')
import_cmd.add_argument('--json', '-j', action='store_true', help='create a "maunium stickerpicker" compatible json file with downloaded stickers')
import_cmd.add_argument('--artist', '-a', action='store_true', help='Ask for the artist name of the sticker pack')
import_cmd.add_argument('--artist-url', '-au', action='store_true', help='Ask for the artist page url')
import_cmd.add_argument('--rating', '-r', action='store_true', help='Ask for rating of the sticker pack')

import_cmd.add_argument('--create-room', '-cr', action='store_true', help='Create a new room for imported stickers')
import_cmd.add_argument('--space', '-s', type=str, help='Space room id to include the new room in. (You will need to invite the bot first!)')

import_cmd.epilog = 'IF boolean flags are true in "cli.yaml", and are provided here, they are applied as a False.'

async def main(args):
    os.makedirs('data', exist_ok=True)
    if not os.path.exists(args.config):
        shutil.copy('config.yaml.example', args.config)
        logging.warning('Please fill in config.yaml file, to use the cli!')
        return
    with open(args.config, 'r') as config_file:
        config = yaml.safe_load(config_file)

    if not os.path.exists(args.cli_config):
        shutil.copy('cli.yaml.example', args.cli_config)
    with open(args.cli_config, 'r') as config_file:
        cli_config = yaml.safe_load(config_file)

    logging.basicConfig(level=os.environ.get("LOGLEVEL", config['log_level']))

    client = AsyncClient(config['matrix_homeserver'], config['matrix_username'])
    client.device_id = config['matrix_bot_name']
    tg_exporter = TelegramExporter(config['telegram_api_id'], config['telegram_api_hash'], config['telegram_bot_token'],
                                   'data/telegram_secrets')
    await tg_exporter.connect()

    if config['matrix_login_type'] == 'password':
        login_response = await client.login(config['matrix_password'])
    elif config['matrix_login_type'] == 'access_token':
        client.restore_login(config['matrix_username'], config['matrix_deviceid'], config['matrix_token'])
        login_response = await client.whoami()
    else:
        raise ValueError(f'Unknown login type: "{config["matrix_login_type"]}" only "password" and "access_token" are supported')
    logging.info("Logged In: " + login_response.user_id)

    if sys.argv[1] == 'import':
        await import_stickerpack(args, client, config, cli_config)


async def import_stickerpack(args: argparse.Namespace, client: AsyncClient, config: dict, cli_config: dict):
    if args.pack_name.startswith('https://t.me/addstickers/'):
        args.pack_name = args.pack_name.split('/')[-1]

    for a in args.__dict__.keys():
        if args.__getattribute__(a) is True and isinstance(args.__getattribute__(a), bool):
            args.__setattr__(a, not cli_config['import'][a])

    room_alias = f'{cli_config['room_prefix']}{args.pack_name}'
    room = await create_or_get_room(args, client, config, cli_config, room_alias)

async def create_or_get_room(args: argparse.Namespace, client: AsyncClient, config: dict, cli_config: dict, room_alias: str):

    if not cli_config['room_homeserver']:
        raise ValueError('Please set room_homeserver in cli.yaml')
    space = args.space or cli_config['room_space']

    if space:
        if space.startswith("#"):
            if not ":" in space:
                raise ValueError(f'Invalid space: "{space}". it should be "#space:example.com"')
            try:
                space = await client.room_resolve_alias(space)
                space = space.room_id
            except:
                raise ValueError(f'Space "{space}" does not exist.')
        try:
            await client.room_get_state_event(space, 'm.room.create')
        except:
            raise ValueError(f'Space "{space}" does not exist.')

    try:
        room = await client.room_resolve_alias(f"#{room_alias}:{cli_config['room_homeserver']}")
        room = room.room_id
    except:
        room = None

    if not (args.create_room or cli_config['import']['create_room']) and not room:
        raise ValueError(f'Room "{room_alias}" does not exist. Use --create-room to create it.')

    if room:
        return room

    room_initial_state = []
    if space:
        room_initial_state = [{
            "type" : "m.space.parent",
            "state_key": space,
            "content": {
                "canonical": True,
                "via": [cli_config['room_homeserver']]
            }
        }]

    room = await client.room_create(
        visibility=RoomVisibility.public,
        alias=room_alias,
        name=args.pack_name,
        topic=f"Sticker pack: {args.pack_name}",
        initial_state=room_initial_state
    )

    if space:
        await client.room_put_state(space, "m.space.child", {
            "suggested": False,
            "via": [cli_config['room_homeserver']]
        }, room.room_id)
    logging.info(f'Created room {room.room_id}, #{room_alias}:{cli_config["room_homeserver"]}')
    return room.room_id

if __name__ == '__main__':
    args = parser.parse_args()
    if len(sys.argv)==1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    asyncio.run(main(args))
