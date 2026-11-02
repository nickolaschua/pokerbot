import pytest
from scripts.benchmark import parse_result

LOG = "A awarded 2\nB awarded -2\nFinal, B (-2), A (2)"
CONNECTED = "A connected successfully\nB connected successfully"


def test_valid_result_and_rejected_fallbacks():
    assert parse_result(LOG, CONNECTED, "", 1) == {"A": 2, "B": -2}
    for problem in ("A attempted illegal RaiseAction", "B ran out of time", "A response misformatted: ", "A disconnected"):
        with pytest.raises(RuntimeError):
            parse_result(LOG + "\n" + problem, CONNECTED, "", 1)
    with pytest.raises(RuntimeError):
        parse_result(LOG, "", "", 1)
    with pytest.raises(RuntimeError):
        parse_result(LOG, CONNECTED, "Traceback", 1)
    with pytest.raises(RuntimeError):
        parse_result(LOG, CONNECTED, "", 2)
