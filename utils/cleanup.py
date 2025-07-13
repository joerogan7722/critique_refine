import os
import shutil
from datetime import datetime
import logging
from typing import List


def cleanup_logs(log_dirs: List[str] = None, archive_base_dir="reviews/self-improve/archive", archive_days=7):
    """
    Cleans up log files by archiving old ones.

    Args:
        log_dirs (List[str]): Directories where log files are stored. Defaults to ["logs", "reviews/self-improve"].
        archive_base_dir (str): Base directory to move old logs to.
        archive_days (int): Logs older than this many days will be archived.
    """
    if log_dirs is None:
        log_dirs = ["logs", "reviews/self-improve"]

    now = datetime.now()
    
    for log_dir in log_dirs:
        if not os.path.exists(log_dir):
            logging.info(f"Log directory '{log_dir}' does not exist. Skipping.")
            continue

        for filename in os.listdir(log_dir):
            filepath = os.path.join(log_dir, filename)
            
            # Process only .json and .jsonl files
            if os.path.isfile(filepath) and (filename.endswith(".jsonl") or filename.endswith(".json")):
                file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))

                # Archive old logs
                if (now - file_mtime).days > archive_days:
                    try:
                        # Create a date-based subdirectory in the archive
                        archive_subdir = os.path.join(archive_base_dir, file_mtime.strftime("%Y-%m-%d"))
                        os.makedirs(archive_subdir, exist_ok=True)
                        
                        shutil.move(filepath, os.path.join(archive_subdir, filename))
                        logging.info(f"Archived old log: {filename} from {log_dir}")
                    except Exception as e:
                        logging.error(f"Error archiving {filename} from {log_dir}: {e}")
            else:
                logging.debug(f"Skipping non-log file: {filename} in {log_dir}")


if __name__ == "__main__":
    # This part is for direct execution of the script
    # In a real application, logging would be configured externally.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logging.info("Starting log cleanup...")
    cleanup_logs()
    logging.info("Log cleanup finished.")
