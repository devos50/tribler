from Tribler.pyipv8.ipv8.messaging.anonymization.tunnel import CIRCUIT_STATE_READY, CIRCUIT_TYPE_RP
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Socks5.server import Socks5Server
from Tribler.community.triblertunnel.dispatcher import TunnelDispatcher
from Tribler.pyipv8.ipv8.messaging.anonymization.community import TunnelCommunity, CreatePayload


class TriblerTunnelCommunity(TunnelCommunity):
    # TODO fix master peer
    # TODO add notifiers!

    def __init__(self, *args, **kwargs):
        self.tribler_session = kwargs.pop('tribler_session', None)
        super(TriblerTunnelCommunity, self).__init__(*args, **kwargs)

        if self.tribler_session:
            self.settings.become_exitnode = self.tribler_session.config.get_tunnel_community_exitnode_enabled()
            socks_listen_ports = self.tribler_session.config.get_tunnel_community_socks5_listen_ports()
            self.tribler_session.lm.tunnel_community = self
        else:
            socks_listen_ports = range(1080, 1085)

        self.bittorrent_peers = {}
        self.dispatcher = TunnelDispatcher(self)

        # Start the SOCKS5 servers
        self.socks_servers = []
        for port in socks_listen_ports:
            socks_server = Socks5Server(port, self.dispatcher)
            socks_server.start()
            self.socks_servers.append(socks_server)

        self.dispatcher.set_socks_servers(self.socks_servers)

    def on_download_removed(self, download):
        """
        This method is called when a download is removed. We check here whether we can stop building circuits for a
        specific number of hops in case it hasn't been finished yet.
        """
        if download.get_hops() > 0:
            self.num_hops_by_downloads[download.get_hops()] -= 1
            if self.num_hops_by_downloads[download.get_hops()] == 0:
                self.circuits_needed[download.get_hops()] = 0

    def readd_bittorrent_peers(self):
        for torrent, peers in self.bittorrent_peers.items():
            infohash = torrent.tdef.get_infohash().encode("hex")
            for peer in peers:
                self.logger.info("Re-adding peer %s to torrent %s", peer, infohash)
                torrent.add_peer(peer)
            del self.bittorrent_peers[torrent]

    def remove_circuit(self, circuit_id, additional_info='', destroy=False):
        if circuit_id not in self.circuits:
            self.logger.warning("Circuit %d not found when trying to remove it", circuit_id)
            return

        circuit = self.circuits[circuit_id]

        # Send the notification
        if self.tribler_session:
            from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_REMOVE
            self.tribler_session.notifier.notify(NTFY_TUNNEL, NTFY_REMOVE, circuit, circuit.sock_addr)

        affected_peers = self.dispatcher.circuit_dead(circuit)
        ltmgr = self.tribler_session.lm.ltmgr \
            if self.tribler_session and self.tribler_session.config.get_libtorrent_enabled() else None
        if ltmgr:
            def update_torrents(handle, download):
                peers = affected_peers.intersection(handle.get_peer_info())
                if peers:
                    if download not in self.bittorrent_peers:
                        self.bittorrent_peers[download] = peers
                    else:
                        self.bittorrent_peers[download] = peers | self.bittorrent_peers[download]

                    # If there are active circuits, add peers immediately. Otherwise postpone.
                    if self.active_data_circuits():
                        self.readd_bittorrent_peers()

            for d, s in ltmgr.torrents.values():
                if s == ltmgr.get_session(d.get_hops()):
                    d.get_handle().addCallback(update_torrents, d)

        # Now we actually remove the circuit
        super(TriblerTunnelCommunity, self).remove_circuit(circuit_id, additional_info=additional_info, destroy=destroy)

        # TODO what about the cleaning of the directions?

    def remove_relay(self, circuit_id, additional_info='', destroy=False, got_destroy_from=None, both_sides=True):
        removed_relays = super(TriblerTunnelCommunity, self).remove_relay(circuit_id,
                                                                          additional_info=additional_info,
                                                                          destroy=destroy,
                                                                          got_destroy_from=got_destroy_from,
                                                                          both_sides=both_sides)

        if self.tribler_session:
            for removed_relay in removed_relays:
                from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_REMOVE
                self.tribler_session.notifier.notify(NTFY_TUNNEL, NTFY_REMOVE, removed_relay, removed_relay.sock_addr)

    def remove_exit_socket(self, circuit_id, additional_info='', destroy=False):
        if circuit_id in self.exit_sockets and self.tribler_session:
            exit_socket = self.exit_sockets[circuit_id]
            from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_REMOVE
            self.tribler_session.notifier.notify(NTFY_TUNNEL, NTFY_REMOVE, exit_socket, exit_socket.sock_addr)

        super(TriblerTunnelCommunity, self).remove_exit_socket(circuit_id, additional_info=additional_info,
                                                               destroy=destroy)

    def _ours_on_created_extended(self, circuit, payload):
        super(TriblerTunnelCommunity, self)._ours_on_created_extended(circuit, payload)

        if circuit.state == CIRCUIT_STATE_READY:
            # Re-add BitTorrent peers, if needed.
            self.readd_bittorrent_peers()

        if self.tribler_session:
            from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_CREATED, NTFY_EXTENDED
            self.tribler_session.notifier.notify(
                NTFY_TUNNEL, NTFY_CREATED if len(circuit.hops) == 1 else NTFY_EXTENDED, circuit)

    def on_create(self, source_address, data, _):
        super(TriblerTunnelCommunity, self).on_create(source_address, data, _)
        dist, payload = self._ez_unpack_noauth(CreatePayload, data)

        if not self.check_create(payload):
            return

        circuit_id = payload.circuit_id

        if self.tribler_session:
            from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_JOINED
            self.tribler_session.notifier.notify(NTFY_TUNNEL, NTFY_JOINED, source_address, circuit_id)

    def handle_raw_data(self, circuit, origin, data):
        anon_seed = circuit.ctype == CIRCUIT_TYPE_RP
        self.dispatcher.on_incoming_from_tunnel(self, circuit, origin, data, anon_seed)

    @inlineCallbacks
    def unload(self):
        for socks_server in self.socks_servers:
            yield socks_server.stop()

        super(TriblerTunnelCommunity, self).unload()
