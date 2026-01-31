# JellyCache-R v2.1.2 Upstream Sync TODO

## Fixes to Implement

- [x] 1. Add `SUBTITLE_EXTENSIONS` constant and `is_subtitle_file()` helper (after line 22)
- [x] 2. Update `find_matching_plexcached()` to accept `source_file` parameter and add type-matching logic
- [x] 3. Update all callers of `find_matching_plexcached()` to pass the source file
- [x] 4. Add `create_plexcached_backups` and `hardlinked_files` parameters to `FileMover.__init__`
- [x] 5. Update `_move_to_cache()` to handle the new backup options and hard-link tracking
- [x] 6. Update `_move_to_array()` to handle hard-link restoration
- [x] 7. Fix subtitle suffix stripping in `_extract_media_name()` to use a loop
- [x] 8. Update `CacheTimestampTracker` with inode support

## Summary of Changes

### Bug Fixes
1. **Subtitle/Video cross-matching prevention**: `find_matching_plexcached()` now accepts a `source_file` parameter and only matches files of the same type (video<->video, subtitle<->subtitle). This prevents the bug where a video's `.plexcached` backup could be incorrectly matched to a subtitle file with the same title.

2. **Chained subtitle suffix stripping**: `_extract_media_name()` now uses a loop to strip language codes, handling files like `Movie.en.hi.srt` that have multiple suffixes.

### New Features
1. **Optional .plexcached backups**: New `create_plexcached_backups` parameter in `FileMover.__init__`. When set to `False`, array files are deleted after copying to cache instead of being renamed to `.plexcached`. This saves disk space at the cost of requiring a copy operation when restoring to array.

2. **Hard-linked file support**: New `hardlinked_files` parameter in `FileMover.__init__` with three modes:
   - `"skip"` (default): Skip caching files with multiple hard links (safe for seeders)
   - `"copy"`: Copy to cache but leave original array file intact (preserves hard links for seeding)
   - `"normal"`: Treat hard-linked files normally (breaks hard links on array)

3. **Inode tracking**: `CacheTimestampTracker.record_cache_time()` now accepts an optional `original_inode` parameter, and a new `get_original_inode()` method retrieves it. This enables proper restoration of hard-linked files.
