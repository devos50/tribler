from binascii import unhexlify

from ipv8.keyvault.crypto import ECCrypto

from Tribler.Core.Utilities.utilities import succeed
from Tribler.Core.bootstrap import Bootstrap
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import TestAsServer


class FakeDHT(object):

    def connect_peer(self, mid):
        matched_node = MockObject()
        matched_node.mid = mid
        matched_node.public_key = ECCrypto().generate_key("low").pub()

        nearby_node = MockObject()
        nearby_node.mid = unhexlify('b' * 20)
        nearby_node.public_key = ECCrypto().generate_key("low").pub()

        return succeed([matched_node, nearby_node])


class TestBootstrapDownload(TestAsServer):

    async def setUp(self):
        await super(TestBootstrapDownload, self).setUp()
        self.bootstrap = Bootstrap(self.temporary_directory(), dht=FakeDHT())

    async def test_load_and_fetch_bootstrap_peers(self):
        # Before bootstrap download
        nodes = await self.bootstrap.fetch_bootstrap_peers()
        self.assertEqual(nodes, {})

        # Assuming after bootstrap download
        self.bootstrap.download = MockObject()
        self.bootstrap.download.get_peerlist = lambda: [{'id': 'a' * 20}]

        # Before fetching any peers from the dht
        self.bootstrap.load_bootstrap_nodes()
        self.assertEqual(self.bootstrap.bootstrap_nodes, {})

        await self.bootstrap.fetch_bootstrap_peers()

        # Assuming DHT returns two peers for bootstrap download
        self.assertIsNotNone(self.bootstrap.bootstrap_nodes['a' * 20])
        self.assertIsNotNone(self.bootstrap.bootstrap_nodes['b' * 20])

        # Check if bootstrap peers are persisted to file after DHT response
        with open(self.bootstrap.nodes_file, "r") as boot_file:
            lines = boot_file.readlines()
            self.assertEqual(len(lines), 2)

        # Clear bootstrap nodes dict and load from file
        self.bootstrap.bootstrap_nodes = {}
        self.bootstrap.load_bootstrap_nodes()
        self.assertIsNotNone(self.bootstrap.bootstrap_nodes['a' * 20])
        self.assertIsNotNone(self.bootstrap.bootstrap_nodes['b' * 20])
