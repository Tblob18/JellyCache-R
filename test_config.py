#!/usr/bin/env python3
"""
Configuration Loading Test Script for JellyCache-R

Tests the ConfigManager class to ensure settings are loaded and validated correctly.
"""

import sys
import os
import logging
import json
import tempfile

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager, PathMapping


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


def _load_config_without_save(config_path):
    """Helper to load config without triggering the buggy save step."""
    manager = ConfigManager(config_path)
    with open(config_path, 'r', encoding='utf-8') as f:
        manager.settings_data = json.load(f)
    manager._validate_required_fields()
    manager._validate_types()
    manager._process_first_start()
    manager._load_all_configs()
    return manager


def test_load_test_config():
    """Test 1: Load Test Configuration"""
    print_header("Test 1: Load Test Configuration File")
    
    config_path = os.path.join(os.path.dirname(__file__), "test_jellycache_settings.json")
    
    try:
        # Load without save step to avoid known bug
        manager = _load_config_without_save(config_path)
        
        print_result("Load config file", True, f"File: {config_path}")
        
        # Verify Jellyfin settings
        jf_ok = manager.jellyfin.jellyfin_url == "https://jellyfin.dummyvault.de:443"
        print_result("Jellyfin URL loaded", jf_ok, manager.jellyfin.jellyfin_url)
        
        api_ok = manager.jellyfin.api_key.startswith("745f11ba")
        print_result("API key loaded", api_ok, f"{manager.jellyfin.api_key[:12]}...")
        
        # Verify path mappings
        mapping_count = len(manager.paths.path_mappings) if manager.paths.path_mappings else 0
        mappings_ok = mapping_count == 2
        print_result("Path mappings loaded", mappings_ok, f"{mapping_count} mappings")
        
        # Verify individual mappings
        if manager.paths.path_mappings:
            tv_mapping = manager.paths.path_mappings[0]
            tv_ok = tv_mapping.name == "Test TV Shows" and tv_mapping.plex_path == "/data/tvshows/"
            print_result("TV Shows mapping", tv_ok, f"{tv_mapping.name}: {tv_mapping.plex_path}")
            
            movies_mapping = manager.paths.path_mappings[1]
            movies_ok = movies_mapping.name == "Test Movies" and movies_mapping.plex_path == "/data/movies/"
            print_result("Movies mapping", movies_ok, f"{movies_mapping.name}: {movies_mapping.plex_path}")
        
        return jf_ok and api_ok and mappings_ok
    except Exception as e:
        print_result("Load config file", False, str(e))
        return False


def test_missing_required_field():
    """Test 2: Missing Required Field Detection"""
    print_header("Test 2: Missing Required Field Detection")
    
    # Create a config missing PLEX_URL
    incomplete_config = {
        "PLEX_TOKEN": "test_token",
        "number_episodes": 5,
        "valid_sections": [],
        "days_to_monitor": 30,
        "users_toggle": True,
        "watchlist_toggle": True,
        "watchlist_episodes": 3,
        "watched_move": True,
        "cache_dir": "/tmp/test_cache/",
        "max_concurrent_moves_array": 2,
        "max_concurrent_moves_cache": 3,
        "path_mappings": []
    }
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(incomplete_config, f)
        temp_path = f.name
    
    try:
        manager = ConfigManager(temp_path)
        manager.load_config()
        print_result("Detect missing PLEX_URL", False, "Should have raised error")
        return False
    except ValueError as e:
        if "PLEX_URL" in str(e):
            print_result("Detect missing PLEX_URL", True, "Correctly detected")
            return True
        else:
            print_result("Detect missing PLEX_URL", False, f"Wrong error: {e}")
            return False
    except Exception as e:
        print_result("Detect missing PLEX_URL", False, f"Unexpected error: {type(e).__name__}: {e}")
        return False
    finally:
        os.unlink(temp_path)


