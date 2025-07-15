import re

def find_trans_units(xml_bytes: bytes):
    """Ищет <trans-unit ...>...</trans-unit> во всём файле. Возвращает list Match."""
    pattern = re.compile(br'<trans-unit\b[\s\S]*?</trans-unit>')
    return [m for m in pattern.finditer(xml_bytes)]

def extract_source_word_count(trans_unit_bytes: bytes):
    """Считает слова в <source>...</source> внутри сегмента."""
    srcs = re.findall(br'<source\b[^>]*>(.*?)</source>', trans_unit_bytes, re.DOTALL)
    count = 0
    for src in srcs:
        # Примитивный подсчёт слов (по пробелам), можно заменить на сложнее
        count += len(re.findall(br'\w+', src))
    return count

def get_header_footer(xml_bytes: bytes, units):
    """Возвращает header до первого <trans-unit> и footer после последнего."""
    if not units:
        raise ValueError("Файл не содержит <trans-unit>")
    first = units[0]
    last = units[-1]
    header = xml_bytes[:first.start()]
    footer = xml_bytes[last.end():]
    return header, footer
