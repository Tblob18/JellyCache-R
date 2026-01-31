"""
System utilities for PlexCache.
Handles OS detection, system-specific operations, and path conversions.
"""

import os
import platform
import shutil
import atexit
import fcntl
from typing import Tuple, Optional
import logging


class SingleInstanceLock:
    """
    Prevent multiple instances of PlexCache from running simultaneously.

    Uses flock to ensure only one instance can run at a time.
    The lock is automatically released when the process exits or crashes.
    """

    def __init__(self, lock_file: str):
        self.lock_file = lock_file
        self.lock_fd = None
        self.locked = False

    def acquire(self) -> bool:
        """
        Acquire the lock.

        Returns:
            True if lock acquired successfully, False if another instance is running.
        """
        try:
            self.lock_fd = open(self.lock_file, 'w')
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

            # Write PID for debugging
            self.lock_fd.write(str(os.getpid()))
            self.lock_fd.flush()
            self.locked = True

            # Register cleanup on exit
            atexit.register(self.release)

            return True

        except (IOError, OSError):
            # Lock is held by another process
            if self.lock_fd:
                self.lock_fd.close()
                self.lock_fd = None
            return False

    def release(self):
        """Release the lock and clean up."""
        if not self.locked:
            return

        try:
            if self.lock_fd:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                self.lock_fd.close()
                self.lock_fd = None

            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)

            self.locked = False
        except Exception:
            pass  # Best effort cleanup


class SystemDetector:
    """Detects and provides information about the current system."""
    
    def __init__(self):
        self.os_name = platform.system()
        self.is_linux = self.os_name != 'Windows'
        self.is_docker = self._detect_docker()
        self.is_unraid = self._detect_unraid()
        
    def _detect_unraid(self) -> bool:
        """Detect if running on Unraid system or in Docker on Unraid.
        
        Detection methods:
        1. Native Unraid: Check for /mnt/user0/ (Unraid's direct disk access path)
        2. Docker on Unraid: Check for disks.ini (requires mounting /var/local/emhttp/)
        3. Docker on Unraid: Check for typical Unraid mount pattern (/mnt/user + /mnt/cache)
        """
        if self.os_name != 'Linux':
            return False
        
        # Native Unraid detection
        if os.path.exists('/mnt/user0/'):
            return True
        
        # Docker on Unraid: check for disks.ini (mounted from host)
        if os.path.exists('/var/local/emhttp/disks.ini'):
            return True
        
        # Docker on Unraid: check for typical Unraid mount pattern
        # Both /mnt/user and /mnt/cache should exist and be directories
        if (os.path.isdir('/mnt/user') and os.path.isdir('/mnt/cache') and 
            self.is_docker):
            return True
        
        return False
    
    def _detect_docker(self) -> bool:
        """Detect if running inside a Docker container."""
        return os.path.exists('/.dockerenv')


