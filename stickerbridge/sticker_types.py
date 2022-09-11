class Sticker:
    """Custom type for easier transfering sticker data between functions and classes with simple lists and returns"""
    def __init__(self, image_data, alt_text: str, mime_type: str):
        self.image_data = image_data
        self.alt_text = alt_text
        self.mime_type = mime_type


class MatrixStickerset:
    def __init__(self, pack_name: str):
        self._content = {
            "pack": {
                "display_name": pack_name
            },
            "images": {}
        }

    def add_sticker(self, mxc_uri: str, alt_text: str):
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
