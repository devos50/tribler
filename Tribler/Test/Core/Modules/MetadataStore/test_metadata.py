import os

from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.serialization import MetadataPayload
from Tribler.Test.test_as_server import TestAsServer


class TestMetadata(TestAsServer):
    """
    Contains various tests for the Metadata type.
    """

    def setUpPreSession(self):
        super(TestMetadata, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    @db_session
    def test_to_dict(self):
        """
        Test whether converting metadata to a dictionary works
        """
        metadata = self.session.lm.mds.Metadata.from_dict({})
        self.assertTrue(metadata.to_dict())

    @db_session
    def test_serialization(self):
        """
        Test converting metadata to serialized data
        """
        metadata = self.session.lm.mds.Metadata.from_dict({})
        self.assertTrue(metadata.serialized())

    @db_session
    def test_to_file(self):
        """
        Test writing metadata to a file
        """
        metadata = self.session.lm.mds.Metadata.from_dict({})
        file_path = os.path.join(self.session.config.get_state_dir(), 'metadata.file')
        metadata.to_file(file_path)
        self.assertTrue(os.path.exists(file_path))

    @db_session
    def test_has_valid_signature(self):
        """
        Test whether a signature can be validated correctly
        """
        metadata = self.session.lm.mds.Metadata.from_dict({})
        self.assertTrue(metadata.has_valid_signature())

        saved_key = metadata.public_key
        # Mess with the public key
        metadata.public_key = 'a'
        self.assertFalse(metadata.has_valid_signature())

        # Mess with the signature
        metadata.public_key = saved_key
        metadata.signature = 'a'
        self.assertFalse(metadata.has_valid_signature())

    @db_session
    def test_from_payload(self):
        """
        Test converting a metadata payload to a metadata object
        """
        metadata = self.session.lm.mds.Metadata.from_dict({})
        metadata_dict = metadata.to_dict()
        metadata.delete()
        metadata_payload = MetadataPayload(**metadata_dict)
        self.assertTrue(self.session.lm.mds.Metadata.from_payload(metadata_payload))
