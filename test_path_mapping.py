#!/usr/bin/env python3
"""
Path Mapping Test Script for JellyCache-R

Tests the MultiPathModifier class with actual paths from Jellyfin API.
"""

import sys
import os
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jellyfin_api import JellyfinManager
from file_operations import MultiPathModifier
from config import PathMapping

# Test configuration
JELLYFIN_URL = "http://YOUR_JELLYFIN_IP:8096"
API_KEY = "YOUR_API_KEY_HERE"


def print_header(title):
    """Print a formatted test header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(test_name, success, message=""):
    """Print test result with status indicator."""
    status = "\033[92mPASS\033[0m" if success else "\033[91mFAIL\033[0m"
    print(f"  [{status}] {test_name}")
    if message:
        print(f"         {message}")


def create_test_path_mappings():
    """Create path mappings matching test config."""
    mappings = [
        PathMapping(
            name="Test TV Shows",
            plex_path="/data/tvshows/",
            real_path="G:/repos/JellyCache-R/test_array/tvshows/",
            cache_path="G:/repos/JellyCache-R/test_cache/tvshows/",
            cacheable=True,
            enabled=True
        ),
        PathMapping(
            name="Test Movies",
            plex_path="/data/movies/",
            real_path="G:/repos/JellyCache-R/test_array/movies/",
            cache_path="G:/repos/JellyCache-R/test_cache/movies/",
            cacheable=True,
            enabled=True
        ),
    ]
    return mappings


def test_basic_path_conversion():
    """Test 1: Basic Path Conversion"""
    print_header("Test 1: Basic Path Conversion")
    
    mappings = create_test_path_mappings()
    modifier = MultiPathModifier(mappings)
    
    # Test Plex to Real conversion
    test_cases = [
        ("/data/tvshows/Supernatural/Season 1/test.mkv", 
         "G:/repos/JellyCache-R/test_array/tvshows/Supernatural/Season 1/test.mkv"),
        ("/data/movies/Harry Potter (2001)/Harry Potter.mkv",
         "G:/repos/JellyCache-R/test_array/movies/Harry Potter (2001)/Harry Potter.mkv"),
    ]
    
    all_passed = True
    for plex_path, expected_real in test_cases:
        real_path, mapping = modifier.convert_plex_to_real(plex_path)
        success = real_path == expected_real and mapping is not None
        if not success:
            all_passed = False
            print_result(f"Convert {os.path.basename(plex_path)}", False, 
                        f"Expected: {expected_real}\n           Got: {real_path}")
        else:
            print_result(f"Convert {os.path.basename(plex_path)}", True,
                        f"Used mapping: {mapping.name}")
    
    return all_passed


def test_real_to_cache_conversion():
    """Test 2: Real to Cache Path Conversion"""
    print_header("Test 2: Real to Cache Path Conversion")
    
    mappings = create_test_path_mappings()
    modifier = MultiPathModifier(mappings)
    
    test_cases = [
        ("G:/repos/JellyCache-R/test_array/tvshows/Supernatural/Season 1/test.mkv",
         "G:/repos/JellyCache-R/test_cache/tvshows/Supernatural/Season 1/test.mkv"),
        ("G:/repos/JellyCache-R/test_array/movies/Harry Potter (2001)/Harry Potter.mkv",
         "G:/repos/JellyCache-R/test_cache/movies/Harry Potter (2001)/Harry Potter.mkv"),
    ]
    
    all_passed = True
    for real_path, expected_cache in test_cases:
        cache_path, mapping = modifier.convert_real_to_cache(real_path)
        success = cache_path == expected_cache and mapping is not None
        if not success:
            all_passed = False
            print_result(f"Convert {os.path.basename(real_path)}", False,
                        f"Expected: {expected_cache}\n           Got: {cache_path}")
        else:
            print_result(f"Convert {os.path.basename(real_path)}", True,
                        f"Used mapping: {mapping.name}")
    
    return all_passed


def test_cache_to_real_conversion():
    """Test 3: Cache to Real Path Conversion"""
    print_header("Test 3: Cache to Real Path Conversion")
    
    mappings = create_test_path_mappings()
    modifier = MultiPathModifier(mappings)
    
    test_cases = [
        ("G:/repos/JellyCache-R/test_cache/tvshows/Supernatural/Season 1/test.mkv",
         "G:/repos/JellyCache-R/test_array/tvshows/Supernatural/Season 1/test.mkv"),
        ("G:/repos/JellyCache-R/test_cache/movies/Harry Potter (2001)/Harry Potter.mkv",
         "G:/repos/JellyCache-R/test_array/movies/Harry Potter (2001)/Harry Potter.mkv"),
    ]
    
    all_passed = True
    for cache_path, expected_real in test_cases:
        real_path, mapping = modifier.convert_cache_to_real(cache_path)
        success = real_path == expected_real and mapping is not None
        if not success:
            all_passed = False
            print_result(f"Convert {os.path.basename(cache_path)}", False,
                        f"Expected: {expected_real}\n           Got: {real_path}")
        else:
            print_result(f"Convert {os.path.basename(cache_path)}", True,
                        f"Used mapping: {mapping.name}")
    
    return all_passed


def test_unmapped_path():
    """Test 4: Unmapped Path Handling"""
    print_header("Test 4: Unmapped Path Handling")
    
    mappings = create_test_path_mappings()
    modifier = MultiPathModifier(mappings)
    
    # Test path that doesn't match any mapping
    unmapped = "/some/other/path/file.mkv"
    converted, mapping = modifier.convert_plex_to_real(unmapped)
    
    # Should return original path and None mapping
    success = converted == unmapped and mapping is None
    print_result("Handle unmapped path", success,
                f"Returns original path with None mapping")
    
    return success


def test_disabled_mapping():
    """Test 5: Disabled Mapping Handling"""
    print_header("Test 5: Disabled Mapping Handling")
    
    # Create mappings with one disabled
    mappings = [
        PathMapping(
            name="Enabled TV",
            plex_path="/data/tvshows/",
            real_path="G:/repos/JellyCache-R/test_array/tvshows/",
            cache_path="G:/repos/JellyCache-R/test_cache/tvshows/",
            cacheable=True,
            enabled=True
        ),
        PathMapping(
            name="Disabled Music",
            plex_path="/data/music/",
            real_path="G:/repos/JellyCache-R/test_array/music/",
            cache_path="G:/repos/JellyCache-R/test_cache/music/",
            cacheable=True,
            enabled=False  # Disabled!
        ),
    ]
    modifier = MultiPathModifier(mappings)
    
    # Try to convert a path matching the disabled mapping
    disabled_path = "/data/music/artist/album/song.mp3"
    converted, mapping = modifier.convert_plex_to_real(disabled_path)
    
    # Should return original path and None mapping (silently skipped)
    success = converted == disabled_path and mapping is None
    print_result("Skip disabled mapping", success,
                f"Disabled mapping silently skipped")
    
    return success


def test_non_cacheable_mapping():
    """Test 6: Non-Cacheable Mapping Handling"""
    print_header("Test 6: Non-Cacheable Mapping Handling")
    
    # Create mappings with one non-cacheable
    mappings = [
        PathMapping(
            name="Cacheable TV",
            plex_path="/data/tvshows/",
            real_path="G:/repos/JellyCache-R/test_array/tvshows/",
            cache_path="G:/repos/JellyCache-R/test_cache/tvshows/",
            cacheable=True,
            enabled=True
        ),
        PathMapping(
            name="Remote NAS (no cache)",
            plex_path="/nas/media/",
            real_path="//nas-server/media/",
            cache_path="",
            cacheable=False,  # Not cacheable!
            enabled=True
        ),
    ]
    modifier = MultiPathModifier(mappings)
    
    # Plex to real should still work
    nas_path = "/nas/media/movie.mkv"
    real_path, mapping = modifier.convert_plex_to_real(nas_path)
    plex_to_real_ok = real_path == "//nas-server/media/movie.mkv" and mapping is not None
    print_result("Convert non-cacheable path", plex_to_real_ok,
                f"Path: {real_path}")
    
    # Real to cache should return None (not cacheable)
    cache_path, mapping = modifier.convert_real_to_cache("//nas-server/media/movie.mkv")
    cache_none = cache_path is None
    print_result("Cache path is None for non-cacheable", cache_none,
                f"cache_path is None as expected")
    
    # is_cacheable should return False
    is_cacheable = modifier.is_cacheable("//nas-server/media/movie.mkv")
    print_result("is_cacheable returns False", not is_cacheable,
                f"is_cacheable() = {is_cacheable}")
    
    return plex_to_real_ok and cache_none and not is_cacheable


def test_modify_file_paths_batch():
    """Test 7: Batch Path Modification"""
    print_header("Test 7: Batch Path Modification (modify_file_paths)")
    
    mappings = create_test_path_mappings()
    modifier = MultiPathModifier(mappings)
    
    # List of paths like Jellyfin would return
    jellyfin_paths = [
        "/data/tvshows/Supernatural/Season 1/ep1.mkv",
        "/data/tvshows/Supernatural/Season 1/ep2.mkv",
        "/data/movies/Harry Potter (2001)/Harry Potter.mkv",
        "/data/movies/LOTR (2001)/LOTR.mkv",
    ]
    
    converted = modifier.modify_file_paths(jellyfin_paths)
    
    # All should be converted
    all_converted = all(
        not path.startswith("/data/") 
        for path in converted
    )
    print_result("Batch convert all paths", all_converted,
                f"Converted {len(converted)} paths")
    
    # Verify count matches
    count_ok = len(converted) == len(jellyfin_paths)
    print_result("Output count matches input", count_ok,
                f"{len(jellyfin_paths)} -> {len(converted)}")
    
    if all_converted:
        print("\n  Converted paths:")
        for orig, conv in zip(jellyfin_paths, converted):
            print(f"    {os.path.basename(orig)} -> {os.path.dirname(conv)}")
    
    return all_converted and count_ok


def test_with_live_jellyfin_data():
    """Test 8: Live Integration with Jellyfin API Data"""
    print_header("Test 8: Live Integration with Jellyfin API Data")
    
    try:
        # Connect to Jellyfin
        manager = JellyfinManager(JELLYFIN_URL, API_KEY)
        manager.connect()
        
        # Load users first (required for get_on_deck_media)
        users = manager.load_user_tokens()
        if not users:
            print_result("Load users", False, "No users found")
            return False
        print_result("Load users", True, f"Found {len(users)} users")
        
        # Get Continue Watching items
        ondeck_items = manager.get_on_deck_media(
            valid_sections=[],
            days_to_monitor=30,
            number_episodes=3,
            users_toggle=True,
            skip_ondeck=[]
        )
        
        if not ondeck_items:
            print_result("Get Jellyfin data", True, "No items (but API works)")
            return True
        
        # Extract file paths
        jellyfin_paths = [item.file_path for item in ondeck_items]
        print_result("Fetch from Jellyfin", True, f"Got {len(jellyfin_paths)} paths")
        
        # Create path modifier
        mappings = create_test_path_mappings()
        modifier = MultiPathModifier(mappings)
        
        # Convert all paths
        converted_paths = modifier.modify_file_paths(jellyfin_paths)
        
        # Count successful conversions
        successful = sum(1 for p in converted_paths if not p.startswith("/data/"))
        failed = len(converted_paths) - successful
        
        print_result(f"Convert Jellyfin paths", successful > 0,
                    f"{successful}/{len(converted_paths)} converted, {failed} unmapped")
        
        # Show sample conversions
        print("\n  Sample conversions:")
        for i, (orig, conv) in enumerate(zip(jellyfin_paths[:5], converted_paths[:5])):
            status = "OK" if not conv.startswith("/data/") else "UNMAPPED"
            print(f"    [{status}] {os.path.basename(orig)}")
            print(f"           From: {orig[:60]}...")
            print(f"           To:   {conv[:60]}...")
        
        if len(jellyfin_paths) > 5:
            print(f"    ... and {len(jellyfin_paths) - 5} more")
        
        return successful > 0
        
    except Exception as e:
        print_result("Live Jellyfin integration", False, str(e))
        return False


def test_get_mapping_for_path():
    """Test 9: Get Mapping for Path"""
    print_header("Test 9: Get Mapping for Path")
    
    mappings = create_test_path_mappings()
    modifier = MultiPathModifier(mappings)
    
    # Test with different path types
    test_cases = [
        ("/data/tvshows/test.mkv", "Test TV Shows"),  # plex_path
        ("G:/repos/JellyCache-R/test_array/tvshows/test.mkv", "Test TV Shows"),  # real_path
        ("G:/repos/JellyCache-R/test_cache/tvshows/test.mkv", "Test TV Shows"),  # cache_path
        ("/data/movies/test.mkv", "Test Movies"),
        ("/unknown/path/test.mkv", None),  # No mapping
    ]
    
    all_passed = True
    for path, expected_name in test_cases:
        mapping = modifier.get_mapping_for_path(path)
        actual_name = mapping.name if mapping else None
        success = actual_name == expected_name
        if not success:
            all_passed = False
        print_result(f"Find mapping for {os.path.basename(path)}", success,
                    f"Expected: {expected_name}, Got: {actual_name}")
    
    return all_passed


def main():
    """Run all path mapping tests."""
    print("\n" + "=" * 60)
    print("  PATH MAPPING TEST SUITE FOR JELLYCACHE-R")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Basic Path Conversion", test_basic_path_conversion()))
    results.append(("Real to Cache Conversion", test_real_to_cache_conversion()))
    results.append(("Cache to Real Conversion", test_cache_to_real_conversion()))
    results.append(("Unmapped Path Handling", test_unmapped_path()))
    results.append(("Disabled Mapping Handling", test_disabled_mapping()))
    results.append(("Non-Cacheable Mapping", test_non_cacheable_mapping()))
    results.append(("Batch Path Modification", test_modify_file_paths_batch()))
    results.append(("Live Jellyfin Integration", test_with_live_jellyfin_data()))
    results.append(("Get Mapping for Path", test_get_mapping_for_path()))
    
    # Summary
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    failed = len(results) - passed
    
    for name, result in results:
        status = "\033[92mPASS\033[0m" if result else "\033[91mFAIL\033[0m"
        print(f"  [{status}] {name}")
    
    print(f"\n  Total: {passed}/{len(results)} passed, {failed} failed")
    print("=" * 60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
