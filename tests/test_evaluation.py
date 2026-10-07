from sentinel.tools.evaluation import binary_metrics


def test_binary_metrics():
    m = binary_metrics([(True, True), (True, True), (True, False), (False, True), (False, False), (False, False)])
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (2, 1, 1, 2)
    assert abs(m["precision"] - 2 / 3) < 1e-9 and abs(m["recall"] - 2 / 3) < 1e-9
    assert abs(m["f1"] - 2 / 3) < 1e-9 and abs(m["accuracy"] - 4 / 6) < 1e-9


def test_binary_metrics_empty_and_degenerate():
    assert binary_metrics([])["accuracy"] == 0.0
    m = binary_metrics([(False, False), (False, False)])
    assert m["precision"] == 0.0 and m["recall"] == 0.0 and m["accuracy"] == 1.0
