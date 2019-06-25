from client import ClientSoundCard
from generate_sound import generate_sound, WindowConfiguration

import pytest


@pytest.fixture
def prepare_sound():
    sound_index = 4
    duration = 12
    sample_rate = 96000
    data_type = 0

    # generate sound
    window_config = WindowConfiguration( left_duration = 0,
                                     left_apply_window_start = True,
                                     left_apply_window_end = False,
                                     left_window_function = 'Blackman',
                                     right_duration = 0.01,
                                     right_apply_window_start = False,
                                     right_apply_window_end = True,
                                     right_window_function = 'Bartlett')

    wave_int = generate_sound(fs=sample_rate,                 # sample rate in Hz
                              duration=duration,              # duration of the sound in seconds
                              frequency_left=1500,            # frequency of the sinusoidal signal generated in Hz for the left channel
                              frequency_right=1200,           # frequency of the sinusoidal signal generated in Hz for the right channel
                              window_configuration=window_config
                              )
    return wave_int

@pytest.mark.asyncio
async def test_header_size_with_data_and_with_file_metadata(prepare_sound):
    client = ClientSoundCard(prepare_sound)
    client.prepare_header(with_data=True, with_file_metadata=True)

    assert len(client.header) == (7 + 16 + 32768 + 2048 + 1)

@pytest.mark.asyncio
async def test_header_size_without_data_and_with_file_metadata(prepare_sound):
    client = ClientSoundCard(prepare_sound)
    client.prepare_header(with_data=False, with_file_metadata=True)

    assert len(client.header) == (7 + 16 + 2048 + 1)

@pytest.mark.asyncio
async def test_header_size_without_data_and_without_file_metadata(prepare_sound):
    client = ClientSoundCard(prepare_sound)
    client.prepare_header(with_data=False, with_file_metadata=False)

    assert len(client.header) == (5 + 16 + 1)