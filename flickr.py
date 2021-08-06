import os
import time
from datetime import datetime

import flickr_api
import yaml

BATCH_SIZE = 25


def load_status():
    with open("status.yaml") as file:
        return yaml.full_load(file)


def write_status(status):
    with open("status.yaml", "w") as file:
        return yaml.dump(status, file)


def fetch_photos():
    flickr_api.set_keys(
        api_key=os.environ["API_KEY"], api_secret=os.environ["API_SECRET"]
    )
    flickr_api.set_auth_handler("token")

    status = load_status()
    while True:
        print(f"Current status: {status}")
        last_page = status["last_page"]
        last_posted = (
            0 if status["last_posted"] is None else status["last_posted"].timestamp()
        )
        photos = flickr_api.Photo.search(
            user_id="me",
            sort="date-posted-asc",
            per_page=BATCH_SIZE,
            page=last_page + 1,
        )
        print(f"Fetched next batch of photos: {photos.info}")
        if len(photos.data) < BATCH_SIZE:
            print(f"We processed all photos !!!")
            break

        try:
            for photo in photos.data:
                if photo.posted < last_posted:
                    print(f"Skip already processed file: {photo.title}")
                    continue

                if photo.media == "photo":
                    print(f"Skip photo file: {photo.title}")
                    continue

                last_posted = photo.posted
                retry_count = 0
                while retry_count < 3:
                    try:
                        fn = photo.save(f"flickr_{photo.id}", size_label="Original")
                        break
                    except Exception as e:
                        print(f"Failed to download photo {photo.id}: {e}")
                        time.sleep(3)
                        retry_count += 1

                yield f"flickr_{photo.id}"
                # yield f"flickr_{photo.id}.{photo.originalformat}"
            status["last_page"] = last_page + 1
            status["last_posted"] = datetime.fromtimestamp(last_posted)
        finally:
            write_status(status)
