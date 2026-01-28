# JellyCache-R Testing Guide

## Table of Contents
1. [Overview](#overview)
2. [Test Environment Setup](#test-environment-setup)
3. [Test Categories](#test-categories)
4. [Unit Testing](#unit-testing)
5. [Integration Testing](#integration-testing)
6. [Manual Testing Procedures](#manual-testing-procedures)
7. [Performance Testing](#performance-testing)
8. [Security Testing](#security-testing)
9. [Regression Testing](#regression-testing)
10. [Test Data Requirements](#test-data-requirements)
11. [CI/CD Integration](#cicd-integration)
12. [Known Issues and Edge Cases](#known-issues-and-edge-cases)
13. [Test Reporting](#test-reporting)

---

## Overview

This document provides comprehensive testing guidelines for JellyCache-R, a Jellyfin media management automation tool. The application manages media caching by moving files between array storage and cache storage based on Jellyfin user activity.

### Core Functionality to Test
- Jellyfin API integration
- File operations (move, copy, delete)
- Path mapping and conversions
- Cache management and retention policies
- Configuration management
- Logging and notifications
- Concurrent file operations
- System detection and compatibility

### Testing Goals
- Verify all features work as documented
- Ensure data integrity during file operations
- Validate configuration handling
- Confirm system compatibility
- Prevent data loss scenarios
- Validate security measures

---

## Test Environment Setup

### Prerequisites
- Python 3.8 or higher
- Jellyfin server (local or remote)
- Test media files (various formats)
- Sufficient storage for array and cache directories

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Tblob18/JellyCache-R.git
   cd JellyCache-R
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install test dependencies:**
   ```bash
   pip install pytest pytest-cov pytest-mock responses
   ```

### Test Configuration

Create a test configuration file `test_jellycache_settings.json`:

```json
{
  "jellyfin_url": "http://localhost:8096",
  "api_key": "test_api_key_here",
  "valid_sections": [],
  "number_episodes": 5,
  "days_to_monitor": 30,
  "users_toggle": true,
  "skip_ondeck": [],
  "skip_favorites": [],
  "favorites_toggle": true,
  "favorites_episodes": 3,
  "watched_move": true,
  "cache_retention_hours": 12,
  "favorites_retention_days": 0,
  "cache_limit": "",
  "cache_dir": "/tmp/test_cache/",
  "path_mappings": [
    {
      "name": "Test TV Shows",
      "plex_path": "/data/tv/",
      "real_path": "/tmp/test_array/tv/",
      "cache_path": "/tmp/test_cache/tv/",
      "cacheable": true,
      "enabled": true,
      "_comment": "plex_path is kept for compatibility with PlexCache-R; it represents the path as seen by Jellyfin"
    },
    {
      "name": "Test Movies",
      "plex_path": "/data/movies/",
      "real_path": "/tmp/test_array/movies/",
      "cache_path": "/tmp/test_cache/movies/",
      "cacheable": true,
      "enabled": true
    }
  ],
  "max_concurrent_moves_array": 2,
  "max_concurrent_moves_cache": 3,
  "notification_type": "system"
}
```

### Test Directory Structure

Create test directories:
```bash
mkdir -p /tmp/test_array/{tv,movies}
mkdir -p /tmp/test_cache/{tv,movies}
mkdir -p /tmp/test_logs
```

---

## Test Categories

### 1. Functional Testing
- Feature completeness
- Input/output validation
- Error handling

### 2. Integration Testing
- API communication
- Module interactions
- External system dependencies

### 3. Performance Testing
- File transfer speeds
- Concurrent operations
- Memory usage
- API rate limiting

### 4. Security Testing
- API key validation
- File permission checks
- Path traversal prevention
- Configuration validation

### 5. Compatibility Testing
- Linux distributions
- Unraid specific features
- Docker environments
- Various Jellyfin versions

---

## Unit Testing

### Module: `config.py`

**Test Cases:**

1. **Configuration Loading**
   ```python
   def test_load_valid_config():
       """Test loading a valid configuration file."""
       # Create valid config file
       # Initialize ConfigManager
       # Call load_config()
       # Assert all values loaded correctly
   
   def test_load_missing_config():
       """Test handling of missing configuration file."""
       # Attempt to load non-existent file
       # Assert FileNotFoundError is raised
   
   def test_load_invalid_json():
       """Test handling of malformed JSON."""
       # Create file with invalid JSON
       # Assert appropriate error is raised
   ```

2. **Path Mapping Validation**
   ```python
   def test_path_mapping_validation():
       """Test path mapping configuration validation."""
       # Test various path mapping scenarios
       # Verify enabled/disabled states
       # Check cacheable flag handling
   
   def test_multi_path_support():
       """Test multiple path mappings."""
       # Create config with multiple mappings
       # Verify all mappings are processed
       # Check path resolution logic
   ```

3. **Configuration Defaults**
   ```python
   def test_default_values():
       """Test that default values are applied correctly."""
       # Load minimal config
       # Verify defaults are applied where needed
   
   def test_config_migration():
       """Test migration from old config format."""
       # Load old format config
       # Verify conversion to new format
   ```

### Module: `jellyfin_api.py`

**Test Cases:**

1. **API Connection**
   ```python
   def test_connect_valid_credentials():
       """Test connection with valid API credentials."""
       # Mock Jellyfin API response
       # Create JellyfinManager
       # Call connect()
       # Assert connection successful
   
   def test_connect_invalid_credentials():
       """Test handling of invalid API key."""
       # Mock 401 response
       # Attempt connection
       # Assert appropriate error handling
   
   def test_connect_server_unreachable():
       """Test handling of unreachable server."""
       # Mock connection timeout
       # Verify graceful error handling
   ```

2. **Media Fetching**
   ```python
   def test_fetch_continue_watching():
       """Test fetching Continue Watching items."""
       # Mock Jellyfin API response
       # Call fetch method
       # Verify items are parsed correctly
   
   def test_fetch_favorites():
       """Test fetching Favorites items."""
       # Mock API response with favorites
       # Verify correct item extraction
   
   def test_fetch_watched_media():
       """Test fetching watched media."""
       # Mock watched items
       # Verify correct filtering
   ```

3. **Rate Limiting**
   ```python
   def test_api_rate_limiting():
       """Test API rate limiting behavior."""
       # Make rapid API calls
       # Verify delays are applied
       # Check no rate limit errors occur
   ```

### Module: `file_operations.py`

**Test Cases:**

1. **File Moving**
   ```python
   def test_move_file_success():
       """Test successful file move operation."""
       # Create test file
       # Call move function
       # Verify file exists at destination
       # Verify source removed
   
   def test_move_file_insufficient_space():
       """Test handling of insufficient disk space."""
       # Mock disk space check
       # Attempt move with insufficient space
       # Verify operation is aborted
   
   def test_move_file_already_exists():
       """Test handling of existing destination file."""
       # Create file at destination
       # Attempt move
       # Verify conflict handling
   ```

2. **Subtitle Handling**
   ```python
   def test_find_subtitles():
       """Test subtitle discovery."""
       # Create media file with subtitles
       # Call subtitle finder
       # Verify all subtitle formats found
   
   def test_move_with_subtitles():
       """Test moving media with subtitles."""
       # Create media with multiple subtitle files
       # Move media
       # Verify all subtitles moved
   ```

3. **Concurrent Operations**
   ```python
   def test_concurrent_moves():
       """Test concurrent file moving."""
       # Create multiple files
       # Initiate concurrent moves
       # Verify all complete successfully
       # Check thread safety
   ```

### Module: `system_utils.py`

**Test Cases:**

1. **System Detection**
   ```python
   def test_detect_linux():
       """Test Linux system detection."""
       # Mock platform detection
       # Verify correct OS identified
   
   def test_detect_unraid():
       """Test Unraid detection."""
       # Mock Unraid indicators
       # Verify Unraid-specific features enabled
   ```

2. **Path Conversion**
   ```python
   def test_path_conversion():
       """Test path format conversions."""
       # Test various path formats
       # Verify correct conversions
   
   def test_windows_path_handling():
       """Test handling of Windows paths."""
       # If running on Windows
       # Verify path normalization
   ```

3. **File Utilities**
   ```python
   def test_disk_space_calculation():
       """Test free space calculation."""
       # Mock disk space info
       # Verify accurate calculations
   
   def test_file_size_calculation():
       """Test file size retrieval."""
       # Create files of known sizes
       # Verify size calculations
   ```

### Module: `logging_config.py`

**Test Cases:**

1. **Log File Creation**
   ```python
   def test_create_log_file():
       """Test log file initialization."""
       # Initialize logging
       # Verify log file created
       # Check file permissions
   
   def test_log_rotation():
       """Test log file rotation."""
       # Generate logs beyond rotation size
       # Verify rotation occurs
       # Check old logs are backed up
   ```

2. **Notification Handlers**
   ```python
   def test_unraid_notifications():
       """Test Unraid notification system."""
       # Configure Unraid notifications
       # Trigger notification
       # Verify notification sent
   
   def test_webhook_notifications():
       """Test webhook notifications."""
       # Mock webhook endpoint
       # Trigger notification
       # Verify webhook called with correct data
   ```

### Module: `plexcache_app.py`

**Test Cases:**

1. **Application Initialization**
   ```python
   def test_app_initialization():
       """Test application startup."""
       # Initialize app with valid config
       # Verify all components initialized
   
   def test_app_dry_run_mode():
       """Test dry-run mode."""
       # Start app in dry-run mode
       # Verify no files are moved
       # Check logging indicates dry-run
   ```

2. **Main Workflow**
   ```python
   def test_full_workflow():
       """Test complete application workflow."""
       # Set up test environment
       # Run full workflow
       # Verify all steps executed
       # Check final state
   ```

3. **Error Recovery**
   ```python
   def test_error_handling():
       """Test graceful error handling."""
       # Inject various errors
       # Verify app doesn't crash
       # Check error logging
   ```

---

## Integration Testing

### Test Scenario 1: End-to-End Cache Operation

**Objective:** Verify complete workflow from fetching media to caching

**Steps:**
1. Configure Jellyfin with test media
2. Add media to Continue Watching
3. Run JellyCache
4. Verify media moved to cache
5. Mark media as watched
6. Run JellyCache again
7. Verify media moved back to array

**Expected Results:**
- Files successfully moved to cache
- Subtitles moved with media
- .plexcached markers created
- Watched media returned to array
- All operations logged correctly

### Test Scenario 2: Multi-User Support

**Objective:** Verify handling of multiple Jellyfin users

**Steps:**
1. Create multiple test users
2. Each user adds different media to Continue Watching
3. Configure skip lists for some users
4. Run JellyCache
5. Verify correct media fetched per user
6. Verify skipped users are ignored

**Expected Results:**
- Only enabled users' media is cached
- Skip lists honored
- No conflicts between users
- Proper logging of user operations

### Test Scenario 3: Cache Retention Policy

**Objective:** Test cache cleanup based on retention policies

**Steps:**
1. Move media to cache
2. Wait for retention period to expire
3. Run JellyCache
4. Verify expired cache items removed
5. Verify priority items retained longer

**Expected Results:**
- Old cache items cleaned up
- Retention policies enforced
- Priority items preserved
- Logs show cleanup actions

### Test Scenario 4: Path Mapping Scenarios

**Objective:** Test various path mapping configurations

**Steps:**
1. Configure multiple path mappings
2. Include cacheable and non-cacheable paths
3. Disable some mappings
4. Run JellyCache
5. Verify only enabled/cacheable paths processed

**Expected Results:**
- Only enabled mappings used
- Non-cacheable paths skipped
- Correct path conversions applied
- No errors with disabled mappings

### Test Scenario 5: Concurrent File Operations

**Objective:** Test parallel file moving

**Steps:**
1. Queue multiple large files for caching
2. Run JellyCache with concurrent moves enabled
3. Monitor system resources
4. Verify all files moved correctly

**Expected Results:**
- Multiple files moved simultaneously
- No file corruption
- Proper concurrency limits respected
- Thread-safe operations

### Test Scenario 6: Active Session Handling

**Objective:** Verify behavior during active playback

**Steps:**
1. Start playing media in Jellyfin
2. Run JellyCache
3. Verify currently playing file is skipped
4. Verify other files are still processed

**Expected Results:**
- Active files not moved
- Application doesn't exit (or exits based on config)
- Proper logging of active sessions
- Other operations continue

### Test Scenario 7: Insufficient Disk Space

**Objective:** Test handling of low disk space

**Steps:**
1. Configure small cache directory
2. Attempt to cache large files
3. Fill cache to near capacity
4. Attempt additional caching

**Expected Results:**
- Operations abort when space insufficient
- No partial moves
- Clear error messages
- Proper cleanup of failed operations

### Test Scenario 8: Network Failures

**Objective:** Test resilience to network issues

**Steps:**
1. Start JellyCache operation
2. Simulate network interruption to Jellyfin
3. Verify error handling
4. Restore network
5. Verify recovery

**Expected Results:**
- Graceful degradation
- Retry mechanisms work
- No data corruption
- Clear error logging

---

## Manual Testing Procedures

### Pre-Flight Checklist

Before each test run:

- [ ] Backup test data
- [ ] Verify Jellyfin server is running
- [ ] Check available disk space
- [ ] Review current configuration
- [ ] Clear previous logs (optional)
- [ ] Verify no other instances running

### Test Procedure 1: First-Time Setup

**Purpose:** Validate new installation

1. **Install JellyCache-R**
   ```bash
   git clone https://github.com/Tblob18/JellyCache-R.git
   cd JellyCache-R
   pip install -r requirements.txt
   ```

2. **Create Configuration**
   - Copy example config
   - Edit with your Jellyfin details
   - Verify JSON syntax

3. **Run Setup Script** (if available)
   ```bash
   python3 plexcache_setup.py
   ```

4. **First Run (Dry-Run)**
   ```bash
   python3 plexcache_app.py --dry-run
   ```

5. **Verify Output**
   - Check log file created
   - Review dry-run actions
   - Verify no errors

6. **First Production Run**
   ```bash
   python3 plexcache_app.py
   ```

7. **Post-Run Verification**
   - Check files moved to cache
   - Verify .plexcached markers
   - Review log file
   - Test media playback in Jellyfin

### Test Procedure 2: Configuration Changes

**Purpose:** Validate configuration modifications

1. **Backup Current Config**
   ```bash
   cp jellycache_settings.json jellycache_settings.json.bak
   ```

2. **Modify Configuration**
   - Change a specific setting
   - Save file

3. **Validate JSON**
   ```bash
   python3 -m json.tool jellycache_settings.json
   ```

4. **Test with Dry-Run**
   ```bash
   python3 plexcache_app.py --dry-run
   ```

5. **Verify Changes Applied**
   - Review log output
   - Check configuration values logged

6. **Production Run**
   - Execute without dry-run
   - Monitor behavior matches expectations

### Test Procedure 3: Path Mapping Validation

**Purpose:** Ensure path mappings work correctly

1. **Display Current Mappings**
   ```bash
   python3 plexcache_app.py --show-mappings
   ```

2. **Add Test File to Array**
   ```bash
   cp test_media.mkv /mnt/array/tv/Show/test_media.mkv
   ```

3. **Verify Jellyfin Detects File**
   - Check in Jellyfin UI
   - Note the path Jellyfin reports

4. **Add to Continue Watching**
   - Start playback briefly
   - Ensure it appears in Continue Watching

5. **Run JellyCache**
   ```bash
   python3 plexcache_app.py
   ```

6. **Verify File Moved**
   ```bash
   ls -la /mnt/cache/tv/Show/
   ls -la /mnt/array/tv/Show/
   ```

7. **Check .plexcached Marker**
   ```bash
   ls -la /mnt/array/tv/Show/*.plexcached
   ```

8. **Verify Jellyfin Still Plays**
   - Play the file in Jellyfin
   - Should work from cache location

### Test Procedure 4: Cache Cleanup Testing

**Purpose:** Verify cache retention policies work

1. **Manually Set Old Timestamps**
   ```bash
   # On Linux - use a date from the past (e.g., December 1, 2025)
   touch -t 202512010000 /mnt/cache/tv/old_file.mkv
   ```

2. **Check Priority File**
   ```bash
   python3 plexcache_app.py --show-priorities
   ```

3. **Run JellyCache**
   ```bash
   python3 plexcache_app.py
   ```

4. **Verify Old Files Removed**
   ```bash
   ls -la /mnt/cache/tv/
   ```

5. **Verify Priority Files Retained**
   - Files in Continue Watching should stay
   - Favorites should stay if configured

6. **Check Logs**
   - Review cleanup actions
   - Verify space reclaimed

### Test Procedure 5: Multi-User Testing

**Purpose:** Test multiple Jellyfin users

1. **Create Test Users in Jellyfin**
   - User A, User B, User C

2. **Configure Skip Lists**
   ```json
   "skip_ondeck": ["UserB"],
   "skip_favorites": ["UserC"]
   ```

3. **Add Media for Each User**
   - User A: Add show to Continue Watching
   - User B: Add show to Continue Watching (should be skipped)
   - User C: Add show to Favorites (should be skipped)

4. **Run JellyCache**
   ```bash
   python3 plexcache_app.py
   ```

5. **Verify Results**
   - User A's media should be cached
   - User B's Continue Watching should be skipped
   - User C's Favorites should be skipped

6. **Check Logs**
   - Verify user filtering logged
   - No errors for skipped users

### Test Procedure 6: Watched Media Return

**Purpose:** Test moving watched media back to array

1. **Cache Media via Continue Watching**
   - Start playback of a show
   - Let it cache

2. **Complete Watching**
   - Watch to completion (or mark watched)
   - Verify removed from Continue Watching

3. **Run JellyCache**
   ```bash
   python3 plexcache_app.py
   ```

4. **Verify File Moved Back**
   ```bash
   ls -la /mnt/array/tv/Show/
   ```

5. **Check .plexcached Removed**
   ```bash
   # Should not exist
   ls -la /mnt/array/tv/Show/*.plexcached
   ```

6. **Verify Jellyfin Access**
   - File should still be accessible
   - Should play from array location

### Test Procedure 7: Subtitle Handling

**Purpose:** Verify subtitles move with media

1. **Create Media with Subtitles**
   ```bash
   touch test_show.mkv
   touch test_show.en.srt
   touch test_show.es.srt
   touch test_show.en.forced.srt
   ```

2. **Add to Continue Watching**
   - Via Jellyfin UI

3. **Run JellyCache**
   ```bash
   python3 plexcache_app.py
   ```

4. **Verify All Files Moved**
   ```bash
   ls -la /mnt/cache/tv/Show/
   # Should show:
   # test_show.mkv
   # test_show.en.srt
   # test_show.es.srt
   # test_show.en.forced.srt
   ```

5. **Test Playback**
   - Play in Jellyfin
   - Verify subtitles available

### Test Procedure 8: Error Recovery

**Purpose:** Test handling of various error conditions

1. **Test: Missing Destination Directory**
   ```bash
   rmdir /mnt/cache/tv/Show
   python3 plexcache_app.py
   # Should create directory or handle gracefully
   ```

2. **Test: Read-Only Destination**
   ```bash
   chmod 555 /mnt/cache/tv
   python3 plexcache_app.py
   # Should detect and report error
   chmod 755 /mnt/cache/tv
   ```

3. **Test: Jellyfin Server Down**
   ```bash
   # Stop Jellyfin temporarily
   python3 plexcache_app.py
   # Should handle connection error gracefully
   ```

4. **Test: Invalid API Key**
   - Change API key to invalid value
   - Run JellyCache
   - Should report authentication error

5. **Test: Corrupted Config**
   - Break JSON syntax
   - Run JellyCache
   - Should report config error

6. **Verify Recovery**
   - Fix each error
   - Verify normal operation resumes

### Test Procedure 9: Performance Testing

**Purpose:** Measure and verify performance

1. **Prepare Large Test Set**
   - 100+ media files
   - Various sizes (1GB-20GB)

2. **Run with Timing**
   ```bash
   time python3 plexcache_app.py
   ```

3. **Monitor System Resources**
   ```bash
   # In another terminal
   top -p $(pgrep -f plexcache_app)
   ```

4. **Check Concurrent Operations**
   - Verify configured parallelism
   - Monitor network/disk I/O

5. **Review Logs**
   - Check transfer speeds
   - Verify no bottlenecks
   - Look for warnings

6. **Test Different Concurrency Settings**
   - Try different values for:
     - `max_concurrent_moves_array`
     - `max_concurrent_moves_cache`
   - Measure performance impact

### Test Procedure 10: Unraid-Specific Testing

**Purpose:** Test Unraid-specific features (if on Unraid)

1. **Test Mover Exclusion**
   ```bash
   cat /boot/config/plugins/mover.tuning/mover.ignore
   # Should contain JellyCache exclusions
   ```

2. **Test Mover Conflict Prevention**
   ```bash
   # Start Unraid mover
   python3 plexcache_app.py
   # Should detect and exit
   ```

3. **Test Unraid Notifications**
   - Configure Unraid notification level
   - Run JellyCache
   - Check Unraid notification system

4. **Test Array Spin-Down**
   - Let array spin down
   - Verify cache hits don't wake array
   - Run JellyCache (should wake array)

---

## Performance Testing

### Metrics to Measure

1. **File Transfer Speed**
   - Time to move files to cache
   - Time to return files to array
   - Comparison with direct copy

2. **API Response Times**
   - Time to fetch Continue Watching
   - Time to fetch Favorites
   - Time to check active sessions

3. **Memory Usage**
   - Peak memory during operations
   - Memory leaks over time

4. **CPU Usage**
   - Processing overhead
   - Impact of concurrent operations

5. **Disk I/O**
   - Read/write operations per second
   - I/O wait times

### Performance Test Scripts

**Test 1: Transfer Speed Benchmark**

```bash
#!/bin/bash
# Create test files
for i in {1..10}; do
    dd if=/dev/zero of=/tmp/test_array/tv/testfile_$i.mkv bs=1M count=1000
done

# Time the cache operation
time python3 plexcache_app.py

# Calculate average speed
# (Total size) / (Total time)
```

**Test 2: API Performance**

```python
import time
from jellyfin_api import JellyfinManager

start = time.time()
# Make 100 API calls
for i in range(100):
    manager.get_continue_watching()
end = time.time()

avg_time = (end - start) / 100
print(f"Average API call time: {avg_time:.3f}s")
```

**Test 3: Concurrent Operations**

```bash
# Configure high concurrency
# max_concurrent_moves_cache: 10

# Monitor resource usage
vmstat 1 > performance.log &
VMSTAT_PID=$!

# Run JellyCache
python3 plexcache_app.py

# Stop monitoring
kill $VMSTAT_PID

# Analyze results
cat performance.log
```

### Performance Benchmarks

Expected performance targets:

| Operation | Target | Acceptable |
|-----------|--------|------------|
| File move (1GB) | < 10s | < 30s |
| API call | < 1s | < 3s |
| Memory usage | < 500MB | < 1GB |
| CPU usage (avg) | < 50% | < 80% |

---

## Security Testing

### Security Checklist

#### API Security

- [ ] **API Key Protection**
  - [ ] Keys not logged in plain text
  - [ ] Keys not exposed in error messages
  - [ ] Config file has appropriate permissions

- [ ] **API Authentication**
  - [ ] Invalid keys rejected
  - [ ] 401 errors handled gracefully
  - [ ] No credential leakage

#### File System Security

- [ ] **Path Traversal Prevention**
  - [ ] Test: `../../etc/passwd` in paths
  - [ ] Verify sanitization works
  - [ ] No access outside configured paths

- [ ] **File Permissions**
  - [ ] New files have correct permissions
  - [ ] Directories created with proper mode
  - [ ] No world-writable files created

- [ ] **Symlink Handling**
  - [ ] Test symlink attacks
  - [ ] Verify symlinks handled safely
  - [ ] No symlink traversal

#### Configuration Security

- [ ] **Validation**
  - [ ] Invalid values rejected
  - [ ] Required fields enforced
  - [ ] Type checking works

- [ ] **Injection Prevention**
  - [ ] Test command injection in paths
  - [ ] SQL injection not applicable (no SQL)
  - [ ] No shell command execution vulnerabilities

### Security Test Cases

**Test 1: Path Traversal Attack**

```python
def test_path_traversal():
    """Test that path traversal is prevented."""
    malicious_config = {
        "cache_dir": "/tmp/test/../../etc/",
        # ... other settings
    }
    # Should reject or sanitize
    # Verify no access outside /tmp/test
```

**Test 2: API Key Leakage**

```python
def test_api_key_not_logged():
    """Verify API key doesn't appear in logs."""
    # Run application
    # Read log file
    # Assert API key not present
    with open('plexcache.log') as f:
        content = f.read()
        assert 'api_key_value' not in content
```

**Test 3: File Permission Validation**

```bash
# Run JellyCache
python3 plexcache_app.py

# Check file permissions
ls -l /mnt/cache/tv/
# Should not show 777 permissions

# Check for world-writable files
find /mnt/cache -type f -perm -002
# Should return no results
```

**Test 4: Configuration Injection**

```python
def test_command_injection_in_path():
    """Test command injection prevention."""
    malicious_config = {
        "cache_dir": "/tmp/test; rm -rf /",
        # ... other settings
    }
    # Should not execute the command
    # Verify /tmp/test is not deleted
```

---

## Regression Testing

### Regression Test Suite

After any code changes, verify:

#### Core Functionality
- [ ] Files move to cache correctly
- [ ] Files return to array when watched
- [ ] .plexcached markers work
- [ ] Subtitles move with media
- [ ] Path mappings resolve correctly

#### Configuration
- [ ] All config options respected
- [ ] Default values applied
- [ ] Invalid configs rejected
- [ ] Path mappings work

#### API Integration
- [ ] Jellyfin connection works
- [ ] Continue Watching fetched
- [ ] Favorites fetched
- [ ] Active sessions detected

#### Error Handling
- [ ] Graceful degradation
- [ ] Error messages clear
- [ ] No data loss on errors
- [ ] Recovery mechanisms work

#### Performance
- [ ] No performance regression
- [ ] Memory usage acceptable
- [ ] Concurrent operations work
- [ ] No bottlenecks introduced

### Automated Regression Tests

Create a regression test script:

```bash
#!/bin/bash
# regression_test.sh

echo "Starting regression tests..."

# Test 1: Basic functionality
echo "Test 1: Basic cache operation"
python3 plexcache_app.py --dry-run
if [ $? -ne 0 ]; then
    echo "FAIL: Basic operation failed"
    exit 1
fi

# Test 2: Configuration loading
echo "Test 2: Configuration"
python3 -c "from config import ConfigManager; cm = ConfigManager('jellycache_settings.json'); cm.load_config()"
if [ $? -ne 0 ]; then
    echo "FAIL: Config loading failed"
    exit 1
fi

# Test 3: File operations
echo "Test 3: File operations"
# Create test file
touch /tmp/test_array/tv/test.mkv
python3 plexcache_app.py
# Verify file exists
if [ ! -f /tmp/test_cache/tv/test.mkv ]; then
    echo "FAIL: File not cached"
    exit 1
fi

echo "All regression tests passed!"
```

### Version Upgrade Testing

When upgrading:

1. **Backup Current State**
   - Configuration files
   - Current cache state
   - Log files

2. **Run Pre-Upgrade Tests**
   - Full test suite on old version
   - Document current behavior

3. **Perform Upgrade**
   - Update code
   - Check for breaking changes

4. **Run Post-Upgrade Tests**
   - Same tests as pre-upgrade
   - Verify behavior unchanged
   - Check new features work

5. **Migration Testing**
   - Test config migration
   - Verify data compatibility
   - Check for deprecated features

---

## Test Data Requirements

### Media Files

**Required Test Files:**

1. **TV Show Episodes**
   - Single episode: `Show.S01E01.mkv` (1-2GB)
   - Multiple episodes: `Show.S01E02.mkv`, `Show.S01E03.mkv`
   - Multiple seasons
   - Various codecs: H.264, H.265

2. **Movies**
   - Standard movie: `Movie.2024.1080p.mkv` (5-10GB)
   - Movie with year: `Movie (2024).mkv`
   - 4K movie: `Movie.2024.2160p.mkv` (20GB+)

3. **Subtitles**
   - SRT format: `Show.S01E01.en.srt`
   - Multiple languages: `.es.srt`, `.fr.srt`
   - Forced subtitles: `.en.forced.srt`
   - Hearing impaired: `.en.sdh.srt`

4. **Special Cases**
   - Files with spaces: `My Show Name S01E01.mkv`
   - Files with special chars: `Show's.Title.S01E01.mkv`
   - Very long filenames (>255 chars)
   - Unicode characters in names

### Creating Test Media

```bash
#!/bin/bash
# create_test_media.sh

BASE_DIR="/tmp/test_array"

# Create directory structure
mkdir -p $BASE_DIR/tv/TestShow/Season\ 01
mkdir -p $BASE_DIR/movies

# Create dummy video files (100MB each)
for i in {1..5}; do
    dd if=/dev/zero of="$BASE_DIR/tv/TestShow/Season 01/TestShow.S01E0$i.mkv" bs=1M count=100
    # Add subtitles
    touch "$BASE_DIR/tv/TestShow/Season 01/TestShow.S01E0$i.en.srt"
    touch "$BASE_DIR/tv/TestShow/Season 01/TestShow.S01E0$i.es.srt"
done

# Create test movies
dd if=/dev/zero of="$BASE_DIR/movies/TestMovie.2024.1080p.mkv" bs=1M count=500
touch "$BASE_DIR/movies/TestMovie.2024.1080p.en.srt"

echo "Test media created in $BASE_DIR"
```

### Jellyfin Test Setup

1. **Create Test Libraries**
   - TV Shows library pointing to test directory
   - Movies library pointing to test directory

2. **Create Test Users**
   ```
   User: TestUser1 (all features enabled)
   User: TestUser2 (skipped for Continue Watching)
   User: TestUser3 (skipped for Favorites)
   ```

3. **Prepare Test States**
   - Add episodes to Continue Watching
   - Add shows/movies to Favorites
   - Mark some items as watched
   - Create active playback session

---

## CI/CD Integration

### Continuous Integration Setup

#### GitHub Actions Example

Create `.github/workflows/test.yml`:

```yaml
name: JellyCache Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-mock responses
    
    - name: Create test directories
      run: |
        mkdir -p /tmp/test_array/{tv,movies}
        mkdir -p /tmp/test_cache/{tv,movies}
    
    - name: Run unit tests
      run: |
        pytest tests/ --cov=. --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
    
    - name: Run linting
      run: |
        pip install pylint
        pylint *.py --disable=C0111,R0801
    
    - name: Run security scan
      run: |
        pip install bandit
        bandit -r . -f json -o bandit-report.json
```

### Pre-Commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
  
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
  
  - repo: https://github.com/PyCQA/pylint
    rev: v2.17.0
    hooks:
      - id: pylint
```

### Automated Testing Script

```bash
#!/bin/bash
# run_all_tests.sh

set -e  # Exit on error

echo "=== Running JellyCache Test Suite ==="

# Setup
echo "Setting up test environment..."
mkdir -p /tmp/test_array/{tv,movies}
mkdir -p /tmp/test_cache/{tv,movies}

# Unit tests
echo "Running unit tests..."
pytest tests/unit/ -v

# Integration tests
echo "Running integration tests..."
pytest tests/integration/ -v

# Security tests
echo "Running security scan..."
bandit -r . -ll

# Linting
echo "Running linter..."
pylint *.py --disable=C0111

# Performance tests
echo "Running performance benchmarks..."
python tests/performance/benchmark.py

# Cleanup
echo "Cleaning up..."
rm -rf /tmp/test_array /tmp/test_cache

echo "=== All tests passed! ==="
```

---

## Known Issues and Edge Cases

### Known Limitations

1. **Large File Handling**
   - Very large files (>100GB) may timeout
   - Consider splitting operations
   - Monitor disk I/O carefully

2. **Network Reliability**
   - Requires stable connection to Jellyfin
   - No automatic retry for failed API calls
   - Long operations may fail on network hiccup

3. **Unicode Support**
   - Some special characters may cause issues
   - Test with your specific character set
   - Report issues with specific characters

4. **Concurrent Access**
   - Single instance lock prevents parallel runs
   - Manual intervention needed if lock stuck
   - Lock file location: `plexcache.lock`

### Edge Cases to Test

1. **File Name Edge Cases**
   ```
   - File with dots: "My.Show.Name.S01E01.mkv"
   - File with spaces: "My Show Name S01E01.mkv"
   - Unicode: "Show名字.S01E01.mkv"
   - Long names: 255+ character filenames
   - Special chars: quotes, apostrophes, ampersands
   ```

2. **Path Edge Cases**
   ```
   - Deeply nested directories (>10 levels)
   - Very long path names (>4096 chars on Linux)
   - Paths with symbolic links
   - Network paths (NFS, SMB)
   - Case sensitivity issues
   ```

3. **Media Edge Cases**
   ```
   - 4K/8K very large files
   - Multi-episode files
   - Files with no extension
   - Zero-byte files
   - Corrupted media files
   ```

4. **State Edge Cases**
   ```
   - Empty Continue Watching
   - No favorites configured
   - All users skipped
   - No cacheable paths
   - Full cache disk
   - Full array disk
   ```

5. **Timing Edge Cases**
   ```
   - File added while script running
   - File deleted during transfer
   - Jellyfin restarted mid-operation
   - System time changes
   - Daylight saving time transitions
   ```

### Bug Reporting

When reporting issues, include:

1. **Environment Information**
   ```
   - OS version
   - Python version
   - Jellyfin version
   - JellyCache-R version/commit
   - Hardware specs (RAM, CPU, disk)
   ```

2. **Configuration** (sanitized)
   - Remove API keys
   - Include path mappings
   - Include relevant settings

3. **Log Files**
   - Full log output
   - Error messages
   - Stack traces

4. **Reproduction Steps**
   - Exact steps to reproduce
   - Expected vs actual behavior
   - Frequency (always, sometimes, once)

5. **Test Results**
   - Which tests pass/fail
   - Any workarounds found
   - Related issues

---

## Test Reporting

### Test Report Template

```markdown
# JellyCache-R Test Report

**Date:** YYYY-MM-DD
**Tester:** Name
**Version:** vX.X.X
**Environment:** OS, Python version, Jellyfin version

## Test Summary

- Total Tests: XX
- Passed: XX
- Failed: XX
- Skipped: XX
- Pass Rate: XX%

## Test Results

### Unit Tests
| Module | Test | Status | Notes |
|--------|------|--------|-------|
| config.py | test_load_valid_config | ✅ PASS | |
| config.py | test_load_missing_config | ✅ PASS | |
| ... | ... | ... | ... |

### Integration Tests
| Scenario | Status | Notes |
|----------|--------|-------|
| End-to-End Cache | ✅ PASS | All files moved correctly |
| Multi-User Support | ❌ FAIL | User skip not working |
| ... | ... | ... |

### Manual Tests
| Procedure | Status | Notes |
|-----------|--------|-------|
| First-Time Setup | ✅ PASS | |
| Path Mapping | ✅ PASS | |
| ... | ... | ... |

## Issues Found

### Critical Issues
1. **Issue Description**
   - Severity: Critical
   - Reproducibility: Always
   - Impact: Data loss possible
   - Workaround: None

### Major Issues
(List major issues)

### Minor Issues
(List minor issues)

## Performance Results

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| File Move (1GB) | <10s | 8.5s | ✅ |
| API Response | <1s | 0.7s | ✅ |
| Memory Usage | <500MB | 450MB | ✅ |

## Recommendations

1. Fix critical issues before release
2. Document known limitations
3. Add more error handling for X
4. Consider performance optimization for Y

## Sign-Off

- [ ] All critical tests passed
- [ ] No blocking issues found
- [ ] Performance acceptable
- [ ] Ready for release / Needs more work

**Tester Signature:** ________________
**Date:** ________________
```

### Automated Test Reports

Configure pytest to generate HTML reports:

```bash
pip install pytest-html
pytest --html=report.html --self-contained-html
```

Generate coverage reports:

```bash
pytest --cov=. --cov-report=html
# Open htmlcov/index.html
```

---

## Appendix

### Test File Locations

```
JellyCache-R/
├── tests/
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_jellyfin_api.py
│   │   ├── test_file_operations.py
│   │   ├── test_system_utils.py
│   │   └── test_logging_config.py
│   ├── integration/
│   │   ├── test_end_to_end.py
│   │   ├── test_multi_user.py
│   │   └── test_cache_management.py
│   ├── performance/
│   │   └── benchmark.py
│   ├── fixtures/
│   │   ├── test_config.json
│   │   └── test_media/
│   └── conftest.py
├── TESTING.md (this file)
└── README.md
```

### Useful Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_config.py

# Run with coverage
pytest --cov=.

# Run with verbose output
pytest -v

# Run only failed tests
pytest --lf

# Run in parallel
pytest -n auto

# Generate HTML report
pytest --html=report.html

# Run with debugging
pytest --pdb

# Dry run (show what would run)
pytest --collect-only
```

### Resources

- **Jellyfin API Documentation:** https://api.jellyfin.org/
- **Python Testing:** https://docs.pytest.org/
- **Original PlexCache-R:** https://github.com/StudioNirin/PlexCache-R
- **Issue Tracker:** https://github.com/Tblob18/JellyCache-R/issues

### Glossary

- **Array:** Primary storage location (usually spinning disks)
- **Cache:** Fast storage (usually SSD)
- **Continue Watching:** Jellyfin's in-progress shows/movies
- **Favorites:** User-marked favorite content
- **.plexcached:** Marker file indicating cached content
- **Path Mapping:** Configuration for translating paths
- **Dry-Run:** Testing mode that doesn't move files

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-28 | Initial testing document |

---

**Last Updated:** 2026-01-28
**Document Owner:** JellyCache-R Project
**Review Schedule:** Quarterly or with major releases
