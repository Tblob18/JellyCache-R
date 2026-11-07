"""Tests for core/jellyfin_api.py using a fake Jellyfin HTTP layer."""

from datetime import datetime, timedelta, timezone

import pytest

from core.jellyfin_api import JellyfinManager, _parse_jellyfin_date


def _iso(days_ago: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.1234567Z")


def _ep(id_, series, season, ep, path, played=False, minutes=45, last_played=None):
    return {
        "Id": id_, "Type": "Episode", "SeriesId": f"s-{series}", "SeriesName": series,
        "ParentIndexNumber": season, "IndexNumber": ep, "Path": path,
        "RunTimeTicks": minutes * 60 * 10_000_000,
        "UserData": {"Played": played, "LastPlayedDate": last_played},
    }


SHOW = [_ep(f"e{i}", "Show", 1, i, f"/media/tv/Show/S01E0{i}.mkv", played=i < 3) for i in range(1, 8)]
MOVIE = {"Id": "m1", "Type": "Movie", "Name": "Film", "Path": "/media/movies/Film.mkv",
         "UserData": {"Played": False, "LastPlayedDate": _iso(1)}}
OLD_MOVIE = {"Id": "m2", "Type": "Movie", "Name": "Old", "Path": "/media/movies/Old.mkv",
             "UserData": {"Played": False, "LastPlayedDate": _iso(60)}}
OTHER_LIB = {"Id": "m3", "Type": "Movie", "Name": "Home video", "Path": "/media/home/clip.mkv",
             "UserData": {"Played": False, "LastPlayedDate": _iso(1)}}


class FakeJellyfin(JellyfinManager):
    """JellyfinManager with _get routed to canned responses."""

    def __init__(self, routes, **kwargs):
        super().__init__("http://jf:8096", "key", **kwargs)
        self.routes = routes
        self.calls = []

    def _get(self, endpoint, params=None):
        self.calls.append((endpoint, params or {}))
        handler = self.routes[endpoint]
        return handler(params or {}) if callable(handler) else handler


def _episodes_from(params):
    start = params.get("StartItemId")
    items = SHOW
    if start:
        idx = next(i for i, e in enumerate(SHOW) if e["Id"] == start)
        items = SHOW[idx:]
    return {"Items": items}


@pytest.fixture
def routes():
    return {
        "/System/Info": {"ServerName": "jf", "Version": "10.10.3"},
        "/Library/VirtualFolders": [
            {"Name": "Movies", "ItemId": "lib-movies", "CollectionType": "movies", "Locations": ["/media/movies"]},
            {"Name": "TV", "ItemId": "lib-tv", "CollectionType": "tvshows", "Locations": ["/media/tv/"]},
            {"Name": "Home", "ItemId": "lib-home", "CollectionType": "homevideos", "Locations": ["/media/home"]},
        ],
        "/Users": [
            {"Name": "admin", "Id": "u1", "Policy": {"IsAdministrator": True}},
            {"Name": "kid", "Id": "u2", "Policy": {}},
            {"Name": "gone", "Id": "u3", "Policy": {"IsDisabled": True}},
        ],
        "/Users/u1/Items/Resume": {"Items": [MOVIE, OLD_MOVIE, OTHER_LIB, SHOW[2]]},
        "/Users/u2/Items/Resume": {"Items": []},
        "/Shows/NextUp": lambda p: {"Items": [SHOW[2]] if p["UserId"] == "u1" else []},
        "/Shows/s-Show/Episodes": _episodes_from,
        "/Users/u1/Items": {"Items": [
            {"Id": "s-Show", "Type": "Series", "Name": "Show"},
            {"Id": "m9", "Type": "Movie", "Path": "/media/movies/Fav.mkv", "UserData": {"Played": False}},
            {"Id": "m8", "Type": "Movie", "Path": "/media/movies/Seen.mkv", "UserData": {"Played": True}},
        ]},
        "/Users/u2/Items": {"Items": []},
        "/Sessions": [
            {"UserId": "u1", "NowPlayingItem": {"Id": "m1", "Path": "/media/movies/Film.mkv"}},
            {"UserId": "u2", "NowPlayingItem": {"Id": "e4"}},
            {"UserId": "u2"},
        ],
        "/Users/u2/Items/e4": SHOW[3],
    }


@pytest.fixture
def jf(routes):
    m = FakeJellyfin(routes, settings_users=[{"title": "admin"}])
    m.connect()
    m.load_user_tokens()
    return m


def test_parse_date_handles_seven_fraction_digits():
    dt = _parse_jellyfin_date("2026-11-01T20:15:03.1234567Z")
    assert dt == datetime(2026, 11, 1, 20, 15, 3, 123456, tzinfo=timezone.utc)
    assert _parse_jellyfin_date(None) is None
    assert _parse_jellyfin_date("garbage") is None


def test_users_skip_disabled_and_report_new(jf):
    assert jf.load_user_tokens() == {"admin": "u1", "kid": "u2"}
    assert [u["title"] for u in jf.get_newly_discovered_users()] == ["kid"]


def test_on_deck_resume_nextup_and_prefetch(jf):
    items = jf.get_on_deck_media([], days_to_monitor=7, number_episodes=2,
                                 users_toggle=True, skip_ondeck=[])
    paths = {i.file_path: i for i in items}
    assert "/media/movies/Film.mkv" in paths
    assert "/media/movies/Old.mkv" not in paths  # older than days_to_monitor
    # current episode + next two, de-duplicated across Resume and NextUp
    assert paths["/media/tv/Show/S01E03.mkv"].is_current_ondeck
    assert not paths["/media/tv/Show/S01E04.mkv"].is_current_ondeck
    assert "/media/tv/Show/S01E05.mkv" in paths
    assert "/media/tv/Show/S01E06.mkv" not in paths
    assert paths["/media/tv/Show/S01E04.mkv"].episode_info == {"show": "Show", "season": 1, "episode": 4}
    assert paths["/media/tv/Show/S01E04.mkv"].rating_key == "e4"
    assert len(items) == len(paths)
    assert jf.is_ondeck_data_complete()


def test_on_deck_prefetch_minimum_minutes_extends(jf):
    items = jf.get_on_deck_media([], 7, 1, True, [], prefetch_minimum_minutes=150)
    eps = sorted(i.file_path for i in items if "Show" in i.file_path)
    # 45 (current) + 45*3 >= 150 -> E04..E06 prefetched
    assert eps == [f"/media/tv/Show/S01E0{i}.mkv" for i in (3, 4, 5, 6)]


def test_on_deck_library_filter_by_name_or_id(jf):
    items = jf.get_on_deck_media(["Movies", "lib-tv"], 7, 0, True, [])
    paths = {i.file_path for i in items}
    assert "/media/home/clip.mkv" not in paths
    assert "/media/movies/Film.mkv" in paths


def test_on_deck_skip_users_and_single_user_mode(jf):
    jf.get_on_deck_media([], 7, 0, True, ["admin"])
    assert not any(c[0] == "/Users/u1/Items/Resume" for c in jf.calls)
    jf.calls.clear()
    jf.get_on_deck_media([], 7, 0, False, [])
    resume_calls = [c[0] for c in jf.calls if c[0].endswith("/Resume")]
    assert resume_calls == ["/Users/u1/Items/Resume"]


def test_on_deck_user_failure_marks_incomplete(jf, routes):
    def boom(_):
        raise ConnectionError("down")
    routes["/Users/u2/Items/Resume"] = boom
    jf.get_on_deck_media([], 7, 0, True, [])
    assert not jf.is_ondeck_data_complete()


def test_watchlist_favorites(jf):
    items = list(jf.get_watchlist_media([], 2, True, []))
    paths = [i[0] for i in items]
    # unwatched episodes of favorited series: E03, E04 (E01/E02 played)
    assert paths[:2] == ["/media/tv/Show/S01E03.mkv", "/media/tv/Show/S01E04.mkv"]
    assert "/media/movies/Fav.mkv" in paths
    assert "/media/movies/Seen.mkv" not in paths
    fav = next(i for i in items if i[0] == "/media/movies/Fav.mkv")
    assert fav == ("/media/movies/Fav.mkv", "admin", None, None, "m9", "movie")
    assert items[0][5] == "episode"


def test_watchlist_rss_is_ignored(jf):
    assert list(jf.get_watchlist_media([], 2, False, [], rss_url="http://x")) == []


def test_sessions(jf):
    sessions = jf.get_active_sessions()
    assert len(sessions) == 2
    assert [jf.get_session_media_path(s) for s in sessions] == [
        "/media/movies/Film.mkv", "/media/tv/Show/S01E04.mkv"]


def test_connect_failure_raises(routes):
    def boom(_):
        raise ConnectionError("refused")
    routes["/System/Info"] = boom
    with pytest.raises(ConnectionError):
        FakeJellyfin(routes).connect()
