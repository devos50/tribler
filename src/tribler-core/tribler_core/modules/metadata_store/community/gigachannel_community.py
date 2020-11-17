import uuid
from binascii import unhexlify
from dataclasses import dataclass
from random import sample

from ipv8.peerdiscovery.network import Network

from pony.orm import db_session

from tribler_common.simpledefs import CHANNELS_VIEW_UUID, NTFY

from tribler_core.modules.metadata_store.community.remote_query_community import (
    RemoteQueryCommunity,
    RemoteQueryCommunitySettings,
)
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT
from tribler_core.modules.metadata_store.store import UNKNOWN_CHANNEL, UNKNOWN_COLLECTION, UNKNOWN_TORRENT

minimal_blob_size = 200
maximum_payload_size = 1024
max_entries = maximum_payload_size // minimal_blob_size
max_search_peers = 5


@dataclass
class GigaChannelCommunitySettings(RemoteQueryCommunitySettings):
    queried_peers_limit: int = 1000


class GigaChannelCommunity(RemoteQueryCommunity):
    community_id = unhexlify('dce2e4e31c57b7b54600251ce3bc8945ee31b7eb')

    def __init__(self, my_peer, endpoint, network, metadata_store, **kwargs):
        kwargs["settings"] = kwargs.get("settings", GigaChannelCommunitySettings())
        self.notifier = kwargs.pop("notifier", None)

        # ACHTUNG! We create a separate instance of Network for this community because it
        # walks aggressively and wants lots of peers, which can interfere with other communities
        super().__init__(my_peer, endpoint, Network(), metadata_store, **kwargs)

        # This set contains all the peers that we queried for subscribed channels over time.
        # It is emptied regularly. The purpose of this set is to work as a filter so we never query the same
        # peer twice. If we do, this should happen really rarely
        # TODO: use Bloom filter here instead. We actually *want* it to be all-false-positives eventually.
        self.queried_peers = set()

    def get_random_peers(self, sample_size=None):
        # Randomly sample sample_size peers from the complete list of our peers
        all_peers = self.get_peers()
        if sample_size is not None and sample_size < len(all_peers):
            return sample(all_peers, sample_size)
        return all_peers

    def introduction_response_callback(self, peer, dist, payload):
        if peer.address in self.network.blacklist or peer.mid in self.queried_peers:
            return
        if len(self.queried_peers) >= self.settings.queried_peers_limit:
            self.queried_peers.clear()
        self.queried_peers.add(peer.mid)
        self.send_remote_select_subscribed_channels(peer)

    def send_remote_select_subscribed_channels(self, peer):
        def on_packet_callback(_, processing_results):
            # We use responses for requests about subscribed channels to bump our local channels ratings
            with db_session:
                for c in [md for md, _ in processing_results if md.metadata_type == CHANNEL_TORRENT]:
                    self.mds.vote_bump(c.public_key, c.id_, peer.public_key.key_to_bin()[10:])

            # Notify GUI about the new channels
            new_channels = [md for md, result in processing_results if result == UNKNOWN_CHANNEL and md.origin_id == 0]
            if self.notifier and new_channels:
                self.notifier.notify(
                    NTFY.CHANNEL_DISCOVERED,
                    {"results": [md.to_simple_dict() for md in new_channels], "uuid": str(CHANNELS_VIEW_UUID)},
                )

        request_dict = {
            "metadata_type": [CHANNEL_TORRENT],
            "subscribed": True,
            "attribute_ranges": (("num_entries", 1, None),),
        }
        self.send_remote_select(peer, **request_dict, processing_callback=on_packet_callback)

    def send_search_request(self, **kwargs):
        # Send a remote query request to multiple random peers to search for some terms
        request_uuid = uuid.uuid4()

        def notify_gui(_, processing_results):
            search_results = [
                md.to_simple_dict()
                for md, result in processing_results
                if result in (UNKNOWN_TORRENT, UNKNOWN_CHANNEL, UNKNOWN_COLLECTION)
            ]
            self.notifier.notify(NTFY.REMOTE_QUERY_RESULTS, {"uuid": str(request_uuid), "results": search_results})

        for p in self.get_random_peers(self.settings.max_query_peers):
            self.send_remote_select(p, **kwargs, processing_callback=notify_gui)

        return request_uuid


class GigaChannelTestnetCommunity(GigaChannelCommunity):
    """
    This community defines a testnet for the giga channels, used for testing purposes.
    """

    community_id = unhexlify('f58df52d10f7339ff6e2888322011489e9ab3d59')
