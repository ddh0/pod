# Program that downloads all episodes of a podcast
# Features
# -- Functions: add, remove, update
# - Run the file to update without having to use python interpreter
# - Download all episodes of a podcast, put into the correct folder
# - Tag each file with metadata from the feed and the stored config

import os
import sys
import pickle
import requests
import datetime
import feedparser
import subprocess

STORAGE_DIR = "C:\\Users\\Dylan\\Python\\pod\\storage\\"
LOGFILE = "C:\\Users\\Dylan\\Python\\pod\\log.txt"
FFMPEG_PATH = "C:\\Users\\Dylan\\Python\\pod\\ffmpeg.exe"
TEMP_DIR = "C:\\Users\\Dylan\\AppData\\Local\\Temp\\"
debug = False
    

class Podcast:
    """For internal use. Class to hold attributes of a podcast."""
    def __init__(self, name: str, feed: str, storage_dir: str, prefix: str,
                 album: str, artist: str, year: str, art: str):
        self.name = name
        self.feed = feed
        self.storage_dir = storage_dir
        self.prefix = prefix
        self.album = album
        self.artist = artist
        self.year = year
        self.art = art


def log(text):
    """For internal use. Easily log events.
       To display these events onscreen as they occur, set pod.debug = True."""

    if debug: print("--debug: " + text)
    with open(LOGFILE, 'a') as log:
        log.write(datetime.datetime.now().isoformat() + ': ' + str(text) + '\n')


def add():
    """Creates a stored configuration file for the given feed, "*.pod", so that
       the feed can be checked quickly without having to specify the URL or metadata again."""
    
    podcast_obj = Podcast(
        input("Podcast name: "),
        input("Feed URL: "),
        input("Storage dir: "),
        input("Prefix: "),
        input("Album: "),
        input("Artist: "),
        input("Release year: "),
        input("Album art URL: ")
    )

    with open(STORAGE_DIR + podcast_obj.name + '.pod', 'wb') as file:
        pickle.dump(podcast_obj, file)


def remove():
    """Removes the configuration file associated with the given podcast."""
    name = input("Name of podcast to remove: ")

    if os.path.exists(STORAGE_DIR + name + '.pod'):
        os.remove(STORAGE_DIR + name + '.pod')

    else:
        print('-- %s does not exist' % name)


def update():
    """Checks for new entries from all feeds, download and tag new episodes."""
    # For each stored podcast config
    for file in os.listdir(STORAGE_DIR):
        with open(STORAGE_DIR + file, 'rb') as f:
            podcast_obj = pickle.load(f)
        
        log("Updating podcast: %s" % podcast_obj.name)
        print('Updating "%s":' % podcast_obj.name)

        # Get feed
        feed = feedparser.parse(podcast_obj.feed)
        length = len(feed.entries)

        # Create storage dir if it does not exist
        if not os.path.exists(podcast_obj.storage_dir):
            os.mkdir(podcast_obj.storage_dir)
        
        # Download image if it does not exist
        image_path = podcast_obj.storage_dir + podcast_obj.prefix + "_Album_Art.png"

        if not os.path.exists(image_path):
            print("Downloading podcast cover art...")
            log("Downloading image")
            response = requests.get(podcast_obj.art)
            with open(image_path, 'wb') as imgfile:
                imgfile.write(response.content)
        
        # Set podcast-specific metadata
        # image_path set above, title set per-episode
        album = podcast_obj.album
        artist = podcast_obj.artist
        year = podcast_obj.year

        # Get episodes from feed in chronological order
        for i in range(length-1, -1, -1):

            # Get current episode number
            ep_num = length - i
            display_prefix = podcast_obj.prefix + "_" + str(ep_num).zfill(3)
            
            # Get episode title
            title = feed.entries[i].title
             
            # Get episode URL
            episode_url = ""  # Variables for
            x = 0             # the while loop
            skip_this_item = False
            while ('.mp3' not in episode_url and 
                '.wav' not in episode_url and 
                '.m4a' not in episode_url): 
                try:
                    episode_url = feed.entries[i]['links'][x]['href']
                except:
                    skip_this_item = True
                    break
                log("episode_url: %s" % episode_url)
                x += 1

            if ".mp3" in episode_url:
                ext = ".mp3"
            if ".wav" in episode_url:
                ext = ".wav"
            if ".m4a" in episode_url:
                ext = ".m4a"

            # Get full episode destination path
            # xpath is the temporary file as it was downloaded with only the name changed
            # path is the final file
            xpath = TEMP_DIR + display_prefix + "X" + ext
            path = podcast_obj.storage_dir + display_prefix + ext

            # Skip this episode if already downloaded
            if os.path.exists(path):
                continue

            if skip_this_item:
                print(display_prefix + ": Skipped due to file extension (item likely not audio)")
                log(display_prefix + ": Skipped due to file extension (item likely not audio)")
                skip_this_item = False
                continue
            
            # Show which episode is in progress
            print(display_prefix + ': Downloading...')
            log('In progress: %s' % display_prefix)

            # Download episode
            HEADER_STRING = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36 Edg/87.0.664.66'}
            response = requests.get(episode_url, headers=HEADER_STRING)
            
            # Fail if size is less than 1MB
            if sys.getsizeof(response.content) < 1000000:  # If size is less than 1MB
                log("FATAL ERROR: response.content = %s bytes" % sys.getsizeof(response))
                raise IOError("-- response.content was only %s bytes" % sys.getsizeof(response.content))

            # Fail upon bad HTTP status code
            if not response.ok:
                log("FATAL ERROR: Bad response: status code %s" % response.status_code)
                raise ConnectionError("-- Response not ok, status code %s" % response.status_code)
            
            # Write mp3 data to file
            # Since this is done after the download is complete, interruptions will only break episodes
            # if they occur during the file being written to disk. If the script is interrupted during download,
            # the script will simply restart the download of the interrupted episode on the next run.
            with open(xpath, 'wb') as f:
                f.write(response.content)

            # Write correct metadata to clean file
            # Force using ID3v2.3 tags for best results
            # Only fatal errors will be displayed
            print(display_prefix + ": Writing correct metadata...")
            log("Writing metadata")
            subprocess.run([FFMPEG_PATH, "-i", xpath, "-i", image_path, "-map", "0:0", "-map", "1:0", "-codec", "copy",
                            "-id3v2_version", "3", "-metadata:s:v", 'title="Album cover"',"-metadata:s:v", 'comment="Cover (front)"',
                            "-metadata", "track=" + str(ep_num),
                            "-metadata", "title=" + title,
                            "-metadata", "album=" + album,
                            "-metadata", "album_artist=" + artist,
                            "-metadata", "artist=" + artist,
                            "-metadata", "year=" + year,
                            "-metadata", "genre=Podcast",
                            "-loglevel", "fatal", path])
            
            # Delete temporary file
            os.remove(xpath)

            log("Download complete: %s" % path)

        log("Update complete.")
        print("Files located in the following folder: %s" % podcast_obj.storage_dir)

if __name__ == '__main__':
    update()
