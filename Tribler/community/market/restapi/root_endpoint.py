from twisted.web import resource


class RootEndpoint(resource.Resource):
    """
    This class represents the root endpoint of the market community API where we trade MultiChain reputation.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

        child_handler_dict = {}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session))
