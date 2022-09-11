# Telegram -> Matrix stickerpack importer

This bot allows for simple and quick copying Telegram stickers into Matrix rooms.
Stickers can be used in clients that implemented them natively by Matrix
([msc2545](https://github.com/matrix-org/matrix-spec-proposals/pull/2545))
like [FluffyChat](https://fluffychat.im/), [Nheko](https://nheko-reborn.github.io/) and [Cinny](https://cinny.in/).
Element currently **does not** support native stickers (can only display them when send by others).

## Requirements
- Python 3.9+ and pip
- Matrix account dedicated for the bot
- Telegram API keys and bot token (**Please don't share it with anyone**)

## Instalation
- Create **new** Matrix account dedicated for the bot
- Get Telegram API key and API hash from https://my.telegram.org/apps
- Create new Telegram bot and get bot token by talking to https://t.me/botfather
- Clone this repository and install dependencies
```
git clone https://codeberg.org/ghostermonster/stickerbridge 
cd stickerbridge
pip install -r requirements.txt
```
- Copy example config file ```cp config.yaml.example config.yaml```
- Fill the config file with creditials for Matrix account and Telegram bot you created
- Run the bot ```python stickerbridge/main.py```

## Usage
Invite the bot in a room (currently does not support encrypted rooms), type ```!sb help``` to list available commands.
Type ```import <stickerpack name>``` to import stickerpack to the room, ex. ```import bestblobcats```.
After importing is completed, you will see stickerpack in the menu.
