from Tribler.pyipv8.ipv8.attestation.trustchain.block import TrustChainBlock, ValidationResult


class TradeChainBlock(TrustChainBlock):
    """
    Container for TradeChain block information
    """

    def validate_transaction(self, database):
        """
        Validate the content inside a TradeChainBlock.
        """
        result = [ValidationResult.valid]
        errors = []

        # short cut for invalidating so we don't have repeating similar code for every error.
        # this is also the reason result is a list, we need a mutable container. Assignments in err are limited to its
        # scope. So setting result directly is not possible.
        def err(reason):
            result[0] = ValidationResult.invalid
            errors.append(reason)

        if self.transaction["type"] == "tick":
            # Validate a tick block
            if 'tick' not in self.transaction:
                err('Tick not found in block')

            if self.transaction['tick']['port'] > 65536 or self.transaction['tick']['port'] < 0:
                err('Invalid port')

        return result[0], errors
