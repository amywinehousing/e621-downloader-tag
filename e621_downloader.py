#!/usr/bin/env python3
import argparse
import os
import sys
import time
import requests

BASE_URL   = "https://e621.net"
USER_AGENT = "e621Downloader/1.0 (by anonymous)"
PAGE_LIMIT = 320

def build_session(username: str = "", api_key: str = "") -> requests.Session:
    """Return a requests Session pre-configured for e621."""
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    if username and api_key:
        s.auth = (username, api_key)
    return s


def fetch_posts(session: requests.Session, tags: str,
                page: int = 1, limit: int = PAGE_LIMIT) -> list[dict]:
    params = {
        "tags":  tags,
        "page":  page,
        "limit": min(limit, PAGE_LIMIT),
    }
    url = f"{BASE_URL}/posts.json"
    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("posts", [])


def collect_posts(session: requests.Session, tags: str,
                  count: int) -> list[dict]:
    collected = []
    page = 1

    while len(collected) < count:
        needed   = count - len(collected)
        limit    = min(needed, PAGE_LIMIT)

        print(f"  Fetching page {page} (need {needed} more)…")
        posts = fetch_posts(session, tags, page=page, limit=limit)

        if not posts:
            print("  No more posts available.")
            break

        collected.extend(posts)
        page += 1
        time.sleep(0.5)

    return collected[:count]

TAG_CATEGORY_ORDER = [
    "artist",
    "copyright",
    "character",
    "species",
    "general",
    "meta",
    "lore",
    "invalid",
]

def format_tags(post: dict) -> str:
    tag_groups = post.get("tags", {})
    all_tags: list[str] = []
    for category in TAG_CATEGORY_ORDER:
        all_tags.extend(tag_groups.get(category, []))
    for category, tags in tag_groups.items():
        if category not in TAG_CATEGORY_ORDER:
            all_tags.extend(tags)
    return ", ".join(all_tags)

def download_image(session: requests.Session, url: str,
                   dest_path: str) -> bool:
    try:
        resp = session.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except requests.RequestException as exc:
        print(f"    ✗ Download failed: {exc}")
        return False


def save_tags(tags: str, dest_path: str) -> None:
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(tags)

def run(tags: str, count: int, output_dir: str,
        username: str = "", api_key: str = "") -> None:

    os.makedirs(output_dir, exist_ok=True)

    print(f"\ne621 Downloader")
    print(f"  Tags      : {tags}")
    print(f"  Count     : {count}")
    print(f"  Output    : {os.path.abspath(output_dir)}")
    if username:
        print(f"  User      : {username}")
    print()

    session = build_session(username, api_key)

    print("Collecting posts…")
    posts = collect_posts(session, tags, count)
    print(f"Found {len(posts)} post(s).\n")

    if not posts:
        print("Nothing to download. Check your tags or credentials.")
        sys.exit(1)

    downloaded = 0
    for idx, post in enumerate(posts, start=1):
        file_info = post.get("file", {})
        image_url = file_info.get("url")

        if not image_url:
            print(f"[{idx}/{len(posts)}] Skipping post {post.get('id')} — no file URL (deleted/unavailable).")
            continue

        ext = image_url.rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "gif", "webm", "mp4"):
            ext = "jpg"   # safe fallback

        img_path = os.path.join(output_dir, f"{downloaded + 1}.{ext}")
        txt_path = os.path.join(output_dir, f"{downloaded + 1}.txt")

        print(f"[{idx}/{len(posts)}] Downloading post {post.get('id')} → {os.path.basename(img_path)} …", end=" ", flush=True)

        if download_image(session, image_url, img_path):
            tag_string = format_tags(post)
            save_tags(tag_string, txt_path)
            print("✓")
            downloaded += 1
        else:
            pass

        time.sleep(0.5)

    print(f"\nDone! {downloaded} image(s) saved to: {os.path.abspath(output_dir)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download images from e621 with numbered filenames and tag .txt files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python e621_downloader.py --tags "nepentz -rating:s -female" --count 50
  python e621_downloader.py --tags "nepentz order:score" --count 100 --output ./art
  python e621_downloader.py --tags "canine solo" --count 25 --user myname --key abc123

Tag syntax:
  artist_name          search by artist
  -tag                 exclude posts with this tag
  -rating:s            exclude safe-rated posts
  -rating:e            exclude explicit posts
  order:score          sort by score (default: newest first)
  order:favcount       sort by favourite count

Notes:
  • e621 requires a User-Agent — this script sets one automatically.
  • For 18+ content you MUST supply --user and --key (your e621 API key).
    Without credentials only safe-rated posts are accessible.
  • API keys can be generated at: https://e621.net/users/home → API Key
        """,
    )

    parser.add_argument(
        "--tags", "-t", required=True,
        help="Space-separated tag string (wrap in quotes). Use - to exclude tags.",
    )
    parser.add_argument(
        "--count", "-n", type=int, default=50,
        help="Number of images to download (default: 50).",
    )
    parser.add_argument(
        "--output", "-o", default="./e621_downloads",
        help="Output directory (default: ./e621_downloads).",
    )
    parser.add_argument(
        "--user", "-u", default="",
        help="Your e621 username (required for non-safe content).",
    )
    parser.add_argument(
        "--key", "-k", default="",
        help="Your e621 API key (required for non-safe content).",
    )

    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count must be at least 1.")

    run(
        tags       = args.tags,
        count      = args.count,
        output_dir = args.output,
        username   = args.user,
        api_key    = args.key,
    )


if __name__ == "__main__":
    main()
