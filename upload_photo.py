#!/usr/bin/python

import argparse
import http.client as httplib
import json
import os
import time

import httplib2
import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from flickr import fetch_photos

# Explicitly tell the underlying HTTP transport library not to retry, since
# we are handling retry logic ourselves.
httplib2.RETRIES = 1

# Maximum number of times to retry before giving up.
MAX_RETRIES = 10

# Always retry when these exceptions are raised.
RETRIABLE_EXCEPTIONS = (
    httplib2.HttpLib2Error,
    IOError,
    httplib.NotConnected,
    httplib.IncompleteRead,
    httplib.ImproperConnectionState,
    httplib.CannotSendRequest,
    httplib.CannotSendHeader,
    httplib.ResponseNotReady,
    httplib.BadStatusLine,
)

# Always retry when an apiclient.errors.HttpError with one of these status
# codes is raised.
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the {{ Google Cloud Console }} at
# {{ https://cloud.google.com/console }}.
# Please ensure that you have enabled the YouTube Data API for your project.
# For more information about using OAuth2 to access the YouTube Data API, see:
#   https://developers.google.com/youtube/v3/guides/authentication
# For more information about the client_secrets.json file format, see:
#   https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
CLIENT_SECRETS_FILE = os.environ['CLIENT_SECRETS_FILE']
SERVICE_ACCOUNT_FILE = os.environ['SERVICE_ACCOUNT_FILE']

# This OAuth 2.0 access scope allows an application to upload files to the
# authenticated user's YouTube channel, but doesn't allow other types of access.
SCOPES = ["https://www.googleapis.com/auth/photoslibrary"]
API_SERVICE_NAME = "photoslibrary"
API_VERSION = "v1"

VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")

MEDIA_FORMATS = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif"}

# Authorize the request and store authorization credentials.
def get_authenticated_service():
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    # credentials = flow.run_console()
    credentials = flow.run_local_server()
    return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)


def get_service_with_service_account():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    credentials.refresh(Request())
    return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)


def upload(photolib, photo_file, media_format):
    token = photolib._http.credentials.token
    url = "https://photoslibrary.googleapis.com/v1/uploads"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "X-Goog-Upload-Content-Type": f"image/{media_format}",
        "X-Goog-Upload-Protocol": "raw",
    }
    upload_token = requests.post(
        url, headers=headers, data=open(photo_file, "rb").read()
    ).text

    payload = json.dumps(
        {
            "newMediaItems": [
                {
                    "description": photo_file,
                    "simpleMediaItem": {
                        "fileName": photo_file,
                        "uploadToken": upload_token,
                    },
                }
            ]
        }
    )

    url = "https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, data=payload)

    # r = photolib.mediaItems().batchCreate(payload).execute()
    if r.ok:
        print(f"Upload response: {r}")
    else:
        if r.status_code == 429:
            raise ResourceWarning(r.text)
        elif r.status_code == 401:
            raise PermissionError(r.text)
        else:
            raise Exception(f"Failed to upload: {r.text}")


if __name__ == "__main__":
    photolib = get_authenticated_service()
    # photolib = get_service_with_service_account()
    delay = 5
    for photo_file in fetch_photos():
        if not os.path.isfile(photo_file):
            print(f"Skip invalid format: {photo_file}")
            continue

        media_format = MEDIA_FORMATS.get(photo_file.split(".")[-1])
        if media_format:
            retry_count = 0
            while retry_count < 10:
                try:
                    upload(photolib, photo_file, media_format)
                    # time.sleep(delay)
                    break
                except ResourceWarning as e:
                    print(f"Failed to upload photo (delay - {delay}): {e}")
                    time.sleep(61)
                    delay += 5
                    retry_count += 1
                except PermissionError as e:
                    print(f"Permission issue: {e}")
                    photolib._http.credentials.refresh(Request())

                    retry_count += 1
                except Exception as e:
                    print(f"Failed to upload photo (delay - {delay}): {e}")
                    time.sleep(61)
                    retry_count += 1

            try:
                os.remove(photo_file)
            except Exception as e:
                pass
        else:
            raise Exception(f"Unsupported media format: {photo_file}")
