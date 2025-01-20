import argparse
import asyncio
import os
import sys
import yaml
import shutil
import logging

from nio import AsyncClient, RoomVisibility
from matrix_reuploader import MatrixReuploader
from telegram_exporter import TelegramExporter

class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)

class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


parser = ArgParser()
parser.add_argument('--config', '-c', help='Path to config.yaml', default='config.yaml')
parser.add_argument('--cli-config', '-cc', help='Path to cli.yaml', default='cli.yaml')
subparsers = parser.add_subparsers(help='Available commands')

import_cmd = subparsers.add_parser('import', help='Import a Telegram stickerpack.')
import_cmd.add_argument('pack_name', type=str, help='Sticker pack url or shortname')
import_cmd.add_argument('import_name', type=str, help='Sticker pack display name', nargs='?')

import_cmd.add_argument('--primary', '-p', action='store_true', help='Upload pack as a default pack for this room')
import_cmd.add_argument('--json', '-j', action='store_true', help='Create a "maunium stickerpicker" compatible json file with downloaded stickers')
import_cmd.add_argument('--artist', '-a', type=str, help='Artist name of the sticker pack', nargs="?", default='False')
import_cmd.add_argument('--artist-url', '-au', type=str, help='Artist page url', nargs="?", default='False')
import_cmd.add_argument('--rating', '-r', choices=('S', 'Q', 'E', 'U'), help='Set the rating of the sticker pack. Safe/Questionable/Explicit/Unrated ', default='U')
import_cmd.add_argument('--room', '-rm', type=str, help='Set a room for the sticker upload')
import_cmd.add_argument('--create-room', '-cr', action='store_true', help='Create a new room for imported stickers')
import_cmd.add_argument('--space', '-s', type=str, help='Space to include the new room in. (You will need to invite the bot first!)')
import_cmd.add_argument('--update-pack', '-upd', action='store_true', help='Update pack if it already exists')

import_cmd.epilog = 'IF boolean flags are true in "config.yaml" or "cli.yaml", and are provided here, they are applied as a False.'

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

    fmt = f"%(asctime)-20s | %(filename)-20s | %(levelname)s : %(message)s"
    logging.basicConfig(level=os.environ.get("LOGLEVEL", config['log_level']), format=fmt, handlers=[logging.StreamHandler()])

    client = AsyncClient(config['matrix_homeserver'], config['matrix_username'])
    client.device_id = config['matrix_bot_name']

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

    await client.close()

async def import_stickerpack(args: argparse.Namespace, client: AsyncClient, config: dict, cli_config: dict):
    if args.pack_name.startswith('https://t.me/addstickers/'):
        args.__setattr__("pack_name", args.pack_name.split('/')[-1])

    if args.import_name is None:
        args.__setattr__("import_name", args.pack_name)

    for a in args.__dict__.keys():
        if args.__getattribute__(a) is True and isinstance(args.__getattribute__(a), bool) and a not in ['primary', 'json', 'update_pack']:
            args.__setattr__(a, not cli_config['import'][a])

    __exporter_args = []
    if args.primary:
        __exporter_args.append('-p')
    if args.json:
        __exporter_args.append('-j')
    if args.update_pack:
        __exporter_args.append('-upd')
    if args.rating:
        __exporter_args.append('-r')
        __exporter_args.append(args.rating)
    if args.artist != 'False' or cli_config['import']['artist']:
        if args.artist is None or args.artist == 'False':
            artistName = input('Artist name: ')
        else:
            artistName = args.artist
        __exporter_args.append('-a')
        __exporter_args.append(artistName)
    if args.artist_url != 'False' or cli_config['import']['artist_url']:
        if args.artist_url is None or args.artist_url == 'False':
            artistUrl = input('Artist url: ')
        else:
            artistUrl = args.artist_url
        __exporter_args.append('-au')
        __exporter_args.append(artistUrl)

    room = await create_or_get_room(args, client, config, cli_config)

    tg_exporter = TelegramExporter(config['telegram_api_id'], config['telegram_api_hash'], config['telegram_bot_token'],
                            'data/telegram_secrets')
    await tg_exporter.connect()

    reuploader = MatrixReuploader(client, AttrDict({'room_id': room}), exporter=tg_exporter)
    async for status in reuploader.import_stickerset_to_room(
            args.pack_name, args.import_name, __exporter_args
        ):
            switch = {
                MatrixReuploader.STATUS_DOWNLOADING: f"Downloading stickerpack {args.pack_name}...",
                MatrixReuploader.STATUS_UPLOADING: f"Uploading stickerpack {args.pack_name}...",
                MatrixReuploader.STATUS_UPDATING_ROOM_STATE: f"Updating room state...",
                MatrixReuploader.STATUS_OK: "Done",
                MatrixReuploader.STATUS_NO_PERMISSION: (
                    "I do not have permissions to create any stickerpack in this room\n"
                    "Please, give me mod 🙏"
                ),
                MatrixReuploader.STATUS_PACK_EXISTS: (
                    f"Stickerpack '{args.pack_name}' already exists.\n"
                    "Please delete it first."
                ),
                MatrixReuploader.STATUS_PACK_UPDATE: (
                    f"Updating Stickerpack '{args.pack_name}'.\n"
                ),
                MatrixReuploader.STATUS_PACK_EMPTY: (
                    f"Warning: Telegram pack {args.pack_name} find out empty or not existing."
                ),
            }
            text = switch.get(status, "Warning: Unknown status")
            logging.info(text)

    await tg_exporter.close()

