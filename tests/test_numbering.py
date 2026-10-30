import pytest
from src.segmentation.numbering import detect_numbering

def test_detect_numbering_cases():
    assert detect_numbering("1. Text")[0] == "1."
    assert detect_numbering("1.1 Text")[0] == "1.1"
    assert detect_numbering("(a) Text")[0] == "(a)"
    assert detect_numbering("(i) Text")[0] == "(i)"
    assert detect_numbering("Article IV.")[0] == "Article IV."
    assert detect_numbering("Section 5.2")[0] == "Section 5.2"
    assert detect_numbering("No numbering here.")[0] is None
