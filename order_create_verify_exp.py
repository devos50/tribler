import time
from Tribler.community.market.database import MarketDB
from Tribler.community.market.tradechain.block import TradeChainBlock
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto


total_times = 0.0

transaction = {
    'type': 'tick',
    'tick': {
        'port': 1234,
        'address': '1.1.1.1',
        'is_ask': True,
        'order_number': 2,
        'price': 1.0,
        'price_type': 'DUM1',
        'quantity': 1.0,
        'quantity_type': 'DUM2',
        'timeout': 3600.0,
        'timestamp': 1234,
        'trader_id': '62290f8e6321fae3ecdffd403b08770bd55ec248'
    }
}


def add_transaction_block(database, pub_key, third_party_key):
    block = TradeChainBlock.create({}, database, pub_key.pub().key_to_bin(),
                                   link_pk=third_party_key.pub().key_to_bin())
    block.sign(pub_key)
    database.add_block(block)


def generate_create_order_block():
    global total_times

    database = MarketDB('market', u":memory:")
    crypto = ECCrypto()

    pub_key = crypto.generate_key(u"curve25519")
    other_pub_key = crypto.generate_key(u"curve25519")
    third_party_key = crypto.generate_key(u"curve25519")

    # Create two previous blocks
    add_transaction_block(database, pub_key, third_party_key)
    add_transaction_block(database, other_pub_key, third_party_key)

    # Create the tick blocks
    start_time = time.time()
    block = TradeChainBlock.create(transaction, database, pub_key.pub().key_to_bin(), link_pk=other_pub_key.pub().key_to_bin())
    block.sign(pub_key)

    other_block = TradeChainBlock.create(transaction, database, other_pub_key.pub().key_to_bin(),
                                         link=block, link_pk=pub_key.pub().key_to_bin())
    other_block.sign(other_pub_key)
    duration = time.time() - start_time
    total_times += duration

    database.close()


def validate_order_block():
    global total_times

    database = MarketDB('market', u":memory:")
    crypto = ECCrypto()

    pub_key = crypto.generate_key(u"curve25519")
    other_pub_key = crypto.generate_key(u"curve25519")
    third_party_key = crypto.generate_key(u"curve25519")

    # Create two previous blocks
    add_transaction_block(database, pub_key, third_party_key)
    add_transaction_block(database, other_pub_key, third_party_key)

    # Create the tick blocks
    block = TradeChainBlock.create(transaction, database, pub_key.pub().key_to_bin(),
                                   link_pk=other_pub_key.pub().key_to_bin())
    block.sign(pub_key)

    other_block = TradeChainBlock.create(transaction, database, other_pub_key.pub().key_to_bin(),
                                         link=block, link_pk=pub_key.pub().key_to_bin())
    other_block.sign(other_pub_key)

    # Validate them
    start_time = time.time()
    block.validate(database)
    other_block.validate(database)
    duration = time.time() - start_time
    total_times += duration

    database.close()

for _ in xrange(1000):
    #generate_create_order_block()
    validate_order_block()

print "AVG: %f" % (total_times / 1000.0)
