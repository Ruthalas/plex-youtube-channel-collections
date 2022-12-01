# plex-youtube-channel-collections
Generate unique collections for each youtube channel folder stored locally

#youtubearchive
When archiving youtube videos, It's difficult to have a proper UI experience to watch the youtube videos and channels that we've archived.
This project aims to utilize tools available in Plex to make a usable watching experience for Youtube channels archived utilizing yt-dlp.

## Environment Setup
- Install the requirements.txt with `py -m pip install -r requirements.txt` located in this project.
- Written and tested with python 3.10.x and 3.11.x
- I enforce black formatter :D -> Install "Black Formatter" in the VSCode Market
- Fill out the required environment variables in the vscode [launch.json](https://github.com/KJBurnett/plex-youtube-channel-collections/blob/main/.vscode/launch.json)  


Example Configuration:
```
        {
            "name": "[LOCAL SERVER] main script run",
            "type": "python",
            "request": "launch",
            "program": "main.py",
            "console": "integratedTerminal",
            "justMyCode": true,
            "env": {
                "PLEX_URL": "https://localhost:32400",
                "PLEX_TOKEN": "<Insert-Plex-Token>",
                "YOUTUBE_PATH": "J:\\Youtube",
                "YOUTUBE_LIBRARY_NAME": "Youtube",
                "MEDIA_TYPE": "movie",
                "YOUTUBE_VIDEO_EXTENSION": ".mkv",
                "SECONDS_TO_WAIT": "3600",
                "PYTHONWARNINGS": "ignore:Unverified HTTPS request",
                "OPTIMIZE_SCANS": "true"
            }
        }
```


## Creating a local Youtube Library
- This project heavily relies on code from the [yt-dlp project](https://github.com/yt-dlp/yt-dlp)
- FFMPEG, and Plex
- Download the latest [yt-dlp](https://github.com/yt-dlp/yt-dlp#installation)
- Place the exe in your youtube library folder Example: Z:\Youtube
- Place the [config.conf](https://github.com/KJBurnett/plex-youtube-channel-collections/blob/main/config.conf) in Z:\Youtube, and ensure the commands point to your new youtube folder Z:\Youtube  
```
--batch-file "Z:\Youtube\channel_list.txt"  
--download-archive "Z:\Youtube\downloaded.txt"  
--output "Z:\Youtube\%(uploader)s [%(channel_id)s]/%(upload_date)s - %(title)s - (%(duration)ss) [%(id)s].%(ext)s"  
--ffmpeg-location "Z:\Youtube\ffmpeg\bin"  
Note: These configurations are very extensive. If you want to speed up downloads, disable --get-comments. 
```
- Create a channel_list.txt file with a list of youtube channel urls you want to download
- Run `Z:\Youtube\yt-dlp.exe --config-location "J:\Youtube\config.conf"`

### After Downloading The Youtube Channels
- Ensure you have a Plex Server running, and create a dedicated library named "Youtube" and point the library to Z:\Youtube
- After Plex has finished scanning the videos, the library will disorganized
- Run [main.py](https://github.com/KJBurnett/plex-youtube-channel-collections/blob/main/main.py)  
This can take some time as the script pings your PlexServer for every video metadata in your Z:\Youtube library.  
Once completed, you should be able to find under the [Collections](https://support.plex.tv/articles/201273953-collections/) tab a collection for every youtube channel in the library.
Additionally, you will find the video files's `modified date` property to be changed to match the original Youtube video upload date.


## TODO
- ✅ Optimize youtube channel scans. Currently we check the PlexServer for every single video in a channel folder. Even if the video was already added to the collection. Idea: After successfully parsing and adding videos to a Plex Collection, serialize the list and store it as a txt file in each respective channel. We can read in thefile every time the script runs so we only scan for new youtube video additions to the channel folder.
- Add more error retry checks. Currently the script will keep going if a video fails. But we should produce a log file of all of the video files it failed to load into Plex. Historically this is usually due to some weird special character in the youtubeVideo's file name.
- Create in-depth documentation for utilizing yt-dlp in conjunction with this script. The video files must be organized and titled correctly or this script will not work.
