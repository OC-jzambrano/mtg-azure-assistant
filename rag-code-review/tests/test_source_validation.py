import re


CITATION_RE = re.compile(r"\[S(\d+)]")


def test_only_known_source_ids_are_accepted() -> None:
    text = "Respuesta [S1] y una fuente inventada [S99]."
    used = {int(value) for value in CITATION_RE.findall(text)}
    valid = {value for value in used if 1 <= value <= 3}
    assert valid == {1}
