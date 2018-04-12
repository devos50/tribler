import logging
import os
from twisted.internet import reactor, task
from twisted.web import resource

import Tribler.Core.Utilities.json_util as json


class ShutdownEndpoint(resource.Resource):
    """
    With this endpoint you can shutdown Tribler.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session

    def render_PUT(self, request):
        """
        .. http:put:: /shutdown

        A PUT request to this endpoint will shutdown Tribler.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/shutdown

            **Example response**:

            .. sourcecode:: javascript

                {
                    "shutdown": True
                }
        """
        def shutdown_process(_, code=1):
            reactor.addSystemEventTrigger('after', 'shutdown', os._exit, code)
            reactor.stop()

        def log_and_shutdown(failure):
            self._logger.error(failure.value)
            shutdown_process(failure, 0)

        task.deferLater(reactor, 0, self.session.shutdown) \
            .addCallback(shutdown_process) \
            .addErrback(log_and_shutdown)

        return json.dumps({"shutdown": True})
