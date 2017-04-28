import json

from twisted.web import http
from twisted.web import resource


class IomInputEndpoint(resource.Resource):
    """
    This class is responsible for managing input in the IoM module.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_POST(self, request):
        parameters = http.parse_qs(request.content.read(), 1)
        if 'input_name' not in parameters:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "input_name parameter missing"})

        input_dict = {}
        for name, value_array in parameters.iteritems():
            if name == 'input_name':
                continue
            input_dict[name] = value_array[0]

        self.session.lm.on_iom_input(parameters['input_name'][0], input_dict)

        return json.dumps({'success': True})
