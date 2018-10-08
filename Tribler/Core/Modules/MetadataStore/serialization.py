from __future__ import division

from datetime import datetime, timedelta

from enum import Enum, unique

from Tribler.pyipv8.ipv8.attestation.trustchain.block import EMPTY_SIG
from Tribler.pyipv8.ipv8.deprecated.payload import Payload
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto
from Tribler.pyipv8.ipv8.messaging.serialization import Serializer

EPOCH = datetime(1970, 1, 1)
INFOHASH_SIZE = 20  # bytes

SIGNATURE_SIZE = 64

crypto = ECCrypto()
serializer = Serializer()


@unique
class MetadataTypes(Enum):
    TYPELESS = 1
    REGULAR_TORRENT = 2
    CHANNEL_TORRENT = 3
    DELETED = 4


TYPELESS = MetadataTypes.TYPELESS
REGULAR_TORRENT = MetadataTypes.REGULAR_TORRENT
CHANNEL_TORRENT = MetadataTypes.CHANNEL_TORRENT
DELETED = MetadataTypes.DELETED


# We have to write our own serialization procedure for timestamps, since
# there is no standard for this, except Unix time, and that is
# deprecated by 2038, that is very soon.


def time2float(date_time, epoch=EPOCH):
    """
    Convert a datetime object to a float.
    :param date_time: The datetime object to convert.
    :param epoch: The epoch time, defaults to Jan 1, 1970.
    :return: The floating point representation of date_time.

    WARNING: TZ-aware timestamps are madhouse...
    For Python3 we could use a simpler method:
    >>> timestamp = (dt - datetime(1970, 1, 1, tzinfo=timezone.utc)) / timedelta(seconds=1)
    """
    time_diff = date_time - epoch
    return float((time_diff.microseconds + (time_diff.seconds + time_diff.days * 86400) * 10 ** 6) / 10 ** 6)


def float2time(timestamp, epoch=EPOCH):
    """
    Convert a float into a datetime object.
    :param timestamp: The timestamp to be converted.
    :param epoch: The epoch time, defaults to Jan 1, 1970.
    :return: The datetime representation of timestamp.
    """
    microseconds_total = int(timestamp * 10 ** 6)
    microseconds = microseconds_total % 10 ** 6
    seconds_total = (microseconds_total - microseconds) / 10 ** 6
    seconds = seconds_total % 86400
    days = (seconds_total - seconds) / 86400
    dt = epoch + timedelta(days=days, seconds=seconds, microseconds=microseconds)
    return dt


class InvalidSignatureException(Exception):
    pass

class KeysMismatchException(Exception):
    pass

class MetadataPayload(Payload):
    """
    Payload for metadata.
    """

    format_list = ['I', '74s', 'f', 'I']

    def __init__(self, metadata_type, public_key, timestamp, tc_pointer, signature=EMPTY_SIG, **kwargs):
        super(MetadataPayload, self).__init__()
        self.metadata_type = metadata_type
        self.public_key = str(public_key)
        self.timestamp = time2float(timestamp) if isinstance(timestamp, datetime) else timestamp
        self.tc_pointer = tc_pointer
        self.signature = str(signature)

    def has_valid_signature(self):
        sig_data = serializer.pack_multiple(self.to_pack_list())[0]
        return crypto.is_valid_signature(crypto.key_from_public_bin(self.public_key), sig_data, self.signature)

    def to_pack_list(self):
        data = [('I', self.metadata_type),
                ('74s', self.public_key),
                ('f', self.timestamp),
                ('I', self.tc_pointer)]
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, timestamp, tc_pointer):
        return MetadataPayload(metadata_type, public_key, timestamp, tc_pointer)

    @classmethod
    def from_signed_blob(cls, data, check_signature=True):
        payload = serializer.unpack_to_serializables([cls, ], data)[0]
        payload.signature = data[-SIGNATURE_SIZE:]
        data_unsigned = data[:-SIGNATURE_SIZE]
        if check_signature:
            key = crypto.key_from_public_bin(payload.public_key)
            if not crypto.is_valid_signature(key, data_unsigned, payload.signature):
                raise InvalidSignatureException
        return payload

    def to_dict(self):
        return {
            "metadata_type": self.metadata_type,
            "public_key": self.public_key,
            "timestamp": float2time(self.timestamp),
            "tc_pointer": self.tc_pointer,
            "signature": self.signature
        }

    def serialized(self, key=None):
        # If we are going to sign it, we must provide a matching key
        if key and self.public_key != str(key.pub().key_to_bin()):
                raise KeysMismatchException(self.public_key, str(key.pub().key_to_bin()))

        serialized_data = serializer.pack_multiple(self.to_pack_list())[0]
        signature = ECCrypto().create_signature(key, serialized_data) if key else self.signature
        #self.from_signed_blob(''.join(str(serialized_data)+str(signature)))
        return str(serialized_data), str(signature)

    @classmethod
    def from_file(cls, filepath):
        with open(filepath, 'rb') as f:
            return cls.from_signed_blob(f.read())


