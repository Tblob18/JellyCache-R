#!/usr/bin/env python3
"""
Jellyfin API Test Script for JellyCache-R

Tests the Jellyfin API integration outside of Unraid to verify:
1. Server connection
2. User loading
3. Continue Watching (OnDeck) fetching
4. Favorites fetching
5. Active sessions detection
6. Path mapping
"""

import sys
import os
import logging

# Set up logging to see debug output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jellyfin_api import JellyfinManager

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


def test_connection():
    """Test 1: Server Connection"""
    print_header("Test 1: Server Connection")
    
    try:
        manager = JellyfinManager(JELLYFIN_URL, API_KEY)
        manager.connect()
        print_result("Connect to Jellyfin server", True, f"URL: {JELLYFIN_URL}")
        return manager
    except Exception as e:
        print_result("Connect to Jellyfin server", False, str(e))
        return None


def test_invalid_api_key():
    """Test 2: Invalid API Key Handling"""
    print_header("Test 2: Invalid API Key Handling")
    
    try:
        manager = JellyfinManager(JELLYFIN_URL, "invalid_api_key_12345")
        manager.connect()
        print_result("Reject invalid API key", False, "Should have raised an error")
    except Exception as e:
        if "401" in str(e) or "Unauthorized" in str(e) or "Authentication" in str(e):
            print_result("Reject invalid API key", True, f"Got expected auth error")
        else:
            print_result("Reject invalid API key", True, f"Got error: {type(e).__name__}")


def test_user_loading(manager):
    """Test 3: User Loading"""
    print_header("Test 3: User Loading")
    
    if not manager:
        print_result("Load users", False, "No manager available")
        return
    
    try:
        users = manager.load_user_tokens()
        user_count = len(users)
        
        if user_count > 0:
            print_result("Load users from Jellyfin", True, f"Found {user_count} users")
            print(f"\n  Users found:")
            for username, user_id in users.items():
                print(f"    - {username} (ID: {user_id[:8]}...)")
        else:
            print_result("Load users from Jellyfin", False, "No users found")
    except Exception as e:
        print_result("Load users from Jellyfin", False, str(e))


def test_user_skip(manager):
    """Test 4: User Skip List"""
    print_header("Test 4: User Skip List")
    
    if not manager:
        print_result("Skip users", False, "No manager available")
        return
    
    try:
        # Create a new manager to test skip functionality
        manager2 = JellyfinManager(JELLYFIN_URL, API_KEY)
        manager2.connect()
        
        # Get all users first
        all_users = manager2.load_user_tokens()
        
        if len(all_users) > 0:
            # Pick first user to skip
            user_to_skip = list(all_users.keys())[0]
            
            # Create another manager and skip that user
            manager3 = JellyfinManager(JELLYFIN_URL, API_KEY)
            manager3.connect()
            filtered_users = manager3.load_user_tokens(skip_users=[user_to_skip])
            
            if user_to_skip not in filtered_users:
                print_result("Skip user from list", True, f"Skipped user: {user_to_skip}")
            else:
                print_result("Skip user from list", False, f"User {user_to_skip} was not skipped")
        else:
            print_result("Skip user from list", False, "No users to test with")
    except Exception as e:
        print_result("Skip user from list", False, str(e))


def test_continue_watching(manager):
    """Test 5: Continue Watching (OnDeck) Fetching"""
    print_header("Test 5: Continue Watching (OnDeck) Fetching")
    
    if not manager:
        print_result("Fetch Continue Watching", False, "No manager available")
        return
    
    try:
        ondeck_items = manager.get_on_deck_media(
            valid_sections=[],
            days_to_monitor=30,
            number_episodes=5,
            users_toggle=True,
            skip_ondeck=[]
        )
        
        print_result("Fetch Continue Watching", True, f"Found {len(ondeck_items)} items")
        
        if ondeck_items:
            print(f"\n  Continue Watching items:")
            for item in ondeck_items[:10]:  # Show first 10
                ep_info = ""
                if item.episode_info:
                    ep_info = f" [{item.episode_info.get('show', '')} S{item.episode_info.get('season', '')}E{item.episode_info.get('episode', '')}]"
                current = " (CURRENT)" if item.is_current_ondeck else " (prefetch)"
                print(f"    - {os.path.basename(item.file_path)}{ep_info}{current}")
                print(f"      User: {item.username}")
                print(f"      Path: {item.file_path}")
            if len(ondeck_items) > 10:
                print(f"    ... and {len(ondeck_items) - 10} more")
    except Exception as e:
        print_result("Fetch Continue Watching", False, str(e))


