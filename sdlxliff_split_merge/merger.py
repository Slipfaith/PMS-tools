class Merger:
    """
    Bit-perfect Merger: склеивает split-файлы SDLXLIFF без изменений.
    Никакого парсинга, никакого обхода, только склейка bytes.
    """

    def __init__(self, parts_bytes: list):
        """
        parts_bytes — список файлов-частей, в нужном порядке (каждый bytes)
        """
        self.parts = parts_bytes

    def merge(self):
        """
        Склеивает все части как есть, бит-в-бит, ничего не меняет.
        """
        return b"".join(self.parts)
