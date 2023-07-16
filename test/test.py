import os
os.environ["environment"] = "testing"

from src.AutoCompressor import AutoCompressor



def repeat(value, num):
    array = []
    for i in range(num):
        array.append(value)

    return array

def get_pressure(compressor, target_value):
    air_sensor = compressor.air_sensor

    return (target_value - air_sensor.c) / air_sensor.m

def get_pressure_samples(compressor, samples, sample_count):
    all_samples = []
    for sample in samples:
        all_samples.extend(repeat(get_pressure(compressor, sample), sample_count))

    return all_samples


class MockInflate:
    def __init__(self):
        self.inflate_calls = []
        self.deflate_calls = []

    def mock_inflate(self, t):
        self.inflate_calls.append(t)
        return

    def mock_deflate(self, t):
        self.deflate_calls.append(t)
        return


def test_deflation_times_should_be_positive(mocker):
    samples = 20
    mock_compressor = AutoCompressor("./test_config.ini")
    mock_funcs = MockInflate()

    determine_current_mol_mock = mocker.spy(mock_compressor, "determine_current_mol")
    mocker.patch.object(mock_compressor, "inflate", mock_funcs.mock_inflate)
    mocker.patch.object(mock_compressor, "deflate", mock_funcs.mock_deflate)
    # mock air sensor readings
    mock_compressor.air_sensor.sensor.values = \
        get_pressure_samples(mock_compressor, [40, 38, 38, 38, 38, 20, 10], samples)
    mock_compressor.reach_target(10)

    assert len(mock_funcs.inflate_calls) == 0
    assert len(mock_funcs.deflate_calls) == 3
    for call in mock_funcs.deflate_calls:
        assert 150 > call > 0

def test_inflation_times_should_be_positive(mocker):
    samples = 20
    mock_compressor = AutoCompressor("./test_config.ini")
    mock_funcs = MockInflate()

    determine_current_mol_mock = mocker.spy(mock_compressor, "determine_current_mol")
    mocker.patch.object(mock_compressor, "inflate", mock_funcs.mock_inflate)
    mocker.patch.object(mock_compressor, "deflate", mock_funcs.mock_deflate)
    # mock air sensor readings
    mock_compressor.air_sensor.sensor.values = \
        get_pressure_samples(mock_compressor, [10, 12, 12, 12, 12, 28, 38, 40], samples)
    mock_compressor.reach_target(40)

    assert len(mock_funcs.deflate_calls) == 0
    assert len(mock_funcs.inflate_calls) == 4
    for call in mock_funcs.inflate_calls:
        assert 150 > call > 0

def test_inflation_deflation_times_should_be_positive(mocker):
    samples = 20
    mock_compressor = AutoCompressor("./test_config.ini")
    mock_funcs = MockInflate()

    determine_current_mol_mock = mocker.spy(mock_compressor, "determine_current_mol")
    mocker.patch.object(mock_compressor, "inflate", mock_funcs.mock_inflate)
    mocker.patch.object(mock_compressor, "deflate", mock_funcs.mock_deflate)
    # mock air sensor readings
    mock_compressor.air_sensor.sensor.values = \
        get_pressure_samples(mock_compressor, [10, 12, 12, 12, 12, 28, 50, 36, 40], samples)
    mock_compressor.reach_target(40)

    assert len(mock_funcs.inflate_calls) == 1
    for call in mock_funcs.inflate_calls:
        assert 150 > call > 0
    assert len(mock_funcs.deflate_calls) == 4
    for call in mock_funcs.deflate_calls:
        assert 150 > call > 0