import glob
import unicodedata
import os
import converter
import uploader
import re
from uploader import *
from inflection import titleize


def normalize_caseless(text):
    return unicodedata.normalize("NFKD", text.casefold())


def caseless_equal(left, right):
    return normalize_caseless(left) == normalize_caseless(right)


def create_and_upload_video(audio_file, options, folder_name, playlist_title):
    # base_filename = splitext(basename(audio_file))[0]
    video_name = folder_name + '.mp4'
    youtube_video_name = titleize(folder_name)
    saved_temp_video = converter.convert_to_mp4(audio_file=audio_file, name=video_name, image_file=options.imageFile)
    uploaded_video_id = uploader.initialize_upload(youtube, playstlist_title= playlist_title,
                                                   file_name=saved_temp_video, category=options.category,
                                                   privacy_status=options.privacyStatus, keywords=options.keywords,
                                                   title=youtube_video_name)
    os.remove(saved_temp_video)
    return uploaded_video_id


def to_be_skipped(folder_name, to_skip):
    folder_number = re.search(r'\d+', folder_name).group()
    if folder_name is None:
        print('Sorry this %s folder is being skipped because it doesn''t have a prefix number'%folder_name)
        return True
    return folder_number in to_skip


def get_upload_name(folder_name):
    parts = folder_name.split('-',1)
    if len(parts) != 2:
        print('Sorry this folder name %s couldn''t be split properly. So using the number instead'%folder_name)
        return parts[0]
    else:
        return parts[1]


if __name__ == '__main__':
    argparser.add_argument("--folder", required=True, help="Path of the root directory")
    argparser.add_argument("--playlistTitle",
                           help="Name of your playlist in Youtube. It will be created if it does not exist")
    argparser.add_argument("--imageFile", default=None, help="Path to the image to be used in the video")
    argparser.add_argument("--category", default="10", help="Numeric video category. If its a music video use 10")
    argparser.add_argument("--keywords", help="Video keywords, comma separated", default="")
    argparser.add_argument("--privacyStatus", choices=VALID_PRIVACY_STATUSES, default=VALID_PRIVACY_STATUSES[0],
                           help="Video privacy status.")
    argparser.add_argument("--clientFile", default="client_secret.json",
                           help="Location of the client secret file. See https://developers.google.com/api-client-library/python/auth/web-app")
    argparser.add_argument("--skipFolderRange", default=None,
                           help="Specify the range of folders to skip. Ex: 1..10 or 1,2,4 or abc,cdef,1..100")
    argparser.add_argument("--startingFolderNumber", default=None,
                           help="Specify the folder number to start from. Ex. 1")
    argparser.add_argument("--uploadAllFiles", default=True,
                           help="Should the script consider to upload all the files inside a folder or consider only the latest one. Defaults to all files.")
    args = argparser.parse_args()

    folders_to_skip = []
    if args.skipFolderRange:
        uniques = args.skipFolderRange.split(",")
        for unique in uniques:
            if ".." in unique:
                start_end = unique.split("..")
                folders_to_skip.extend(str(x) for x in range(int(start_end[0]), int(start_end[1]) + 1))
            else:
                folders_to_skip.append(unique)

    if args.startingFolderNumber:
        folders_to_skip.extend(str(x) for x in range(int(args.startingFolderNumber)))

    if not os.path.exists(args.folder):
        exit("Please specify a valid file using the --folder= parameter.")

    path = os.path.abspath(args.folder)
    # This is the parent folder. This will be used as the name of the playlist
    playlist_title = os.path.basename(path)
    if args.playlistTitle:
        playlist_title = args.playlistTitle

    youtube = get_authenticated_service(args)

    folders = next(os.walk(path))[1]

    for folder in folders:
        if to_be_skipped(folder, folders_to_skip):
            print('Skipping folder ' + folder + '\n')
            continue

        file_name_to_upload = get_upload_name(folder)

        if not args.uploadAllFiles:
            file = max(files_in_folder=glob.glob(path + '/' + folder + '/*.mp3'), key=os.path.getctime)
            create_and_upload_video(file, args, file_name_to_upload, playlist_title)
        else:
            files_in_folder = glob.glob(path + '/' + folder + '/*.mp3')
            for file in files_in_folder:
                create_and_upload_video(file, args, file_name_to_upload, playlist_title)
