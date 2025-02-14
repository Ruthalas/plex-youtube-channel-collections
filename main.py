# 11/25/2022
# Kyler Burnett

import json
import os
import sys
from plexapi.server import PlexServer
from plexapi.video import Movie
from plexapi.collection import Collection
import requests
import time
import math
from datetime import datetime
import re

# Internal modules
import avatarProcessor
from config import Config
import utils


def setDatesFromTitles(videoObjects: list[Movie], channelFolder: str) -> list[Movie]:
    for videoObject in videoObjects:
        videoObject.originallyAvailableAt = getDateFromTitle(videoObject.title)
        videoPath = f"{os.path.join(channelFolder, videoObject.title)}.mkv"
        modTime = time.mktime(getDateFromTitle(videoObject.title).timetuple())
        if os.path.isfile(videoPath):
            # Ensure the file exists. Sometimes the file gets modified during scanning process and is modified or removed.
            # If the video file exists, updat the "Modified Date" metadata to match the actual uploaded-to-youtube-datetime which is parsed from the title from yt-dlp.
            os.utime(
                videoPath,
                (modTime, modTime),
            )
    return videoObjects


# Expected file name format: "20120727 - Ferrari Dino 246 GTS - (81s) [qZbpzYNEziY]"
# Split by first whitespace to get the date string.
# Then, parse the year, month, and day out of the singular no-space string.
# returns a datetime object, as required by plexapi.video.originallyAvailableAt
def getDateFromTitle(title: str) -> datetime:
    try:
        date = title.split(" ")[0]
        year = int(date[:4])
        month = int(date[4:6])
        day = int(date[6:8])
    except:
        year = 1970
        month = 1
        day = 1
    return datetime(year, month, day)


# Get a list of videos from the channelFolder by finding all files with the YOUTUBE_VIDEO_EXTENSION
# strip the video of its extension, and remove the filepath. Plex only needs the file name.
# Example:
# Before: "Z:\Youtube\TheStradman [UC21Kozr_K0yDM-VjoihG9Aw]\20120727 - Ferrari Dino 246 GTS - (81s) [qZbpzYNEziY].mkv"
# After: "20120727 - Ferrari Dino 246 GTS - (81s) [qZbpzYNEziY]"
def getVideosFromChannelFolder(channelFolder: str, optimizeScans: bool) -> list[str]:
    videos = [
        os.path.basename(video.replace(".mkv", ""))
        for video in utils.getFileNamesFromDirectory(channelFolder)
        # Ensure the extension is .mkv, but also ensure the video is not still "in progress" wtih ffmpeg.
        if video.endswith(".mkv") and not video.endswith(".temp.mkv")
    ]
    if optimizeScans:
        videos = filterAlreadyScannedVideos(videos, channelFolder)
    return videos


def filterAlreadyScannedVideos(videos: list[str], channelFolder: str) -> list[str]:
    scannedVideosPath = os.path.join(channelFolder, "scannedVideos.txt")
    if os.path.isfile(scannedVideosPath):
        # If optimizeScans=True and the scannedvideos.txt exists
        # then we need to check if any videos exist in the scannedVideos log.
        scannedVideos = getScannedVideos(scannedVideosPath)
        newVideos = list(filter(lambda video: isNewVideo(video, scannedVideos), videos))
        return newVideos
    return videos


# If the video guid is found in scannedVideos, then we've already scanned this
# video before. Don't include it in our run.
def isNewVideo(video: str, scannedVideos: list[str]) -> bool:
    if utils.getGuidFromTitle(video) in scannedVideos:
        print(f"{video} already scanned into Plex, skipping.")
        return False
    return True


def getScannedVideos(scannedVideosPath: str) -> list[str]:
    scannedVideos = []
    with open(scannedVideosPath) as videosFile:
        for line in videosFile:
            scannedVideos.append(line.rstrip("\n"))
    return scannedVideos


# Ensure we're looking at specifically Youtube Channel Folders.
# We determine this by ensuring there is a unique guid at the end of the folder name.
# Example:
# A valid channel folder: TheStradman [UC21Kozr_K0yDM-VjoihG9Aw]
# An invalid channel folder: TheStradman
# A channelFolder is the full filePath. Example: 'J:\\Youtube\\100 Percent Zelda [UC4It_xPxQyCpyTJshlAQSgA]'
def getValidChannelFolders(youtubePath: str) -> list[str]:
    # Use list comprehension to ensure the folders are full file paths.
    # os.listdir() only returns the folder/filenames. Not full path.
    folders = [os.path.join(youtubePath, folder) for folder in os.listdir(youtubePath)]
    validFolders = filter(
        lambda folder: "[" in folder and folder.endswith("]"), folders
    )
    # Note filter is an iterable, so we need to convert it back into a list.
    return list(validFolders)