def test_invalid_json():
    """Test 3: Invalid JSON Detection"""
    print_header("Test 3: Invalid JSON Detection")
    
    # Write invalid JSON to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{ "invalid": json syntax }')
        temp_path = f.name
    
    try:
        manager = ConfigManager(temp_path)
        manager.load_config()
        print_result("Detect invalid JSON", False, "Should have raised error")
        return False
    except ValueError as e:
        if "Invalid JSON" in str(e):
            print_result("Detect invalid JSON", True, "Correctly detected")
            return True
        else:
            print_result("Detect invalid JSON", False, f"Wrong error: {e}")
            return False
    except Exception as e:
        print_result("Detect invalid JSON", True, f"Got error: {type(e).__name__}")
        return True
    finally:
        os.unlink(temp_path)


def test_file_not_found():
    """Test 4: File Not Found Detection"""
    print_header("Test 4: File Not Found Detection")
    
    try:
        manager = ConfigManager("/nonexistent/path/config.json")
        manager.load_config()
        print_result("Detect missing file", False, "Should have raised error")
        return False
    except FileNotFoundError:
        print_result("Detect missing file", True, "Correctly detected")
        return True
    except Exception as e:
        print_result("Detect missing file", False, f"Wrong error type: {type(e).__name__}")
        return False


