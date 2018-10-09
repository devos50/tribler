import os
from datetime import datetime

from pony.orm import db_session
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.serialization import ChannelMetadataPayload, MetadataPayload
from Tribler.Core.Modules.MetadataStore.store import MetadataStore, UnknownBlobTypeException
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto

def make_wrong_payload(filename):
    key = ECCrypto().generate_key(u"curve25519")
    metadata_payload = MetadataPayload(666, buffer(key.pub().key_to_bin()), datetime.utcnow(), 123)
    with open(filename, 'wb') as output_file:
        output_file.write(''.join(metadata_payload.serialized(key)))

class TestMetadataStore(TriblerCoreTest):
    """
    This class contains tests for the metadata store.
    """
    DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(os.path.realpath(__file__))), '..', '..', 'data')
    CHANNEL_DIR = os.path.join(DATA_DIR, 'sample_channel',
                               'd24941643ff471e40d7761c71f4e3a4c21a4a5e89b0281430d01e78a4e46')
    CHANNEL_METADATA = os.path.join(DATA_DIR, 'sample_channel', 'channel.mdblob')

    @inlineCallbacks
    def setUp(self):
        yield super(TestMetadataStore, self).setUp()
        my_key = ECCrypto().generate_key(u"curve25519")

        self.metadata_store = MetadataStore(os.path.join(self.session_base_dir, 'test.db'),
                                            self.session_base_dir, my_key)

    @inlineCallbacks
    def tearDown(self):
        self.metadata_store.shutdown()
        yield super(TestMetadataStore, self).tearDown()

    @db_session
    def test_process_channel_dir_file(self):
        """
        Test whether we are able to process files in a directory containing torrent metadata
        """
        my_key = ECCrypto().generate_key(u"curve25519")
        pub_key_bin = my_key.pub().key_to_bin()

        test_torrent_metadata = self.metadata_store.TorrentMetadata(title='test', public_key=pub_key_bin)
        test_torrent_metadata.sign(my_key)
        metadata_path = os.path.join(self.session_base_dir, 'metadata.data')
        test_torrent_metadata.to_file(metadata_path)
        # We delete this TorrentMeta info now, it should be added again to the database when loading it
        test_torrent_metadata.delete()
        loaded_metadata = self.metadata_store.process_channel_dir_file(metadata_path)
        self.assertEqual(loaded_metadata.title, 'test')

        # Test whether we delete existing metadata when loading a DeletedMetadata blob
        metadata = self.metadata_store.TorrentMetadata(infohash='1'*20)
        metadata.sign(my_key)
        metadata.to_delete_file(my_key, metadata_path)
        loaded_metadata = self.metadata_store.process_channel_dir_file(metadata_path)
        # Make sure the original metadata is deleted
        self.assertIsNone(loaded_metadata)
        self.assertIsNone(self.metadata_store.TorrentMetadata.get(infohash='1'*20))

        # Test an unknown metadata type, this should raise an exception
        invalid_metadata = os.path.join(self.session_base_dir,'invalidtype.mdblob')
        make_wrong_payload(invalid_metadata)
        self.assertRaises(UnknownBlobTypeException, self.metadata_store.process_channel_dir_file, invalid_metadata)


    def test_process_channel_dir(self):
        """
        Test processing a directory containing metadata blobs
        """
        payload = ChannelMetadataPayload.from_file(self.CHANNEL_METADATA)
        channel_metadata = self.metadata_store.ChannelMetadata.process_channel_metadata_payload(payload)
        self.assertFalse(channel_metadata.contents_list)
        self.metadata_store.process_channel_dir(self.CHANNEL_DIR)
        self.assertEqual(len(channel_metadata.contents_list), 3)