class UnraidDiskManager:
    """Manages Unraid disk operations including spin-up detection and wake."""
    
    DISKS_INI_PATH = '/var/local/emhttp/disks.ini'
    
    def __init__(self):
        self.is_available = os.path.exists(self.DISKS_INI_PATH)
        self._disk_status_cache = {}
        self._cache_time = 0
        self._cache_ttl = 5  # seconds
    
    def _parse_disks_ini(self) -> dict:
        """Parse Unraid's disks.ini to get disk status information."""
        import time
        current_time = time.time()
        
        # Return cached result if still valid
        if self._disk_status_cache and (current_time - self._cache_time) < self._cache_ttl:
            return self._disk_status_cache
        
        disks = {}
        if not os.path.exists(self.DISKS_INI_PATH):
            return disks
        
        try:
            current_disk = None
            with open(self.DISKS_INI_PATH, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('[') and line.endswith(']'):
                        current_disk = line[1:-1]
                        disks[current_disk] = {}
                    elif '=' in line and current_disk:
                        key, value = line.split('=', 1)
                        disks[current_disk][key.strip()] = value.strip().strip('"')
            
            self._disk_status_cache = disks
            self._cache_time = current_time
        except Exception as e:
            logging.debug(f"Error parsing disks.ini: {e}")
        
        return disks
    
    def get_disk_for_file(self, file_path: str) -> Optional[str]:
        """
        Determine which Unraid disk a file resides on.
        
        For /mnt/user/ paths, checks each /mnt/disk*/ to find the actual location.
        Returns the disk name (e.g., 'disk1') or None if not found.
        """
        # If it's already a /mnt/disk*/ path, extract the disk name
        if file_path.startswith('/mnt/disk'):
            parts = file_path.split('/')
            if len(parts) >= 3:
                return parts[2]  # e.g., 'disk1'
        
        # For /mnt/user/ paths, we need to find which disk has the file
        if file_path.startswith('/mnt/user/'):
            # Extract the path relative to /mnt/user/
            relative_path = file_path[len('/mnt/user/'):]
            
            # Check each disk
            try:
                for entry in os.listdir('/mnt'):
                    if entry.startswith('disk') and entry[4:].isdigit():
                        disk_path = f'/mnt/{entry}/{relative_path}'
                        if os.path.exists(disk_path):
                            return entry
            except OSError:
                pass
        
        return None
    
    def is_disk_spun_up(self, disk_name: str) -> bool:
        """
        Check if a specific disk is spun up.
        
        Args:
            disk_name: Name like 'disk1', 'disk2', etc.
            
        Returns:
            True if spun up, False if spun down, True if status unknown (assume up)
        """
        disks = self._parse_disks_ini()
        
        if disk_name not in disks:
            logging.debug(f"Disk {disk_name} not found in disks.ini, assuming spun up")
            return True
        
        # Unraid uses 'spundown' field: '0' = spun up, '1' = spun down
        spundown = disks[disk_name].get('spundown', '0')
        is_up = spundown != '1'
        
        logging.debug(f"Disk {disk_name} spin status: {'up' if is_up else 'down'}")
        return is_up
    
    def spin_up_disk(self, disk_name: str, timeout: int = 30) -> bool:
        """
        Spin up a disk by reading from it.
        
        Args:
            disk_name: Name like 'disk1', 'disk2', etc.
            timeout: Maximum seconds to wait for spin-up
            
        Returns:
            True if disk is spun up, False on timeout
        """
        import time
        
        if self.is_disk_spun_up(disk_name):
            return True
        
        logging.info(f"Spinning up {disk_name}...")
        
        # Find a file on the disk to read (triggers spin-up)
        disk_path = f'/mnt/{disk_name}'
        if not os.path.exists(disk_path):
            logging.warning(f"Disk path not found: {disk_path}")
            return False
        
        # Try to read the disk - this triggers spin-up
        try:
            # Reading the directory listing is enough to trigger spin-up
            os.listdir(disk_path)
        except OSError as e:
            logging.warning(f"Error accessing {disk_path}: {e}")
        
        # Wait for spin-up with polling
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            # Clear cache to get fresh status
            self._disk_status_cache = {}
            
            if self.is_disk_spun_up(disk_name):
                elapsed = time.time() - start_time
                logging.info(f"Disk {disk_name} spun up in {elapsed:.1f}s")
                return True
            
            time.sleep(1)
        
        logging.warning(f"Timeout waiting for {disk_name} to spin up")
        return False
    
    def ensure_disks_for_files(self, file_paths: list, timeout_per_disk: int = 30) -> dict:
        """
        Ensure all disks needed for the given files are spun up.
        
        Args:
            file_paths: List of file paths to check
            timeout_per_disk: Timeout in seconds for each disk spin-up
            
        Returns:
            Dict mapping disk names to their spin-up status (True/False)
        """
        if not self.is_available:
            logging.debug("Unraid disk management not available (not on Unraid or disks.ini missing)")
            return {}
        
        # Find unique disks needed
        disks_needed = set()
        for file_path in file_paths:
            disk = self.get_disk_for_file(file_path)
            if disk:
                disks_needed.add(disk)
        
        if not disks_needed:
            logging.debug("No array disks identified for files")
            return {}
        
        logging.debug(f"Files require disks: {', '.join(sorted(disks_needed))}")
        
        # Check and spin up each disk
        results = {}
        disks_to_spinup = []
        
        for disk in disks_needed:
            if not self.is_disk_spun_up(disk):
                disks_to_spinup.append(disk)
        
        if disks_to_spinup:
            logging.info(f"Spinning up {len(disks_to_spinup)} disk(s): {', '.join(disks_to_spinup)}")
            for disk in disks_to_spinup:
                results[disk] = self.spin_up_disk(disk, timeout_per_disk)
        else:
            logging.debug("All required disks are already spun up")
            for disk in disks_needed:
                results[disk] = True
        
        return results


class FileUtils:
    """Utility functions for file operations."""
    
    def __init__(self, is_linux: bool, permissions: int = 0o777):
        self.is_linux = is_linux
        self.permissions = permissions
        self.is_unraid = is_unraid_system()
    
    def check_path_exists(self, path: str) -> None:
        """Check if path exists, is a directory, and is writable."""
        logging.debug(f"Checking path: {path}")
        
        if not os.path.exists(path):
            logging.error(f"Path does not exist: {path}")
            raise FileNotFoundError(f"Path {path} does not exist.")
        
        if not os.path.isdir(path):
            logging.error(f"Path is not a directory: {path}")
            raise NotADirectoryError(f"Path {path} is not a directory.")
        
        if not os.access(path, os.W_OK):
            logging.error(f"Path is not writable: {path}")
            raise PermissionError(f"Path {path} is not writable.")
        
        logging.debug(f"Path validation successful: {path}")
    
    def get_free_space(self, directory: str) -> Tuple[float, str]:
        """Get free space in a human-readable format."""
        if not os.path.exists(directory):
            raise FileNotFoundError(f"Invalid path, unable to calculate free space for: {directory}.")

        stat = os.statvfs(directory)
        free_space_bytes = stat.f_bfree * stat.f_frsize
        return self._convert_bytes_to_readable_size(free_space_bytes)

    def get_total_drive_size(self, directory: str) -> int:
        """Get total size of the drive in bytes."""
        if not os.path.exists(directory):
            raise FileNotFoundError(f"Invalid path, unable to calculate drive size for: {directory}.")

        stat = os.statvfs(directory)
        return stat.f_blocks * stat.f_frsize

    def get_total_size_of_files(self, files: list) -> Tuple[float, str]:
        """Calculate total size of files in human-readable format."""
        total_size_bytes = 0
        skipped_files = []
        for file in files:
            try:
                total_size_bytes += os.path.getsize(file)
            except (OSError, FileNotFoundError):
                skipped_files.append(file)

        if skipped_files:
            logging.warning(f"Could not get size for {len(skipped_files)} files (will skip during move)")
            for f in skipped_files:
                logging.debug(f"  Skipping inaccessible file: {f}")

        return self._convert_bytes_to_readable_size(total_size_bytes)
    
    def _convert_bytes_to_readable_size(self, size_bytes: int) -> Tuple[float, str]:
        """Convert bytes to human-readable format."""
        if size_bytes >= (1024 ** 4):
            size = size_bytes / (1024 ** 4)
            unit = 'TB'
        elif size_bytes >= (1024 ** 3):
            size = size_bytes / (1024 ** 3)
            unit = 'GB'
        elif size_bytes >= (1024 ** 2):
            size = size_bytes / (1024 ** 2)
            unit = 'MB'
        else:
            size = size_bytes / 1024
            unit = 'KB'
        
        return size, unit
    
    def _spin_up_read(self, file_path: str, timeout: int = 60) -> bool:
        """
        Trigger disk spin-up by reading from the file.
        
        On Unraid with spun-down disks, accessing a file through /mnt/user/
        will trigger the disk to spin up. We read a small chunk and wait
        for the read to complete, which ensures the disk is ready.
        
        Args:
            file_path: Path to the file to read
            timeout: Maximum seconds to wait for the read
            
        Returns:
            True if read succeeded, False otherwise
        """
        import time
        start_time = time.time()
        
        try:
            logging.debug(f"Triggering disk spin-up by reading from: {file_path}")
            with open(file_path, 'rb') as f:
                # Read first 4KB - this triggers the disk spin-up
                chunk = f.read(4096)
                if len(chunk) > 0:
                    elapsed = time.time() - start_time
                    if elapsed > 5:
                        logging.info(f"Disk spin-up completed after {elapsed:.1f}s for: {os.path.basename(file_path)}")
                    else:
                        logging.debug(f"File accessible (read {len(chunk)} bytes in {elapsed:.1f}s)")
                    return True
                else:
                    logging.warning(f"Read 0 bytes from file: {file_path}")
                    return False
        except IOError as e:
            elapsed = time.time() - start_time
            logging.error(f"Failed to read file after {elapsed:.1f}s: {file_path} - {e}")
            return False
    
    def copy_file_with_permissions(self, src: str, dest: str, verbose: bool = False) -> int:
        """Copy a file preserving original ownership and permissions (Linux only)."""
        logging.debug(f"Copying file from {src} to {dest}")

        try:
            # Trigger disk spin-up by reading from source before getting size
            # This is especially important on Unraid where disks may be sleeping
            if self.is_unraid:
                if not self._spin_up_read(src):
                    raise RuntimeError(f"Failed to access source file (disk may be unresponsive): {src}")
            
            # Get source file size before copy for verification
            src_size = os.path.getsize(src)
            if src_size == 0:
                raise RuntimeError(f"Source file appears empty (0 bytes): {src}")

            if self.is_linux:
                # Get source file ownership before copy
                stat_info = os.stat(src)
                src_uid = stat_info.st_uid
                src_gid = stat_info.st_gid
                src_mode = stat_info.st_mode

                # Copy the file (preserves metadata like timestamps)
                shutil.copy2(src, dest)

                # Verify copy succeeded - check destination size matches source
                dest_size = os.path.getsize(dest)
                if dest_size != src_size:
                    # Remove failed copy
                    try:
                        os.remove(dest)
                    except OSError:
                        pass
                    raise RuntimeError(
                        f"Copy verification failed: size mismatch. "
                        f"Source: {src_size} bytes, Destination: {dest_size} bytes. "
                        f"This may indicate the source disk is spun down or unresponsive."
                    )

                # Restore original ownership (shutil.copy2 doesn't preserve uid/gid)
                os.chown(dest, src_uid, src_gid)
                original_umask = os.umask(0)
                os.chmod(dest, self.permissions)
                os.umask(original_umask)

                if verbose:
                    # Log ownership details for debugging
                    dest_stat = os.stat(dest)
                    logging.debug(f"File copied: {src} -> {dest}")
                    logging.debug(f"  Preserved ownership: uid={dest_stat.st_uid}, gid={dest_stat.st_gid}")
                    logging.debug(f"  Mode: {oct(dest_stat.st_mode)}")
                else:
                    logging.debug(f"File copied with permissions preserved: {dest}")
            else:  # Windows logic
                shutil.copy2(src, dest)
                # Verify on Windows too
                dest_size = os.path.getsize(dest)
                if dest_size != src_size:
                    try:
                        os.remove(dest)
                    except OSError:
                        pass
                    raise RuntimeError(f"Copy verification failed: size mismatch.")
                logging.debug(f"File copied (Windows): {src} -> {dest}")

            return 0
        except (FileNotFoundError, PermissionError, Exception) as e:
            logging.error(f"Error copying file from {src} to {dest}: {str(e)}")
            raise RuntimeError(f"Error copying file: {str(e)}")

    def create_directory_with_permissions(self, path: str, src_file_for_permissions: str) -> None:
        """Create directory with proper permissions."""
        logging.debug(f"Creating directory with permissions: {path}")
        
        if not os.path.exists(path):
            if self.is_linux:
                # Get the permissions of the source file
                stat_info = os.stat(src_file_for_permissions)
                uid = stat_info.st_uid
                gid = stat_info.st_gid
                original_umask = os.umask(0)
                os.makedirs(path, exist_ok=True)
                os.chown(path, uid, gid)
                os.chmod(path, self.permissions)
                os.umask(original_umask)
                logging.debug(f"Directory created with permissions (Linux): {path}")
            else:  # Windows platform
                os.makedirs(path, exist_ok=True)
                logging.debug(f"Directory created (Windows): {path}")
        else:
            logging.debug(f"Directory already exists: {path}") 