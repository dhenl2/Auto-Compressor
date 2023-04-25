class MockMCP3008:
    """
    Mock Class for MCP3008 library
    """

    def __init__(self, channel):
        self.channel = channel
        self.values = []
        self.value_index = 0

    def __getattribute__(self, item):
        value = self.values[self.value_index]
        self.value_index += 1

        return value

    def set_values(self, values):
        self.values = values
        self.value_index = 0