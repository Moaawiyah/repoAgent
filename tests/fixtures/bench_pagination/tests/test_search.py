from listing.search import search


def test_even_pages():
    data = [f"item {i}" for i in range(20)]
    assert search(data, "item", size=10)["pages"] == 2


def test_first_page_results():
    assert search(["a1", "a2", "b"], "a", size=1)["results"] == ["a1"]