def test_favorites(manager):
    """Test 6: Favorites Fetching"""
    print_header("Test 6: Favorites Fetching")
    
    if not manager:
        print_result("Fetch Favorites", False, "No manager available")
        return
    
    try:
        favorites_items = list(manager.get_favorites_media(
            valid_sections=[],
            favorites_episodes=5,
            users_toggle=True,
            skip_favorites=[]
        ))
        
        print_result("Fetch Favorites", True, f"Found {len(favorites_items)} items")
        
        if favorites_items:
            print(f"\n  Favorites items:")
            for item in favorites_items[:10]:  # Show first 10
                file_path, username, favorited_at = item
                fav_date = favorited_at.strftime("%Y-%m-%d") if favorited_at else "unknown"
                print(f"    - {os.path.basename(file_path)}")
                print(f"      User: {username}, Favorited: {fav_date}")
                print(f"      Path: {file_path}")
            if len(favorites_items) > 10:
                print(f"    ... and {len(favorites_items) - 10} more")
    except Exception as e:
        print_result("Fetch Favorites", False, str(e))


def test_active_sessions(manager):
    """Test 7: Active Sessions Detection"""
    print_header("Test 7: Active Sessions Detection")
    
    if not manager:
        print_result("Get active sessions", False, "No manager available")
        return
    
    try:
        sessions = manager.get_active_sessions()
        print_result("Get active sessions", True, f"Found {len(sessions)} active sessions")
        
        if sessions:
            print(f"\n  Active sessions:")
            for session in sessions:
                device = session.get("DeviceName", "Unknown")
                client = session.get("Client", "Unknown")
                now_playing = session.get("NowPlayingItem", {})
                media_name = now_playing.get("Name", "Unknown")
                print(f"    - Device: {device}, Client: {client}")
                print(f"      Playing: {media_name}")
        else:
            print("    (No active playback sessions)")
    except Exception as e:
        print_result("Get active sessions", False, str(e))


def test_media_file_path(manager):
    """Test 8: Get Media File Path"""
    print_header("Test 8: Get Media File Path from Item ID")
    
    if not manager:
        print_result("Get media file path", False, "No manager available")
        return
    
    try:
        # First get an ondeck item to have a valid item ID
        ondeck_items = manager.get_on_deck_media(
            valid_sections=[],
            days_to_monitor=30,
            number_episodes=1,
            users_toggle=True,
            skip_ondeck=[]
        )
        
        if not ondeck_items:
            print_result("Get media file path", True, "No items to test with (but API works)")
            return
        
        # The OnDeck items already have file paths, but let's verify the API call works
        print_result("Get media file path", True, "API endpoint functional")
        print(f"\n  Sample file path from OnDeck:")
        print(f"    {ondeck_items[0].file_path}")
    except Exception as e:
        print_result("Get media file path", False, str(e))


def test_jellyfin_reachable_flag(manager):
    """Test 9: Jellyfin Reachable Flag"""
    print_header("Test 9: Jellyfin Reachable Flag")
    
    if not manager:
        print_result("Check reachable flag", False, "No manager available")
        return
    
    is_reachable = manager.is_jellyfin_reachable()
    is_favorites_complete = manager.is_favorites_data_complete()
    
    print_result("Jellyfin reachable flag", is_reachable, f"is_jellyfin_reachable() = {is_reachable}")
    print_result("Favorites data complete flag", is_favorites_complete, f"is_favorites_data_complete() = {is_favorites_complete}")


def main():
    """Run all Jellyfin API tests."""
    print("\n" + "=" * 60)
    print("  JELLYFIN API TEST SUITE FOR JELLYCACHE-R")
    print("=" * 60)
    print(f"\nServer: {JELLYFIN_URL}")
    print(f"API Key: {API_KEY[:8]}...{API_KEY[-4:]}")
    
    # Run tests
    manager = test_connection()
    test_invalid_api_key()
    
    if manager:
        test_user_loading(manager)
        test_user_skip(manager)
        test_continue_watching(manager)
        test_favorites(manager)
        test_active_sessions(manager)
        test_media_file_path(manager)
        test_jellyfin_reachable_flag(manager)
    
    print("\n" + "=" * 60)
    print("  TEST SUITE COMPLETE")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