# Search the Plex database for plex video objects of the youtube videos.
# We have to search the Plex database for every single video file name, and retrieve its Plex library object.
def findYoutubeVideosInPlex(
    plex: PlexServer, channelVideos: list[str], mediaType: str, youtubeLibrary: str
) -> list[Movie]:
    plexVideoObjects = []

    counter = 1
    for video in channelVideos:
        # Find existence of video in the plex library.
        print(f"[{counter}/{len(channelVideos)}] Searching for {video}")
        counter += 1
        videoObject = searchPlexForVideo(plex, video, mediaType, youtubeLibrary)
        if videoObject:
            plexVideoObjects.append(videoObject[0])
            print("Video found in Plex!")
        else:
            print("Error. Video was not found in Plex.")
        if counter % 100 == 0:
            # Wait for 30 seconds to reduce load on the plexapi
            print("Sleeping for 30 seconds every 100th query to reduce plexapi load.")
            time.sleep(30)
    return plexVideoObjects


def searchPlexForVideo(
    plex: PlexServer, video: str, mediaType: str, youtubeLibrary: str
):
    maxRetries = 7
    attempt = 1
    waitInSeconds = 30
    querySucess = False
    videoObject = None
    while attempt <= maxRetries and not querySucess:
        try:
            videoObject = plex.search(
                video, mediatype=mediaType, sectionId=youtubeLibrary
            )
            querySucess = True
        except Exception as e:
            print(f"\n Caught Exception: {e}")
            print(
                f"Error. The Plex server likely timed out from too many requests. Waiting for {waitInSeconds} seconds before trying again.\nAttempt {attempt}/{maxRetries} failed."
            )
            attempt += 1
            time.sleep(waitInSeconds)
            waitInSeconds = (
                waitInSeconds * 2
            )  # Increase the wait time if we have to wait again.
    return videoObject


def addVideosToPlexCollection(
    plex: PlexServer, videoObjects, youtubeLibrary: str, channelName: str
) -> Collection:
    # Check to see if the collection already exists.
    collectionResults = plex.search(
        channelName, mediatype="collection", sectionId=youtubeLibrary
    )

    if collectionResults:
        collection = collectionResults[0]
        collection.addItems(videoObjects)
        collection.sortUpdate(sort="custom")
        return collection
    else:
        print(f"The collection does not exist. Creating a collection for {channelName}")
        collection = plex.createCollection(
            title=channelName, section=youtubeLibrary, items=videoObjects, sort="custom"
        )
        return collection


def getRequiredVariables() -> dict[str, str]:
    return {
        "YOUTUBE_LIBRARY_NAME": "The name of your Youtube library in Plex. eg: 'Youtube'",
        "YOUTUBE_VIDEO_EXTENSION": "The file extension of your Youtube videos. eg: '.mkv'",
        "MEDIA_TYPE": "The type of media your Youtube videos are classified as in Plex. eg: 'movie'",
        "PLEX_URL": "the url of your plex server. eg: 'https://192.168.1.25:32400'",
        "PLEX_TOKEN": "The token required to access your plex api. See https://tinyurl.com/get-plex-token",
        "YOUTUBE_PATH": "The filepath to your Youtube library. eg: 'Z:\\Youtube'",
    }


def getOptionalVariables() -> dict[str, str]:
    return {
        "OPTIMIZE_SCAN": "Optional 'true' or 'false'. If true, successfully scanned files will be added to a 'plex-scanned.json' and will be skipped during runtime."
    }


# Error checking for initial startup of the script.
# We require these environment variables to ensure a smooth and successful run.
def environmentVariableError(missingVariable: str) -> None:
    requiredVariables = getRequiredVariables()
    errorMessage = f"\nError. Missing environment variable '{missingVariable}'. You must supply all required environment variables.\n\nRequired Environment Variables:{json.dumps(requiredVariables, indent=4, separators=(',', ': '))}"
    print(errorMessage)
    sys.exit()


def saveVideosToScannedVideosLog(channelVideos: list[str], channelFolder: str) -> None:
    scannedVideosPath = os.path.join(channelFolder, "scannedVideos.txt")
    scannedVideos = []
    if os.path.isfile(scannedVideosPath):
        scannedVideos = getScannedVideos(scannedVideosPath)
        [
            scannedVideos.append(utils.getGuidFromTitle(channelVideo))
            for channelVideo in channelVideos
            if utils.getGuidFromTitle(channelVideo) not in scannedVideos
        ]
    else:
        scannedVideos = channelVideos

    with open(scannedVideosPath, "w") as f:
        for video in scannedVideos:
            f.write(f"{utils.getGuidFromTitle(video)}\n")


def loadArguments(configFilePath: str) -> Config:
    with open(configFilePath) as configFile:
        configJson = json.load(configFile)

    config = Config(
        configJson["YOUTUBE_LIBRARY_NAME"],
        configJson["YOUTUBE_VIDEO_EXTENSION"],
        configJson["MEDIA_TYPE"],
        configJson["PLEX_URL"],
        configJson["PLEX_TOKEN"],
        configJson["YOUTUBE_PATH"],
        configJson["OPTIMIZE_SCANS"],
        configJson["YTDLP_PROCESS_PATH"],
        configJson["DOWNLOAD_AVATARS_AND_BANNERS"],
    )
    print(f"Loading config file from {configFilePath} was successful.")
    return config


