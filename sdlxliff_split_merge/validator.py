from .xml_utils import find_trans_units

class SdlxliffValidator:
    def validate(self, xml_bytes: bytes):
        """Минимальная валидация: есть ли сегменты и структура не порвана."""
        units = find_trans_units(xml_bytes)
        if not units:
            return False, "В файле нет сегментов <trans-unit>"
        return True, None

    def is_compatible(self, parts: list):
        """Проверяет что все части можно собрать — одинаковый header/footer."""
        headers = [p['header'] for p in parts]
        footers = [p['footer'] for p in parts]
        if not all(h == headers[0] for h in headers):
            return False, "Разные заголовки в split-файлах"
        if not all(f == footers[0] for f in footers):
            return False, "Разные хвосты в split-файлах"
        return True, None
