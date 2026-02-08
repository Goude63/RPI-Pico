import os

def check_disk_space(path='/'):
    """
    Checks the free and total disk space on the given path (default is root '/').
    Returns total_bytes, free_bytes
    """
    try:
        # Get filesystem statistics
        # Index 0: f_bsize (fundamental block size)
        # Index 1: f_frsize (fragment size) - MicroPython often uses same as bsize
        # Index 2: f_blocks (total blocks)
        # Index 3: f_bfree (free blocks for unprivileged users)
        # Index 4: f_bavail (free blocks available to non-super user)
        # Index 5: f_files (total inodes)
        # Index 6: f_ffree (free inodes)
        # Index 7: f_favail (free inodes available to non-super user)
        # Index 8: f_fsid (filesystem ID)
        # Index 9: f_flag (mount flags)
        # Index 10: f_namemax (maximum filename length)
        stat = os.statvfs(path)

        # Calculate sizes in bytes
        block_size = stat[0]
        total_blocks = stat[2]
        free_blocks = stat[3] # or stat[4] for available blocks

        total_bytes = total_blocks * block_size
        free_bytes = free_blocks * block_size
        used_bytes = total_bytes - free_bytes

        # Convert to KB for human readability
        kb = 1024
        print(f"Total space: {total_bytes / kb:,.2f} KB")
        print(f"Used space:  {used_bytes / kb:,.2f} KB")
        print(f"Free space:  {free_bytes / kb:,.2f} KB")
        
        return total_bytes, free_bytes

    except OSError as e:
        print(f"Error checking disk space: {e}")
        return 0, 0

# Example usage:
if __name__ == "__main__":
    check_disk_space('/')