async def create_or_get_room(args: argparse.Namespace, client: AsyncClient, config: dict, cli_config: dict):

    if not cli_config['room']['homeserver']:
        raise ValueError('Please set room homeserver in cli.yaml')

    room_alias = f'{cli_config['room']['prefix']}{args.pack_name}'
    if args.room:
        room_alias = args.room

    if room_alias.startswith("#"):
            if not ":" in room_alias:
                raise ValueError(f'Invalid room: "{room_alias}". it should be "#room:example.com"')
            try:
                room = await client.room_resolve_alias(room_alias)
                room = room.room_id
            except:
                room = None
    elif room_alias.startswith("!"):
        room = room_alias
        try:
            await client.room_get_state_event(room, 'm.room.create')
        except:
            room = None
    else:
        try:
            room = await client.room_resolve_alias(f"#{room_alias}:{cli_config['room']['homeserver']}")
            room = room.room_id
        except:
            room = None

    if not (args.create_room or cli_config['import']['create_room']) and not room:
        raise ValueError(f'Room "{room_alias}" does not exist. Use --create-room to create it.')

    if room:
        return room

    space = args.space or cli_config['room']['space']
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

    room_initial_state = []
    if space:
        room_initial_state = [{
            "type" : "m.space.parent",
            "state_key": space,
            "content": {
                "canonical": True,
                "via": [cli_config['room']['homeserver']]
            }
        }]

    try:
        room = await client.room_create(
            visibility=RoomVisibility.public,
            alias=room_alias,
            name=args.pack_name,
            topic=f"Sticker pack: {args.pack_name}",
            initial_state=room_initial_state,
        )
    except:
        raise ValueError(f'Failed to create room "{room_alias}: {room}"')

    RoomPowerLevels = {
        "users": {
                config["matrix_username"]: 100
            },
        "users_default": 0,
        "events": {
                "m.room.name": 50,
                "m.room.power_levels": 100,
                "m.room.history_visibility": 100,
                "m.room.canonical_alias": 50,
                "m.room.avatar": 50,
                "m.room.tombstone": 100,
                "m.room.server_acl": 100,
                "m.room.encryption": 100,
                "m.space.child": 50,
                "m.room.topic": 50,
                "m.room.pinned_events": 50,
                "m.reaction": 0,
                "m.room.redaction": 50,
                "org.matrix.msc3401.call": 50,
                "org.matrix.msc3401.call.member": 50,
                "im.vector.modular.widgets": 50
            },
        "events_default": 50,
        "state_default": 50,
        "ban": 50,
        "kick": 50,
        "redact": 50,
        "invite": 0,
        "historical": 100,
        "m.call.invite": 50
    }

    if cli_config['room'].get('autoinvite', False):
        for user in cli_config['room']['autoinvite']:
            await client.room_invite(room.room_id, user['user'])
            if user['power'] > 100:
                user['power'] = 100
            RoomPowerLevels['users'][user['user']] = user['power']
    await client.room_put_state(room.room_id, "m.room.power_levels", RoomPowerLevels)
    await client.room_put_state(room.room_id, "m.room.guest_access", {"guest_access": "can_join"})

    if space:
        await client.room_put_state(space, "m.space.child", {
            "suggested": False,
            "via": [cli_config['room']['homeserver']]
        }, room.room_id)
    logging.info(f'Created room {room.room_id}, #{room_alias}:{cli_config["room"]["homeserver"]}')
    return room.room_id

if __name__ == '__main__':
    args = parser.parse_args()
    if len(sys.argv)==1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    asyncio.run(main(args))
