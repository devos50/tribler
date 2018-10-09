import os
from datetime import datetime

from libtorrent import file_storage, add_files, create_torrent, set_piece_hashes, bencode, torrent_info
from pony import orm
from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.serialization import MetadataTypes, ChannelMetadataPayload
from Tribler.Core.exceptions import DuplicateTorrentFileError, DuplicateChannelNameError

CHANNEL_DIR_NAME_LENGTH = 60  # Its not 40 so it could be distinguished from infohash
BLOB_EXTENSION = '.mdblob'


def create_torrent_from_dir(directory, torrent_filename):
    fs = file_storage()
    add_files(fs, directory)
    t = create_torrent(fs)
    # For a torrent created with flags=19 with 200+ small files
    # libtorrent client_test can't see its files on disk.
    # optimize_alignment + merkle + mutable_torrent_support = 19
    # t = create_torrent(fs, flags=19) # BUG?
    t.set_priv(False)
    set_piece_hashes(t, os.path.dirname(directory))
    torrent = t.generate()
    with open(torrent_filename, 'wb') as f:
        f.write(bencode(torrent))

    infohash = torrent_info(torrent).info_hash().to_bytes()
    return infohash


def define_binding(db):
    class ChannelMetadata(db.TorrentMetadata):
        _discriminator_ = MetadataTypes.CHANNEL_TORRENT.value
        version = orm.Optional(int, size=64, default=0)
        subscribed = orm.Optional(bool, default=False)
        votes = orm.Optional(int, size=64, default=0)
        _payload_class = ChannelMetadataPayload
        _channels_dir = None

        @db_session
        def update_metadata(self, update_dict=None):
            now = datetime.utcnow()
            channel_dict = self.to_dict()
            channel_dict.update(update_dict or {})
            channel_dict.update({
                "size": len(self.contents_list),
                "timestamp": now,
                "torrent_date": now
            })
            self.set(**channel_dict)
            self.sign()

        @classmethod
        @db_session
        def process_channel_metadata_payload(cls, payload):
            """
            Process some channel metadata.
            :param payload: The channel metadata, in serialized form.
            :return: The ChannelMetadata object that contains the latest version of the channel
            """
            channel = ChannelMetadata.get_channel_with_id(payload.public_key)
            if channel:
                if payload.version > channel.version:
                    channel.delete()
                    return ChannelMetadata.from_payload(payload)
                else:
                    return channel
            else:
                return ChannelMetadata.from_payload(payload)

        @property
        @db_session
        def contents_list(self):
            return list(self.contents)

        @property
        def contents(self):
            return db.TorrentMetadata.select(lambda g: g.public_key == self.public_key and g != self)

        @property
        def dir_name(self):
            # Have to limit this to support Windows file path length limit
            return str(self.public_key).encode('hex')[-CHANNEL_DIR_NAME_LENGTH:]

        @classmethod
        @db_session
        def create_channel(cls, title, description):
            """
            Create a channel and sign it with a given key.
            :param title: The title of the channel
            :param description: The description of the channel
            :return: The channel metadata
            """
            if ChannelMetadata.get_channel_with_id(cls._my_key.pub().key_to_bin()):
                raise DuplicateChannelNameError()

            my_channel = cls(public_key=buffer(cls._my_key.pub().key_to_bin()), title=title,
                             tags=description, subscribed=True)
            my_channel.sign()
            return my_channel

        def consolidate_channel_torrent(self):
            """
            Delete the channel dir contents and create it anew.
            Use it to consolidate fragmented channel torrent directories.
            :param key: The public/private key, used to sign the data
            """

            self.commit_channel_torrent()

            folder = os.path.join(self._channels_dir, self.dir_name)
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if filename.endswith(BLOB_EXTENSION):
                    os.unlink(file_path)
                else:
                    raise ValueError
            self.update_channel_torrent(self.contents_list)

        def update_channel_torrent(self, metadata_list):
            """
            Channel torrents are append-only to support seeding the old versions
            from the same dir and avoid updating already downloaded blobs.
            :param metadata_list: The list of metadata entries to add to the torrent dir
            :return The new infohash, should be used to update the downloads
            """
            # Create dir for metadata files
            channel_dir = os.path.abspath(os.path.join(self._channels_dir, self.dir_name))
            if not os.path.isdir(channel_dir):
                os.makedirs(channel_dir)

            new_version = self.version

            # Write serialized and signed metadata into files
            for metadata in metadata_list:
                new_version += 1
                with open(os.path.join(channel_dir, str(new_version).zfill(9) + BLOB_EXTENSION), 'wb') as f:
                    serialized = metadata.serialized_delete(self._my_key) if metadata.deleted else metadata.serialized()
                    f.write(''.join(serialized))

            # Make torrent out of dir with metadata files
            infohash = create_torrent_from_dir(channel_dir, os.path.join(self._channels_dir, self.dir_name + ".torrent"))
            self.update_metadata(update_dict={"infohash": infohash, "version": new_version})

            # Write the channel mdblob away
            with open(os.path.join(self._channels_dir, self.dir_name + BLOB_EXTENSION), 'wb') as out_file:
                out_file.write(''.join(self.serialized()))
            return infohash

        def commit_channel_torrent(self):
            """
            Collect new/uncommitted and marked for deletion metadata entries, commit them to channel torrent and
            remove the obsolete entries if the commit succeeds.
            :return The new infohash, should be used to update the downloads
            """
            new_infohash = None
            try:
                new_infohash = self.update_channel_torrent(self.staged_entries_list)
            except IOError:
                print ("Error during channel torrent commit, not going to garbage collect the channel")
            else:
                # Clean up obsolete entries
                self.garbage_collect()
            return new_infohash

        @db_session
        def has_torrent(self, infohash):
            """
            Check whether this channel contains the torrent with a provided infohash.
            :param infohash: The infohash of the torrent to search for
            :return: True if the torrent exists in the channel, else False
            """
            return db.TorrentMetadata.get(public_key=self.public_key, infohash=infohash) is not None

        @db_session
        def add_torrent_to_channel(self, tdef, extra_info):
            """
            Add a torrent to your channel.
            :param tdef: The torrent definition file of the torrent to add
            :param extra_info: Optional extra info to add to the torrent
            """
            if self.has_torrent(tdef.get_infohash()):
                raise DuplicateTorrentFileError()

            torrent_metadata = db.TorrentMetadata.from_dict({
                "infohash": tdef.get_infohash(),
                "title": tdef.get_name_as_unicode(),
                "tags": extra_info.get('description', '') if extra_info else '',
                "size": tdef.get_length(),
                "torrent_date": datetime.fromtimestamp(tdef.get_creation_date()),
                "tc_pointer": 0,
                "public_key": self._my_key.pub().key_to_bin()
            })
            torrent_metadata.sign()

        @property
        def newer_entries(self):
            return db.Metadata.select(
                lambda g: g.timestamp > self.timestamp and g.public_key == self.public_key)

        @property
        @db_session
        def staged_entries_list(self):
            return list(db.Metadata.select(lambda g: g.deleted)) + list(self.newer_entries)

        @property
        def older_entries(self):
            return db.Metadata.select(
                lambda g: g.timestamp < self.timestamp and g.public_key == self.public_key)

        @db_session
        def garbage_collect(self):
            orm.delete(g for g in self.older_entries if g.deleted)

        @db_session
        def delete_torrent_from_channel(self, infohash):
            """
            Remove a torrent from this channel.
            Obsolete blob files are never deleted except on defragmentation of the channel.
            :param infohash: The infohash of the torrent to remove
            :return True if deleted, False if no MD with the given infohash found
            """
            if self.has_torrent(infohash):
                torrent_metadata = db.TorrentMetadata.get(public_key=self.public_key, infohash=infohash)
            else:
                return False
            if torrent_metadata.timestamp > self.timestamp:
                # Uncommited metadata. Delete immediately
                torrent_metadata.delete()
            else:
                torrent_metadata.deleted = True
            return True

        @classmethod
        @db_session
        def get_channel_with_id(cls, channel_id):
            """
            Fetch a channel with a specific id.
            :param channel_id: The ID of the channel to fetch.
            :return: the ChannelMetadata object, or None if it is not available.
            """
            return cls.get(public_key=buffer(channel_id))

    return ChannelMetadata
