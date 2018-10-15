import logging
import os
import struct
from array import array

from pony import orm
from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.OrmBindings import metadata, torrent_metadata, channel_metadata
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import BLOB_EXTENSION, SQUASHED_BLOB_EXTENSION, \
    CHUNK_HEADER_FORMAT, CHUNK_HEADER_INTRO, CHUNK_HEADER_SIZE
from Tribler.Core.Modules.MetadataStore.serialization import MetadataTypes, read_payload

# This table should never be used from ORM directly.
# It is created as a VIRTUAL table by raw SQL and
# maintained by SQL triggers.
from Tribler.Core.exceptions import InvalidSignatureException
from Tribler.pyipv8.ipv8.messaging.serialization import Serializer

sql_create_fts_table = """
    CREATE VIRTUAL TABLE IF NOT EXISTS FtsIndex USING FTS5
        (title, tags, content='Metadata',
         tokenize='porter unicode61 remove_diacritics 1');"""

sql_add_fts_trigger_insert = """
    CREATE TRIGGER IF NOT EXISTS fts_ai AFTER INSERT ON Metadata
    BEGIN
        INSERT INTO FtsIndex(rowid, title, tags) VALUES
            (new.rowid, new.title, new.tags);
    END;"""

sql_add_fts_trigger_delete = """
    CREATE TRIGGER IF NOT EXISTS fts_ad AFTER DELETE ON Metadata
    BEGIN
        DELETE FROM FtsIndex WHERE rowid = old.rowid;
    END;"""

sql_add_fts_trigger_update = """
    CREATE TRIGGER IF NOT EXISTS fts_au AFTER UPDATE ON Metadata BEGIN
        DELETE FROM FtsIndex WHERE rowid = old.rowid;
        INSERT INTO FtsIndex(rowid, title, tags) VALUES (new.rowid, new.title,
      new.tags);
    END;"""


class BadChunkException(Exception):
    pass


class MetadataStore(object):
    def __init__(self, db_filename, channels_dir, my_key):
        self.db_filename = db_filename
        self.channels_dir = channels_dir
        self.serializer = Serializer()
        self.my_key = my_key
        self._logger = logging.getLogger(self.__class__.__name__)

        create_db = (db_filename == ":memory:" or not os.path.isfile(self.db_filename))

        # We have to dynamically define/init ORM-managed entities here to be able to support
        # multiple sessions in Tribler. ORM-managed classes are bound to the database instance
        # at definition.
        self._db = orm.Database()

        # Accessors for ORM-managed classes
        self.Metadata = metadata.define_binding(self._db)
        self.TorrentMetadata = torrent_metadata.define_binding(self._db)
        self.ChannelMetadata = channel_metadata.define_binding(self._db)

        self.Metadata._my_key = my_key
        self.ChannelMetadata._channels_dir = channels_dir

        self._db.bind(provider='sqlite', filename=db_filename, create_db=create_db)
        if create_db:
            with db_session:
                self._db.execute(sql_create_fts_table)
        self._db.generate_mapping(create_tables=create_db)  # Must be run out of session scope
        if create_db:
            with db_session:
                self._db.execute(sql_add_fts_trigger_insert)
                self._db.execute(sql_add_fts_trigger_delete)
                self._db.execute(sql_add_fts_trigger_update)

    def shutdown(self):
        self._db.disconnect()

    def process_channel_dir(self, dirname):
        """
        Load blobs all metadata blobs in a given directory.
        :param dirname: The directory containing the metadata blobs.
        """
        for filename in sorted(os.listdir(dirname)):
            full_filename = os.path.join(dirname, filename)
            try:
                if filename.endswith(BLOB_EXTENSION):
                    self.process_mdblob_file(full_filename)
                elif filename.endswith(SQUASHED_BLOB_EXTENSION):
                    self.process_squashed_mdblob_file(full_filename)
            except InvalidSignatureException:
                self._logger.error("Not processing metadata located at %s: invalid signature", full_filename)

    @db_session
    def process_mdblob_file(self, filepath):
        """
        Process a file with metadata in a channel directory.
        :param filepath: The path to the file
        :return a Metadata object if we can correctly load the metadata
        """
        with open(filepath, 'rb') as f:
            serialized_data = f.read()
        return self.process_payload(read_payload(serialized_data))


    @db_session
    def process_squashed_mdblob(self, chunk_data):
        # Read the header
        print CHUNK_HEADER_SIZE
        intro, ends_offsets_array_size = struct.unpack(CHUNK_HEADER_FORMAT, chunk_data[:CHUNK_HEADER_SIZE])
        if intro != CHUNK_HEADER_INTRO:
            raise BadChunkException

        metadata_list = []
        ends_offsets_array = array('L').fromstring(
            chunk_data[CHUNK_HEADER_SIZE:CHUNK_HEADER_SIZE + ends_offsets_array_size])
        print ends_offsets_array
        for index, end_offset in enumerate(ends_offsets_array):
            blob = chunk_data[ends_offsets_array[index-1]:end_offset]
            md = self.process_payload(read_payload(blob))
            if md:
                metadata_list.append(md)

        return metadata_list


    @db_session
    def process_squashed_mdblob_file(self, filepath):
        """
        Process a file with multiple metadata entries in a channel directory.
        :param filepath: The path to the file
        :return a list of Metadata objects if we can correctly load the metadata
        """
        with open(filepath, 'rb') as f:
            chunk_data = f.read()

        return self.process_squashed_mdblob(chunk_data)


    @db_session
    def process_payload(self, payload):
        # Don't touch me! Workaround for Pony bug https://github.com/ponyorm/pony/issues/386 !
        orm.flush()

        if self.Metadata.exists(signature=payload.signature):
            return self.Metadata.get(signature=payload.signature)

        if payload.metadata_type == MetadataTypes.DELETED.value:
            # We only allow people to delete their own entries, thus PKs must match
            existing_metadata = self.Metadata.get(signature=payload.delete_signature, public_key=payload.public_key)
            if existing_metadata:
                existing_metadata.delete()
            return None
        elif payload.metadata_type == MetadataTypes.REGULAR_TORRENT.value:
            return self.TorrentMetadata.from_payload(payload)
        elif payload.metadata_type == MetadataTypes.CHANNEL_TORRENT.value:
            return self.ChannelMetadata.from_payload(payload)


    @db_session
    def get_my_channel(self):
        return self.ChannelMetadata.get_channel_with_id(self.my_key.pub().key_to_bin())


