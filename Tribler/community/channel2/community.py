import struct
import time

from Tribler.Core.Modules.MetadataStore.serialization import ChannelMetadataPayload
from Tribler.pyipv8.ipv8.deprecated.community import Community
from Tribler.pyipv8.ipv8.peer import Peer


class Channel2Community(Community):
    """
    Simple overlay to test channel 2.0 dissemination.
    """
    master_peer = Peer("3081a7301006072a8648ce3d020106052b81040027038192000400118911f5102bac4fca2d6ee5c3cb41978a4b657"
                       "e9707ce2031685c7face02bb3bf42b74a47c1d2c5f936ea2fa2324af12de216abffe01f10f97680e8fe548b82dedf"
                       "362eb29d3b074187bcfbce6869acb35d8bcef3bb8713c9e9c3b3329f59ff3546c3cd560518f03009ca57895a5421b"
                       "4afc5b90a59d2096b43eb22becfacded111e84d605a01e91a600e2b55a79d".decode('hex'))

    def __init__(self, my_peer, endpoint, network, tribler_session=None):
        super(Channel2Community, self).__init__(my_peer, endpoint, network)
        self.tribler_session = tribler_session
        self.download_times = {}

    def get_my_channel(self):
        my_channel_id = self.tribler_session.trustchain_keypair.pub().key_to_bin()
        return self.tribler_session.lm.mds.ChannelMetadata.get_channel_with_id(my_channel_id)

    def create_introduction_response(self, lan_socket_address, socket_address, identifier,
                                     introduction=None, extra_bytes=b''):
        """
        Create an introduction response, that contains a ChannelMetadataNetworkPayload.
        """
        extra_bytes = b''
        channel = self.get_my_channel()
        if channel:
            lt_port = self.tribler_session.config.get_libtorrent_port()
            extra_bytes = channel.serialized(key=self.tribler_session.trustchain_keypair)
            extra_bytes += struct.pack('I', lt_port)
        return super(Channel2Community, self).create_introduction_response(lan_socket_address, socket_address,
                                                                           identifier, introduction, extra_bytes)

    def introduction_response_callback(self, peer, dist, payload):
        if not payload.extra_bytes:
            return

        lt_port = struct.unpack('I', payload.extra_bytes[-4:])[0]
        orig_payload = ChannelMetadataPayload.from_signed_blob(payload.extra_bytes[:-4])

        if not self.tribler_session.has_download(orig_payload.infohash):
            self._logger.info("Starting channel download with infohash %s (from peer %s)",
                              orig_payload.infohash.encode('hex'), peer)
            # Start downloading this channel
            download, finished_deferred = self.tribler_session.lm.update_channel(orig_payload)
            download.add_peer((peer.address[0], lt_port))

            start_time = time.time()

            def on_channel_download_finished(_):
                self.download_times[orig_payload.infohash] = time.time() - start_time

            finished_deferred.addCallback(on_channel_download_finished)
