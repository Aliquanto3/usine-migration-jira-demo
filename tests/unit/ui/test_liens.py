"""Rendu d'une clé de ticket : lien Jira, ou texte simple en Mode repli (FR-29)."""

from usine.ui.liens import echapper_markdown, lien_ticket

URL = "https://jira.example.invalid/browse/DEMO-1"


def test_lien() -> None:
    assert lien_ticket("DEMO-1", URL) == f"[DEMO-1]({URL})"


def test_mode_repli() -> None:
    assert lien_ticket("DEMO-1", None) == "DEMO-1"


def test_echappement() -> None:
    assert echapper_markdown("A]B") == r"A\]B"
    assert echapper_markdown("a|b*c_d`e$f\\g") == r"a\|b\*c\_d\`e\$f\\g"
    assert echapper_markdown("DEMO-12") == "DEMO-12"
    assert lien_ticket("A]B", None) == r"A\]B"


def test_destination_protegee() -> None:
    lien = lien_ticket("A B", "https://x.invalid/browse/A B)")
    assert lien == "[A B](https://x.invalid/browse/A%20B%29)"
