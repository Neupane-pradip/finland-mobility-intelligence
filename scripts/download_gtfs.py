"""Download a Tampere GTFS snapshot and identify its contents."""

import hashlib
import tempfile
import json
import sys
import time
from urllib.error import HTTPError
from urllib.error import URLError
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import is_zipfile


SOURCE_URL = (
    "https://data.itsfactory.fi/journeys/files/"
    "gtfs/latest/gtfs_tampere.zip"
)

# These are project limits, not rules from the data provider.
TIMEOUT_SECONDS = 30
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # 100 MiB


def calculate_sha256(file_path):
    """Return a fingerprint of the file's contents."""
    fingerprint = hashlib.sha256()

    with file_path.open("rb") as source:
        while True:
            chunk = source.read(1024 * 1024)

            if not chunk:
                break

            fingerprint.update(chunk)

    return fingerprint.hexdigest()


def download_snapshot(source_url, output_folder):
    """Download into a temporary file before saving a complete snapshot."""
    output_folder.mkdir(parents=True, exist_ok=True)

    request = Request(
        source_url,
        headers={"User-Agent": "FinlandMobilityIntelligence/0.1"},
    )

    # The temporary folder is removed automatically, including after an error.
    with tempfile.TemporaryDirectory(dir=output_folder) as temporary_folder:
        temporary_path = Path(temporary_folder) / "download.zip"
        downloaded_bytes = 0

        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            with temporary_path.open("wb") as destination:
                while True:
                    chunk = response.read(1024 * 1024)

                    if not chunk:
                        break

                    downloaded_bytes += len(chunk)

                    if downloaded_bytes > MAX_DOWNLOAD_BYTES:
                        raise ValueError("Download exceeds our size limit")

                    destination.write(chunk)

        # A server might return an error page instead of a ZIP.
        # This checks the archive format, not the GTFS tables inside it.
        if not is_zipfile(temporary_path):
            raise ValueError("The downloaded file is not a ZIP archive")

        fingerprint = calculate_sha256(temporary_path)
        saved_path = output_folder / f"{fingerprint}.zip"

        if saved_path.exists():
            # Verify the existing file before trusting its filename.
            if calculate_sha256(saved_path) != fingerprint:
                raise ValueError("Existing snapshot does not match its filename")

            print("This snapshot is already saved.")
        else:
            temporary_path.rename(saved_path)
            print("Saved a new snapshot.")

    return saved_path, fingerprint, downloaded_bytes

def record_retrieval(log_path, started_at, saved_path, fingerprint, size):
    """Append one successful download event to the log."""
    record = {
        "source_url": SOURCE_URL,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": fingerprint,
        "size_bytes": size,
        "started_at_utc": started_at,
        "snapshot_file": saved_path.name,
        "status": "success",
    }

    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Append preserves earlier records.
    # Each line is a separate JSON object: this format is called JSON Lines.
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record) + "\n")

def record_failure(log_path, started_at, error):
    """Save information about an unsuccessful download."""
    record = {
        "source_url": SOURCE_URL,
        "started_at_utc": started_at,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "failed",
        "error_type": type(error).__name__,
        "error_message": str(error),
    }

    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record) + "\n")

def download_with_retries(source_url, output_folder):
    """Try up to three times when a temporary network problem occurs."""
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            return download_snapshot(source_url, output_folder)

        # HTTPError is also a URLError, so check it first.
        except HTTPError as error:
            # Retry only these server errors.
            if error.code not in (500, 502, 503, 504):
                raise

            if attempt == max_attempts:
                raise

        except (URLError, TimeoutError, ConnectionError):
            if attempt == max_attempts:
                raise

        # Wait 1 second after the first failure, then 2 seconds.
        wait_seconds = 2 ** (attempt - 1)
        print(
            f"Attempt {attempt} failed. "
            f"Trying again in {wait_seconds} second(s)."
        )
        time.sleep(wait_seconds)

def main():
    project_root = Path(__file__).resolve().parent.parent
    raw_folder = project_root / "data" / "raw"
    output_folder = raw_folder / "snapshots"
    log_path = raw_folder / "retrievals.jsonl"

    started_at = datetime.now(timezone.utc).isoformat()

    try:
        saved_path, fingerprint, size = download_with_retries(
            SOURCE_URL,
            output_folder,
        )
    except (URLError, OSError, ValueError) as error:
        record_failure(log_path, started_at, error)
        print(f"Download failed: {error}", file=sys.stderr)
        return 1

    record_retrieval(
        log_path,
        started_at,
        saved_path,
        fingerprint,
        size,
    )

    print("Saved file:", saved_path)
    print("Size in bytes:", size)
    print("SHA-256:", fingerprint)
    print("Retrieval log:", log_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())