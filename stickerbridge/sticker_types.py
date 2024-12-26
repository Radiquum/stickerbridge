class Sticker:
    """Custom type for easier transfering sticker data between functions and classes with simple lists and returns"""
    def __init__(self, image_data, alt_text: str, width: int, height: int, size: int, mimetype: str):
        self.image_data = image_data
        self.alt_text = alt_text

        self.width = width
        self.height = height
        self.mimetype = mimetype
        self.size = size


class MatrixStickerset:
    def __init__(self, pack_name: str):
        self._content = {
            "pack": {
                "display_name": pack_name
            },
            "images": {}
        }

    def add_sticker(self, mxc_uri: str, alt_text: str):
        if alt_text in self._content['images']:
            duplicate_counter = 1
            alt_text = alt_text + '-' + str(duplicate_counter)
            while (alt_text in self._content['images']):
                duplicate_counter += 1
                alt_text = alt_text.split('-')[0] + '-' + str(duplicate_counter)
                print(alt_text)
        self._content['images'][alt_text] = {
            "url": mxc_uri,
            "usage": ["sticker"]
        }

    def count(self):
        return len(self._content['images'])

    def name(self):
        return self._content['pack']['display_name']

    def json(self):
        return self._content


class MauniumStickerset:
    def __init__(self, title: str, id: str, rating: str, author: str, room_id: str):
        self.title = title
        self.id = id
        self.rating = rating
        self.author = author
        self.room_id = room_id
        self.stickers = []

    def add_sticker(self, mxc_uri: str, alt_text: str, width: int, height: int, size: int, mimetype: str):
        self.stickers.append(
            {
                "body": alt_text,
                "info": {
                    "h": height,
                    "w": width,
                    "size": size,
                    "mimetype": mimetype,
                },
                "msgtype": "m.sticker",
                "url": mxc_uri,
                "id": mxc_uri.split("/")[-1]
            }
        )

    def json(self):
        return {
            "title": self.title,
            "id": self.id,
            "rating": self.rating,
            "author": self.author,
            "room_id": self.room_id,
            "stickers": self.stickers
        }
