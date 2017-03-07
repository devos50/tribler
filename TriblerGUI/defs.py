"""
This file contains various definitions used by the Tribler GUI.
"""

API_PORT = 8085

# Define stacked widget page indices
PAGE_HOME = 0
PAGE_EDIT_CHANNEL = 1
PAGE_SEARCH_RESULTS = 2
PAGE_CHANNEL_DETAILS = 3
PAGE_SETTINGS = 4
PAGE_VIDEO_PLAYER = 5
PAGE_SUBSCRIBED_CHANNELS = 6
PAGE_DOWNLOADS = 7
PAGE_PLAYLIST_DETAILS = 8
PAGE_LOADING = 9
PAGE_DISCOVERING = 10
PAGE_DISCOVERED = 11
PAGE_TRUST = 12
PAGE_MARKET = 13
PAGE_MARKET_TRANSACTIONS = 14

PAGE_CHANNEL_CONTENT = 0
PAGE_CHANNEL_COMMENTS = 1
PAGE_CHANNEL_ACTIVITY = 2

PAGE_EDIT_CHANNEL_OVERVIEW = 0
PAGE_EDIT_CHANNEL_SETTINGS = 1
PAGE_EDIT_CHANNEL_TORRENTS = 2
PAGE_EDIT_CHANNEL_PLAYLISTS = 3
PAGE_EDIT_CHANNEL_RSS_FEEDS = 4
PAGE_EDIT_CHANNEL_PLAYLIST_EDIT = 5
PAGE_EDIT_CHANNEL_PLAYLIST_TORRENTS = 6
PAGE_EDIT_CHANNEL_PLAYLIST_MANAGE = 7
PAGE_EDIT_CHANNEL_CREATE_TORRENT = 8

PAGE_SETTINGS_GENERAL = 0
PAGE_SETTINGS_CONNECTION = 1
PAGE_SETTINGS_BANDWIDTH = 2
PAGE_SETTINGS_SEEDING = 3
PAGE_SETTINGS_ANONYMITY = 4

# Definition of the download statuses and the corresponding strings
DLSTATUS_ALLOCATING_DISKSPACE = 0
DLSTATUS_WAITING4HASHCHECK = 1
DLSTATUS_HASHCHECKING = 2
DLSTATUS_DOWNLOADING = 3
DLSTATUS_SEEDING = 4
DLSTATUS_STOPPED = 5
DLSTATUS_STOPPED_ON_ERROR = 6
DLSTATUS_METADATA = 7
DLSTATUS_CIRCUITS = 8

DLSTATUS_STRINGS = ["Allocating disk space", "Waiting for check", "Checking", "Downloading", "Seeding", "Stopped",
                    "Stopped on error", "Waiting for metadata", "Building circuits"]

# Definitions of the download filters. For each filter, it is specified which download statuses can be displayed.
DOWNLOADS_FILTER_ALL = 0
DOWNLOADS_FILTER_DOWNLOADING = 1
DOWNLOADS_FILTER_COMPLETED = 2
DOWNLOADS_FILTER_ACTIVE = 3
DOWNLOADS_FILTER_INACTIVE = 4

DOWNLOADS_FILTER_DEFINITION = {
    DOWNLOADS_FILTER_ALL: [DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_WAITING4HASHCHECK, DLSTATUS_HASHCHECKING,
                           DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR,
                           DLSTATUS_METADATA, DLSTATUS_CIRCUITS],
    DOWNLOADS_FILTER_DOWNLOADING: [DLSTATUS_DOWNLOADING],
    DOWNLOADS_FILTER_COMPLETED: [DLSTATUS_SEEDING],
    DOWNLOADS_FILTER_ACTIVE: [DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_WAITING4HASHCHECK, DLSTATUS_HASHCHECKING,
                              DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_METADATA, DLSTATUS_CIRCUITS],
    DOWNLOADS_FILTER_INACTIVE: [DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR]
}

BUTTON_TYPE_NORMAL = 0
BUTTON_TYPE_CONFIRM = 1

VIDEO_EXTS = ['aac', 'asf', 'avi', 'dv', 'divx', 'flac', 'flc', 'flv', 'mkv', 'mpeg', 'mpeg4', 'mpegts',
              'mpg4', 'mp3', 'mp4', 'mpg', 'mkv', 'mov', 'm4v', 'ogg', 'ogm', 'ogv', 'oga', 'ogx', 'qt',
              'rm', 'swf', 'ts', 'vob', 'wmv', 'wav', 'webm']

# Torrent health status
STATUS_GOOD = 0
STATUS_UNKNOWN = 1
STATUS_DEAD = 2
