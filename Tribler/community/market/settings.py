# Sync policies
SYNC_POLICY_NONE = 0
SYNC_POLICY_NEIGHBOURS = 1

# Dissemination policies
DISSEMINATION_POLICY_NEIGHBOURS = 0
DISSEMINATION_POLICY_RANDOM = 1


class MatchingSettings(object):
    """
    Object that defines various settings for the matching behaviour.
    """
    def __init__(self):
        self.ttl = 1
        self.fanout = 20
        self.match_window = 0  # How much time we wait before accepting a specific match
        self.match_send_interval = 0  # How long we should wait with sending a match message (to avoid overloading a peer)
        self.sync_interval = 30  # Synchronization interval
        self.num_order_sync = 10  # How many orders to sync at most
        self.send_fail_rate = 0  # Probability that sending a order/cancel order/match message is not received
        self.matchmaker_malicious_rate = 0  # Probability that the matchmaker behaves malicious

        self.sync_policy = SYNC_POLICY_NONE
        self.dissemination_policy = DISSEMINATION_POLICY_NEIGHBOURS

    def get_msg_reach(self):
        """
        Return the message reach, based on TTL/fanout
        """
        total = 0
        for ind in range(1, self.ttl+1):
            total += self.fanout ** ind
        return total