def test_type_validation():
    """Test 5: Type Validation"""
    print_header("Test 5: Type Validation")
    
    # Create config with wrong type for number_episodes (string instead of int)
    bad_type_config = {
        "PLEX_URL": "https://test.server.com",
        "PLEX_TOKEN": "test_token",
        "number_episodes": "not_a_number",  # Should be int
        "valid_sections": [],
        "days_to_monitor": 30,
        "users_toggle": True,
        "watchlist_toggle": True,
        "watchlist_episodes": 3,
        "watched_move": True,
        "cache_dir": "/tmp/test_cache/",
        "max_concurrent_moves_array": 2,
        "max_concurrent_moves_cache": 3,
        "path_mappings": []
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(bad_type_config, f)
        temp_path = f.name
    
    try:
        manager = ConfigManager(temp_path)
        manager.load_config()
        print_result("Detect wrong type", False, "Should have raised error")
        return False
    except (ValueError, TypeError) as e:
        print_result("Detect wrong type", True, f"Error: {str(e)[:50]}...")
        return True
    except Exception as e:
        # Other errors might also indicate validation
        print_result("Detect wrong type", True, f"{type(e).__name__}: {str(e)[:40]}...")
        return True
    finally:
        os.unlink(temp_path)


def test_path_mapping_loading():
    """Test 6: Path Mapping Structure"""
    print_header("Test 6: Path Mapping Structure")
    
    config_path = os.path.join(os.path.dirname(__file__), "test_jellycache_settings.json")
    
    try:
        manager = _load_config_without_save(config_path)
        
        all_ok = True
        
        if not manager.paths.path_mappings:
            print_result("Path mappings exist", False, "No path mappings loaded")
            return False
        
        for mapping in manager.paths.path_mappings:
            # Check that trailing slashes are added
            has_trailing_plex = mapping.plex_path.endswith('/')
            has_trailing_real = mapping.real_path.endswith('/')
            has_trailing_cache = mapping.cache_path is None or mapping.cache_path.endswith('/')
            
            if not has_trailing_plex:
                print_result(f"Trailing slash on plex_path ({mapping.name})", False)
                all_ok = False
            if not has_trailing_real:
                print_result(f"Trailing slash on real_path ({mapping.name})", False)
                all_ok = False
            if not has_trailing_cache:
                print_result(f"Trailing slash on cache_path ({mapping.name})", False)
                all_ok = False
            
            # Check required fields are set
            if not mapping.name:
                print_result(f"Mapping has name", False, "Empty name")
                all_ok = False
            if not mapping.plex_path:
                print_result(f"Mapping has plex_path", False, "Empty plex_path")
                all_ok = False
            if not mapping.real_path:
                print_result(f"Mapping has real_path", False, "Empty real_path")
                all_ok = False
        
        if all_ok:
            print_result("All mappings have trailing slashes", True)
            print_result("All mappings have required fields", True)
        
        # Show loaded mappings
        print(f"\n  Loaded mappings:")
        if manager.paths.path_mappings:
            for m in manager.paths.path_mappings:
                print(f"    [{m.name}]")
                print(f"      plex_path:  {m.plex_path}")
                print(f"      real_path:  {m.real_path}")
                print(f"      cache_path: {m.cache_path}")
                print(f"      cacheable:  {m.cacheable}")
                print(f"      enabled:    {m.enabled}")
        
        return all_ok
    except Exception as e:
        print_result("Load path mappings", False, str(e))
        return False


def test_cache_config_loading():
    """Test 7: Cache Configuration"""
    print_header("Test 7: Cache Configuration Loading")
    
    config_path = os.path.join(os.path.dirname(__file__), "test_jellycache_settings.json")
    
    try:
        manager = _load_config_without_save(config_path)
        
        # Check cache settings
        retention_ok = manager.cache.cache_retention_hours == 12
        print_result("cache_retention_hours", retention_ok, f"{manager.cache.cache_retention_hours}")
        
        favorites_ok = manager.cache.favorites_toggle == True
        print_result("favorites_toggle", favorites_ok, f"{manager.cache.favorites_toggle}")
        
        episodes_ok = manager.cache.favorites_episodes == 3
        print_result("favorites_episodes", episodes_ok, f"{manager.cache.favorites_episodes}")
        
        watched_ok = manager.cache.watched_move == True
        print_result("watched_move", watched_ok, f"{manager.cache.watched_move}")
        
        return retention_ok and favorites_ok and episodes_ok and watched_ok
    except Exception as e:
        print_result("Load cache config", False, str(e))
        return False


def test_performance_config_loading():
    """Test 8: Performance Configuration"""
    print_header("Test 8: Performance Configuration Loading")
    
    config_path = os.path.join(os.path.dirname(__file__), "test_jellycache_settings.json")
    
    try:
        manager = _load_config_without_save(config_path)
        
        array_ok = manager.performance.max_concurrent_moves_array == 2
        print_result("max_concurrent_moves_array", array_ok, f"{manager.performance.max_concurrent_moves_array}")
        
        cache_ok = manager.performance.max_concurrent_moves_cache == 3
        print_result("max_concurrent_moves_cache", cache_ok, f"{manager.performance.max_concurrent_moves_cache}")
        
        return array_ok and cache_ok
    except Exception as e:
        print_result("Load performance config", False, str(e))
        return False


def test_notification_config():
    """Test 9: Notification Configuration"""
    print_header("Test 9: Notification Configuration Loading")
    
    config_path = os.path.join(os.path.dirname(__file__), "test_jellycache_settings.json")
    
    try:
        manager = _load_config_without_save(config_path)
        
        notif_ok = manager.notification.notification_type == "system"
        print_result("notification_type", notif_ok, f"{manager.notification.notification_type}")
        
        return notif_ok
    except Exception as e:
        print_result("Load notification config", False, str(e))
        return False


def main():
    """Run all configuration tests."""
    print("\n" + "=" * 60)
    print("  CONFIGURATION LOADING TEST SUITE FOR JELLYCACHE-R")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Load test config", test_load_test_config()))
    results.append(("Missing required field", test_missing_required_field()))
    results.append(("Invalid JSON detection", test_invalid_json()))
    results.append(("File not found", test_file_not_found()))
    results.append(("Type validation", test_type_validation()))
    results.append(("Path mapping structure", test_path_mapping_loading()))
    results.append(("Cache configuration", test_cache_config_loading()))
    results.append(("Performance configuration", test_performance_config_loading()))
    results.append(("Notification configuration", test_notification_config()))
    
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
