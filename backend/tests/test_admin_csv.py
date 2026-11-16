"""The door list's cells: what a spreadsheet would run as a formula isn't."""

import pytest

from admin import cell


@pytest.mark.parametrize("value", ["=SUM(A1:A9)", "+46 70", "-1", "@SUM(A1)", "\tx", "\rx"])
def test_escapes_what_a_spreadsheet_would_run(value: str):
    assert cell(value) == "'" + value


@pytest.mark.parametrize("value", ["Ada Lovelace", "ada@example.test", "", "a=b"])
def test_leaves_the_rest(value: str):
    assert cell(value) == value
