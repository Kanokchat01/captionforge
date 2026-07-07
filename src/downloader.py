"""
Download a task's video_url to local disk before handing it to Gemini.
Bounded timeout + retries per the team's own error-handling plan (Use Case 1
in hackathon_strategy_guide.md): don't let one bad clip stall the whole run.
"""
import os
import time

import requests

DOWNLOAD_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3


def download_video(url: str, output_dir: str = "/tmp/captionforge_videos") -> str:
    os.makedirs(output_dir, exist_ok=True)
    filename = url.split("/")[-1].split("?")[0] or "clip.mp4"
    local_path = os.path.join(output_dir, filename)

    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        return local_path

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS)
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
            if os.path.getsize(local_path) == 0:
                raise IOError("Downloaded file is empty")
            return local_path
        except Exception as e:
            last_error = e
            if os.path.exists(local_path):
                os.remove(local_path)
            if attempt < MAX_RETRIES:
                time.sleep(1.5 * attempt)

    raise RuntimeError(f"Failed to download {url} after {MAX_RETRIES} attempts: {last_error}")
