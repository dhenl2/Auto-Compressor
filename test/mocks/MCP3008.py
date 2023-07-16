class MockMCP3008:
    """
    Mock Class for MCP3008 library
    """

    def __init__(self, channel):
        self.channel = channel
        self.values = [1, 2, 3, 4]
        self.value_index = 0

    def __getattribute__(self, item):
        if item == "value":
            return super(MockMCP3008, self).__getattribute__("mock_get_value")()
        else:
            return super(MockMCP3008, self).__getattribute__(item)

    def mock_get_value(self):
        val = self.values[self.value_index]
        self.value_index += 1

        return val

    def set_values(self, values):
        self.values = values
        self.value_index = 0