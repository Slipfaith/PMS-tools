from pathlib import Path
from controller import MainController

def test_set_get_file_languages():
    c = MainController()
    fake = Path('a.sdltm')
    c.files.append(fake)
    c.set_file_languages(fake, 'en-US', 'de-DE')
    langs = c.get_file_languages(fake)
    assert langs == {'source': 'en-US', 'target': 'de-DE'}
