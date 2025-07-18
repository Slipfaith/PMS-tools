import re
from sdlxliff_split_merge import StructuralSplitter, merge_with_original

SAMPLE_ORIG = """
<xliff xmlns='urn:oasis:names:tc:xliff:document:1.2'><file><header></header><body>
<trans-unit id="1"><source>one two three</source><target/></trans-unit>
<trans-unit id="2"><source>four five six seven</source><target/></trans-unit>
<trans-unit id="3"><source>eight nine</source><target/></trans-unit>
<trans-unit id="4"><source>ten</source><target/></trans-unit>
</body></file></xliff>
"""


def test_split_by_words():
    splitter = StructuralSplitter(SAMPLE_ORIG)
    parts = splitter.split_by_words(2)
    assert len(parts) == 2
    # first part should contain first two segments
    assert re.search(r'id="1"', parts[0])
    assert re.search(r'id="2"', parts[0])


def test_merge_with_original():
    parts = [
        "<xliff><file><body>"
        "<trans-unit id='1'><source>one two three</source><target>uno</target></trans-unit>"
        "<trans-unit id='2'><source>four five six seven</source><target>dos</target></trans-unit>"
        "</body></file></xliff>",
        "<xliff><file><body>"
        "<trans-unit id='3'><source>eight nine</source><target>tres</target></trans-unit>"
        "<trans-unit id='4'><source>ten</source><target>cuatro</target></trans-unit>"
        "</body></file></xliff>",
    ]
    merged = merge_with_original(SAMPLE_ORIG, parts)
    assert "<target>uno</target>" in merged
    assert "<target>dos</target>" in merged
    assert "<target>tres</target>" in merged
    assert "<target>cuatro</target>" in merged