def loadEnvironmentVariables():
    # Ensure the environment variables exist. Otherwise throw an error and quit.
    youtubeLibrary = os.environ.get("YOUTUBE_LIBRARY_NAME")
    if not youtubeLibrary:
        environmentVariableError("YOUTUBE_LIBRARY_NAME")
        sys.exit()
    extension = os.environ.get("YOUTUBE_VIDEO_EXTENSION")
    if not extension:
        environmentVariableError("YOUTUBE_VIDEO_EXTENSION")
        sys.exit()
    mediaType = os.environ.get("MEDIA_TYPE")
    if not mediaType:
        environmentVariableError("MEDIA_TYPE")
        sys.exit()
    baseurl = os.environ.get("PLEX_URL")
    if not baseurl:
        environmentVariableError("PLEX_URL")
        sys.exit()
    token = os.environ.get("PLEX_TOKEN")
    if not token:
        environmentVariableError("PLEX_TOKEN")
        sys.exit()
    youtubePath = os.environ.get("YOUTUBE_PATH")
    if not youtubePath:
        environmentVariableError("YOUTUBE_PATH")
        sys.exit()
    optimizeScans = os.environ.get("OPTIMIZE_SCANS")
    optimizeScans = True if optimizeScans == "true" else False
    ytdlpProcessPath = os.environ.get("YTDLP_PROCESS_PATH")
    # Only download avatars and banners if the ytdlpProcessPath environment variable exists.
    downloadAvatarsAndBanners = (
        os.environ.get("DOWNLOAD_AVATARS_AND_BANNERS") if ytdlpProcessPath else False
    )
    downloadAvatarsAndBanners = True if downloadAvatarsAndBanners == "true" else False

    config = Config(
        youtubeLibrary,
        extension,
        mediaType,
        baseurl,
        token,
        youtubePath,
        optimizeScans,
        ytdlpProcessPath,
        downloadAvatarsAndBanners,
    )

    print("All environment variables successfully loaded.\n")

    return config


def run():

    configFilePath = None
    if len(sys.argv) > 1:
        configFilePath = sys.argv[1]
    config = None

    if configFilePath is not None and configFilePath.endswith("json"):
        config = loadArguments(configFilePath)
    else:
        config = loadEnvironmentVariables()

    # Start a PlexServer API session.
    session = requests.Session()
    session.verify = False
    plex = PlexServer(config.baseurl, config.token, session)

    # ===== Let's get to work ===== #
    validChannelFolders = getValidChannelFolders(config.youtubePath)
    print(f"Found {len(validChannelFolders)} channel(s) to sync.\n")

    startTime = time.time()
    library = plex.library.section(config.youtubeLibrary)
    # Large operation but only needs to be done once (13,000 files took about 38 seconds).
    print(
        f"Getting all youtube videos from library '{config.youtubeLibrary}'. This can take up to a minute."
    )
    allYoutubeVideos = library.all()
    print(
        f"Found: {len(allYoutubeVideos)} videos in Plex library '{config.youtubeLibrary}!\nTook {math.trunc(time.time() - startTime)} seconds to complete.\n"
    )

    for channelFolder in validChannelFolders:
        channelName = utils.getChannelNameFromFolder(channelFolder=channelFolder)

        channelSpecificVideos = [
            video
            for video in allYoutubeVideos
            if channelName in video.locations[0]
            and video.locations[0].endswith("mkv")
        ]

        if len(channelSpecificVideos) > 0:
            # # This sorts the videos in Descending order.
            # # Mimicking Youtube's video listing, most recent to oldest.
            channelSpecificVideos.sort(key=lambda video: video.title, reverse=True)

            # # We must parse the date out of the youtube video title and apply it to the plex object
            # # otherwise, we won't be able to properly sort by release date.
            channelSpecificVideos = setDatesFromTitles(
                channelSpecificVideos, channelFolder
            )

            print(
                f"Adding {len(channelSpecificVideos)} videos to collection '{channelName}..."
            )
            startTime = time.time()
            collection = addVideosToPlexCollection(
                plex, channelSpecificVideos, config.youtubeLibrary, channelName
            )
            print(f"Took {math.trunc(time.time() - startTime)} seconds to complete.")

            if config.downloadAvatarsAndBanners and config.ytdlpProcessPath:
                downloadSuccess = avatarProcessor.getChannelAvatarsAndBanners(
                    channelFolder, config.ytdlpProcessPath
                )
                # Only attempt to set the plex collection poster if the avatar downloader
                # above successfully completed.
                # If you want to reset your collection posters, delete the images/ folder in the
                # youtubeChannel directory.
                if downloadSuccess and collection is not None:
                    avatarProcessor.setPlexCollectionPoster(
                        collection, channelName, channelFolder, config.youtubeLibrary
                    )

        print(f"Channel videos successfully added to Collection in Plex!\n")


if __name__ == "__main__":
    # Initialize runtime timer. So we can see how long it takes the script to run at the end.
    startTime = time.time()

    # Run the tool.
    runtimeResult = run()

    # Completion, cleanup.
    totalTime = time.time() - startTime
    print(
        f"\nCollections creation completed. Total run time: {math.trunc(totalTime)} seconds."
    )

    # Cool TRON reference.
    print("\nEnd of Line.")
