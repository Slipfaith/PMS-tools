import re

class Splitter:
    def __init__(self, xml_bytes: bytes):
        self.xml_bytes = xml_bytes
        # Найдём все <group ...>...</group> с их start/end позициями
        self.group_matches = list(re.finditer(br'<group\b[\s\S]*?</group>', xml_bytes))
        if not self.group_matches:
            raise ValueError("Файл не содержит <group>")

        self.fragments = self._get_raw_fragments()

    def _get_raw_fragments(self):
        """
        Разбивает файл на: [header/gap0], [group0], [gap1], [group1], ..., [gapN], [footer]
        gapN всегда соответствует реальному байтовому диапазону между группами!
        """
        frags = []
        prev_end = 0
        for m in self.group_matches:
            start, end = m.start(), m.end()
            frags.append(self.xml_bytes[prev_end:start])   # gap до этой группы (возможно, b"" если группы подряд)
            frags.append(self.xml_bytes[start:end])        # сама группа
            prev_end = end
        frags.append(self.xml_bytes[prev_end:])            # gap после последней группы (footer или пусто)
        return frags

    def split_by_parts(self, num_parts):
        """
        Делит файл строго по группам, с сохранением gap'ов byte-в-byte между ними.
        merge = b''.join(all_parts) даст полный bit-perfect original!
        """
        group_count = len(self.group_matches)
        # Число групп в каждой части
        groups_per_part = [
            group_count // num_parts + (1 if x < group_count % num_parts else 0)
            for x in range(num_parts)
        ]
        parts = []
        frag_idx = 1  # 0 — первый gap/header, 1 — первая group, 2 — gap, 3 — group, ...
        for part_size in groups_per_part:
            # Для первой части обязательно добавить header/gap0
            if frag_idx == 1:
                part = [self.fragments[0]]  # header/gap0
            else:
                part = [self.fragments[frag_idx-1]]  # gap перед текущей группой (может быть b"")
            for _ in range(part_size):
                part.append(self.fragments[frag_idx])    # group
                part.append(self.fragments[frag_idx+1])  # gap после group (может быть b"")
                frag_idx += 2
            parts.append(b"".join(part))
        return parts