class TorrentMetadataPayload(MetadataPayload):
    """
    Payload for metadata that stores a torrent.
    """
    format_list = MetadataPayload.format_list + ['20s', 'I', 'varlenI', 'varlenI']

    def __init__(self, metadata_type, public_key, timestamp, tc_pointer, infohash, size, title, tags,
                 signature=EMPTY_SIG, **kwargs):
        super(TorrentMetadataPayload, self).__init__(metadata_type, public_key, timestamp, tc_pointer,
                                                     signature=signature, **kwargs)
        self.infohash = str(infohash)
        self.size = size
        self.title = str(title)
        self.tags = str(tags)

    def to_pack_list(self):
        data = super(TorrentMetadataPayload, self).to_pack_list()
        data.append(('20s', self.infohash))
        data.append(('I', self.size))
        data.append(('varlenI', self.title))
        data.append(('varlenI', self.tags))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, timestamp, tc_pointer, infohash, size, title, tags):
        return TorrentMetadataPayload(metadata_type, public_key, timestamp, tc_pointer, infohash, size, title, tags)

    def to_dict(self):
        dct = super(TorrentMetadataPayload, self).to_dict()
        dct.update({
            "infohash": self.infohash,
            "size": self.size,
            "title": self.title,
            "tags": self.tags
        })
        return dct


class ChannelMetadataPayload(TorrentMetadataPayload):
    """
    Payload for metadata that stores a channel.
    """
    format_list = TorrentMetadataPayload.format_list + ['I']

    def __init__(self, metadata_type, public_key, timestamp, tc_pointer, infohash, size, title, tags, version,
                 signature=EMPTY_SIG, **kwargs):
        super(ChannelMetadataPayload, self).__init__(metadata_type, public_key, timestamp, tc_pointer,
                                                     infohash, size, title, tags, signature=signature, **kwargs)
        self.version = version

    def to_pack_list(self):
        data = super(ChannelMetadataPayload, self).to_pack_list()
        data.append(('I', self.version))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, timestamp, tc_pointer, infohash, size, title, tags, version):
        return ChannelMetadataPayload(metadata_type, public_key, timestamp, tc_pointer, infohash, size,
                                      title, tags, version)

    def to_dict(self):
        dct = super(ChannelMetadataPayload, self).to_dict()
        dct.update({"version": self.version})
        return dct


class DeletedMetadataPayload(MetadataPayload):
    """
    Payload for metadata that stores deleted metadata.
    """
    format_list = MetadataPayload.format_list + ['64s']

    def __init__(self, metadata_type, public_key, timestamp, tc_pointer, delete_signature,
                 signature=EMPTY_SIG, **kwargs):
        super(DeletedMetadataPayload, self).__init__(metadata_type, public_key, timestamp, tc_pointer,
                                                     signature=signature, **kwargs)
        self.delete_signature = str(delete_signature)

    def to_pack_list(self):
        data = super(DeletedMetadataPayload, self).to_pack_list()
        data.append(('64s', self.delete_signature))
        return data

    @classmethod
    def from_unpack_list(cls, metadata_type, public_key, timestamp, tc_pointer, delete_signature):
        return DeletedMetadataPayload(metadata_type, public_key, timestamp, tc_pointer, delete_signature)

    def to_dict(self):
        dct = super(DeletedMetadataPayload, self).to_dict()
        dct.update({"delete_signature": self.delete_signature})
        return dct

