import http.client
import httplib2
import random
import sys
import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

# Explicitly tell the underlying HTTP transport library not to retry, since
# we are handling retry logic ourselves.
httplib2.RETRIES = 1

# Maximum number of times to retry before giving up.
MAX_RETRIES = 10

# Always retry when these exceptions are raised.
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, http.client.NotConnected,
                        http.client.IncompleteRead, http.client.ImproperConnectionState,
                        http.client.CannotSendRequest, http.client.CannotSendHeader,
                        http.client.ResponseNotReady, http.client.BadStatusLine)

# Always retry when an apiclient.errors.HttpError with one of these status
# codes is raised.
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

# This OAuth 2.0 access scope allows an application to upload files to the
# authenticated user's YouTube channel, but doesn't allow other types of access.
YOUTUBE_READ_WRITE_SCOPE = "https://www.googleapis.com/auth/youtube"
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")


def get_authenticated_service(args):
    flow = flow_from_clientsecrets(args.clientFile,
                                   scope=YOUTUBE_READ_WRITE_SCOPE)

    storage = Storage("%s-oauth2.json" % sys.argv[0])
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        credentials = run_flow(flow, storage, args)

    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                 http=credentials.authorize(httplib2.Http()))


# This method implements an exponential backoff strategy to resume a
# failed upload.
def resumable_upload(insert_request):
    response = None
    error = None
    retry = 0
    while response is None:
        try:
            print("Uploading file...")
            status, response = insert_request.next_chunk()
            if 'id' in response:
                print("Video id '%s' was successfully uploaded." % response['id'])
                return response['id']
            else:
                exit("The upload failed with an unexpected response: %s" % response)
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = "A retriable HTTP error %d occurred:\n%s" % (e.resp.status,
                                                                     e.content)
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = "A retriable error occurred: %s" % e

        if error is not None:
            print(error)
            retry += 1
            if retry > MAX_RETRIES:
                exit("No longer attempting to retry.")

            max_sleep = 2 ** retry
            sleep_seconds = random.random() * max_sleep
            print("Sleeping %f seconds and then retrying..." % sleep_seconds)
            time.sleep(sleep_seconds)


def get_playlist_id(youtube, playlist_title=None):
    playlists = youtube.playlists().list(
        part="snippet",
        mine=True
    ).execute()
    playlist_to_use = None
    if playlist_title:
        for playlist in playlists['items']:
            if playlist['snippet']['title'].lower() == playlist_title.lower():
                playlist_to_use = playlist['id']
                break

        # We could not find a suitable playlist. Going to create one
        if not playlist_to_use:
            playlist_response = youtube.playlists().insert(
                part="snippet,status",
                body=dict(
                    snippet=dict(
                        title=playlist_title,
                        description="A private playlist created with the YouTube MP3 Uploader"
                    ),
                    status=dict(
                        privacyStatus="private"
                    )
                )
            ).execute()
            playlist_to_use = playlist_response['id']
    return playlist_to_use


def add_to_playlist(youtube, video_id, playlist_title=None):
    playlist_id = get_playlist_id(youtube, playlist_title)
    if playlist_id:
        playlist_item_response = youtube.playlistItems().insert(
            part="snippet,status",
            body=dict(
                snippet=dict(
                    playlistId=playlist_id,
                    resourceId=dict(
                        videoId=video_id,
                        kind="youtube#video"
                    )
                )
            )

        ).execute()
        print('Succesfully added ' + video_id + ' to playlist ' + playlist_title)
        return playlist_item_response


def initialize_upload(youtube, file_name, category, privacy_status, playstlist_title=None, keywords="",
                      title="Test Title", description="Test Description"):
    tags = None
    if keywords:
        tags = keywords.split(",")

    body = dict(
        snippet=dict(
            title=title,
            description=description,
            tags=tags,
            categoryId=category,
        ),
        status=dict(
            privacyStatus=privacy_status
        )
    )

    # Call the API's videos.insert method to create and upload the video.
    insert_request = youtube.videos().insert(
        part=",".join(list(body.keys())),
        body=body,
        # The chunksize parameter specifies the size of each chunk of data, in
        # bytes, that will be uploaded at a time. Set a higher value for
        # reliable connections as fewer chunks lead to faster uploads. Set a lower
        # value for better recovery on less reliable connections.
        #
        # Setting "chunksize" equal to -1 in the code below means that the entire
        # file will be uploaded in a single HTTP request. (If the upload fails,
        # it will still be retried where it left off.) This is usually a best
        # practice, but if you're using Python older than 2.6 or if you're
        # running on App Engine, you should set the chunksize to something like
        # 1024 * 1024 (1 megabyte).
        media_body=MediaFileUpload(file_name, chunksize=-1, resumable=True)
    )

    video_id = resumable_upload(insert_request)
    add_to_playlist(youtube=youtube, playlist_title=playstlist_title, video_id=video_id)
