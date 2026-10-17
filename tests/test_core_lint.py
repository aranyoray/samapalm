from pathlib import Path

from palmppg.core.lint import scan_path, scan_text

ROOT = Path(__file__).resolve().parents[1]


def test_scan_text_finds_each_banned_term():
    text = "This was validated.\nA medical-grade device.\nDiagnostic use.\nIt generalises.\nexternal validation done."
    hits = scan_text(text)
    assert [h[0] for h in hits] == [1, 2, 3, 4, 5]


def test_scan_text_ignores_benign_words():
    assert scan_text("cross-validation fold, valid_clip, generalised linear model is not written here") == [
        (1, "generalised", "cross-validation fold, valid_clip, generalised linear model is not written here")
    ]
    assert scan_text("cross-validation fold, valid_clip, invalid, validity, general linear model") == []


def test_repository_is_clean():
    hits = scan_path(ROOT)
    assert not hits, "banned vocabulary found: " + "; ".join(f"{k}:{v[0][0]} '{v[0][1]}'" for k, v in hits.items())
