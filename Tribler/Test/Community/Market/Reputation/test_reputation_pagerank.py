from Tribler.Test.Community.Market.Reputation.test_reputation_base import TestReputationBase
from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair


class TestReputationPagerank(TestReputationBase):
    """
    Contains tests to test the reputation based on pagerank
    """

    def test_pagerank_1(self):
        """
        Test a very simple Temporal Pagerank computation
        """
        self.insert_transaction(b'a', b'b', AssetPair(AssetAmount(1, b'BTC'), AssetAmount(1, b'MB')))
        rep_dict = self.compute_reputations()
        self.assertTrue(b'a' in rep_dict)
        self.assertTrue(b'b' in rep_dict)
        self.assertGreater(rep_dict[b'a'], 0)
        self.assertGreater(rep_dict[b'b'], 0)

    def test_pagerank_2(self):
        """
        Test isolated nodes during a Temporal Pagerank computation
        """
        self.insert_transaction(b'a', b'b', AssetPair(AssetAmount(1, b'BTC'), AssetAmount(1, b'MB')))
        self.insert_transaction(b'c', b'd', AssetPair(AssetAmount(1, b'BTC'), AssetAmount(1, b'MB')))
        rep_dict = self.compute_reputations()
        self.assertTrue(b'c' in rep_dict)
        self.assertTrue(b'd' in rep_dict)

    def test_pagerank_3(self):
        """
        Test a more involved example of a Temporal Pagerank computation
        """
        self.insert_transaction(b'a', b'b', AssetPair(AssetAmount(1, b'BTC'), AssetAmount(1, b'MB')))
        self.insert_transaction(b'b', b'c', AssetPair(AssetAmount(100, b'BTC'), AssetAmount(10000, b'MB')))
        self.insert_transaction(b'b', b'd', AssetPair(AssetAmount(100, b'BTC'), AssetAmount(10000, b'MB')))
        self.insert_transaction(b'b', b'e', AssetPair(AssetAmount(100, b'BTC'), AssetAmount(10000, b'MB')))
        rep_dict = self.compute_reputations()
        self.assertEqual(len(rep_dict.keys()), 5)
        for rep in rep_dict.values():
            self.assertGreater(rep, 0)

    def test_pagerank_4(self):
        """
        Test an empty pagerank computation
        """
        rep_dict = self.compute_reputations()
        self.assertDictEqual(rep_dict, {})

    def test_pagerank_5(self):
        """
        Test a Temporal Pagerank computation
        """
        self.insert_transaction(b'a', b'b', AssetPair(AssetAmount(1, b'BTC'), AssetAmount(1, b'MB')))
        self.insert_transaction(b'a', b'c', AssetPair(AssetAmount(2, b'BTC'), AssetAmount(2, b'MB')))
        self.insert_transaction(b'a', b'd', AssetPair(AssetAmount(3, b'BTC'), AssetAmount(3, b'MB')))
        self.insert_transaction(b'a', b'e', AssetPair(AssetAmount(4, b'BTC'), AssetAmount(4, b'MB')))
        self.insert_transaction(b'a', b'f', AssetPair(AssetAmount(5, b'BTC'), AssetAmount(5, b'MB')))
        self.insert_transaction(b'a', b'g', AssetPair(AssetAmount(6, b'BTC'), AssetAmount(6, b'MB')))
        self.insert_transaction(b'a', b'h', AssetPair(AssetAmount(7, b'BTC'), AssetAmount(7, b'MB')))
        rep_dict = self.compute_reputations()
        self.assertTrue(b'c' in rep_dict)
        self.assertTrue(b'd' in rep_dict)
