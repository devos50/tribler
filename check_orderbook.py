"""
Check the orderbook whether there are still orders left.
"""
from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.matching_engine import MatchingEngine, PriceTimeStrategy
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId
from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.tick import Ask, Bid
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp

orders = []

with open("orders.log") as orders_file:
    for line in orders_file.readlines()[1:]:  # First line = header
        parts = line.split(",")
        order_type = parts[3]
        order_status = parts[4]
        order_cls = Ask if order_type == "ask" else Bid

        if order_status == "cancelled" or order_status == "expired":
            continue

        order_id_str = parts[1]
        order_id_parts = order_id_str.split(".")
        trader_id = TraderId(order_id_parts[0].decode('hex'))
        order_number = int(order_id_parts[1])
        order_id = OrderId(trader_id, order_number)
        asset_pair = AssetPair(AssetAmount(int(parts[5]), parts[6]), AssetAmount(int(parts[7]), parts[8]))
        timestamp = Timestamp(int(parts[0]))
        traded = int(parts[10])
        order = order_cls(order_id, asset_pair, Timeout(3600), timestamp, traded)
        orders.append(order)

orders.sort(key=lambda order: order.timestamp)

order_book = OrderBook()
matching_engine = MatchingEngine(PriceTimeStrategy(order_book))

# Start inserting them
for order in orders:
    if isinstance(order, Ask):
        order_book.insert_ask(order)
    else:
        order_book.insert_bid(order)

    entry = order_book.get_tick(order.order_id)
    matched_ticks = matching_engine.match(entry)
    if matched_ticks:
        print "Found possible match of %s and %s!" % (order.order_id, matched_ticks[0][1].order_id)
