from datetime import datetime

from pony import orm

from Tribler.Core.Modules.MetadataStore.serialization import MetadataTypes, MetadataPayload, time2float, float2time, \
    DeletedMetadataPayload
from Tribler.Core.exceptions import InvalidSignatureException
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto
from Tribler.pyipv8.ipv8.messaging.serialization import Serializer


EMPTY_SIG = '0' * 64


def define_binding(db):
    class Metadata(db.Entity):
        rowid = orm.PrimaryKey(int, auto=True)
        type = orm.Discriminator(int)
        _discriminator_ = MetadataTypes.TYPELESS.value
        signature = orm.Optional(buffer, default=EMPTY_SIG)
        timestamp = orm.Optional(datetime, default=datetime.utcnow)
        tc_pointer = orm.Optional(int, size=64, default=0)
        public_key = orm.Optional(buffer, default='\x00' * 74)
        addition_timestamp = orm.Optional(datetime, default=datetime.utcnow)
        deleted = orm.Optional(bool, default=False)

        def serialized_delete(self, key):
            """
            Encode for transport the special command to delete this metadata.
            """
            serializer = Serializer()
            delete_signature = self.signature
            type = MetadataTypes.DELETED.value
            signature = ECCrypto().create_signature(key, self.serialized_delete(key=None))\
                if key is not None else EMPTY_SIG
            payload = DeletedMetadataPayload(type, str(self.public_key), time2float(self.timestamp),
                                             self.tc_pointer,
                                             str(signature),
                                             str(delete_signature))
            return serializer.pack_multiple(payload.to_pack_list())[0]

        def serialized(self, signature=True):
            """
            Encode this metadata for transport.
            """
            serializer = Serializer()
            payload = MetadataPayload(self.type, str(self.public_key), time2float(self.timestamp),
                                      self.tc_pointer, str(self.signature) if signature else EMPTY_SIG)
            return serializer.pack_multiple(payload.to_pack_list())[0]

        def to_file(self, filename):
            with open(filename, 'wb') as output_file:
                output_file.write(self.serialized())

        def to_delete_file(self, key, filename):
            with open(filename, 'wb') as output_file:
                output_file.write(self.serialized_delete(key))

        def sign(self, key):
            self.public_key = buffer(key.pub().key_to_bin())
            serialized_data = self.serialized(signature=False)
            signature = ECCrypto().create_signature(key, serialized_data)
            self.signature = signature
            if not self.has_valid_signature():
                raise InvalidSignatureException("BLA")

        def has_valid_signature(self):
            crypto = ECCrypto()
            if not crypto.is_valid_public_bin(str(self.public_key)):
                return False
            if not crypto.is_valid_signature(crypto.key_from_public_bin(str(self.public_key)),
                                             self.serialized(signature=False), str(self.signature)):
                return False
            return True

        @classmethod
        def from_dict(cls, md_dict):
            return cls(**md_dict)

        @classmethod
        def from_payload(cls, payload):
            metadata_dict = {
                "type": payload.metadata_type,
                "public_key": payload.public_key,
                "timestamp": float2time(payload.timestamp),
                "tc_pointer": payload.tc_pointer,
                "signature": payload.signature
            }
            return cls(**metadata_dict)

    return Metadata
