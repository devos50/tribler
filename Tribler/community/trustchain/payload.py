from Tribler.dispersy.payload import Payload


class CrawlRequestPayload(Payload):
    """
    Request a crawl of blocks starting with a specific sequence number or the first if 0.
    """
    class Implementation(Payload.Implementation):
        def __init__(self, meta, requested_sequence_number, crawl_id):
            super(CrawlRequestPayload.Implementation, self).__init__(meta)
            self.requested_sequence_number = requested_sequence_number
            self.crawl_id = crawl_id


class CrawlResponsePayload(Payload):
    """
    Response to a crawl of blocks.
    """
    class Implementation(Payload.Implementation):
        def __init__(self, meta, block, crawl_id, cur_count, total_count):
            super(CrawlResponsePayload.Implementation, self).__init__(meta)
            self.block = block
            self.crawl_id = crawl_id
            self.cur_count = cur_count
            self.total_count = total_count


class HalfBlockPayload(Payload):
    """
    Payload for message that ships a half block
    """
    class Implementation(Payload.Implementation):
        def __init__(self, meta, block):
            super(HalfBlockPayload.Implementation, self).__init__(meta)
            self.block = block


class BlockPairPayload(Payload):
    """
    Payload for message that ships two (signed) half blocks
    """
    class Implementation(Payload.Implementation):
        def __init__(self, meta, block1, block2):
            super(BlockPairPayload.Implementation, self).__init__(meta)
            self.block1 = block1
            self.block2 = block2
