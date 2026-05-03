import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_release import filter_new_releases, format_jst


def リリース(タグ名, prerelease=False, draft=False):
    return {
        "tag_name": タグ名,
        "prerelease": prerelease,
        "draft": draft,
    }


def タグ一覧(リリース一覧):
    return [release["tag_name"] for release in リリース一覧]


class FilterNewReleasesTest(unittest.TestCase):
    def test_初回はlast_tagがNoneなら空リストを返す(self):
        releases = [
            リリース("v3.0.0"),
            リリース("v2.0.0"),
        ]

        self.assertEqual([], filter_new_releases(releases, None))

    def test_last_tagと一致するものより新しいリリースを返す(self):
        releases = [
            リリース("v3.0.0"),
            リリース("v2.0.0"),
            リリース("v1.0.0"),
        ]

        new_releases = filter_new_releases(releases, "v1.0.0")

        self.assertEqual(["v3.0.0", "v2.0.0"], タグ一覧(new_releases))

    def test_last_tagが範囲外の場合は最新1件のみ返す(self):
        releases = [
            リリース("v3.0.0"),
            リリース("v2.0.0"),
        ]

        new_releases = filter_new_releases(releases, "v0.9.0")

        self.assertEqual(["v3.0.0"], タグ一覧(new_releases))

    def test_prereleaseとdraftは除外される(self):
        releases = [
            リリース("v4.0.0-beta", prerelease=True),
            リリース("v3.0.0-draft", draft=True),
            リリース("v2.0.0"),
            リリース("v1.0.0"),
        ]

        new_releases = filter_new_releases(releases, "v1.0.0")

        self.assertEqual(["v2.0.0"], タグ一覧(new_releases))

    def test_last_tagと完全一致なら空リストを返す(self):
        releases = [
            リリース("v3.0.0"),
            リリース("v2.0.0"),
        ]

        self.assertEqual([], filter_new_releases(releases, "v3.0.0"))


class FormatJstTest(unittest.TestCase):
    def test_UTC_Z表記をJSTに変換する(self):
        self.assertEqual("2025-01-01 09:00 JST", format_jst("2025-01-01T00:00:00Z"))

    def test_UTC_オフセット表記でも動作する(self):
        self.assertEqual("2025-01-01 21:34 JST", format_jst("2025-01-01T12:34:56+00:00"))

    def test_日付境界をまたぐ場合(self):
        self.assertEqual("2026-01-01 01:00 JST", format_jst("2025-12-31T16:00:00Z"))


if __name__ == "__main__":
    unittest.main()
