import pytest
import numpy as np
from client import ClientSoundCard
from generate_sound import generate_sound, WindowConfiguration


@pytest.fixture
def prepare_sound():

    def create_sound(sound_index, duration, sample_rate, data_type):
        # generate sound
        window_config = WindowConfiguration( left_duration = 0.01,
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

    return create_sound

@pytest.mark.asyncio
async def test_header_size_with_data_and_with_file_metadata(prepare_sound):
    client = ClientSoundCard(prepare_sound(2, 4, 96000, 0))
    client.prepare_header(with_data=True, with_file_metadata=True)

    assert len(client.header) == (7 + 16 + 32768 + 2048 + 1)

@pytest.mark.asyncio
async def test_header_size_without_data_and_with_file_metadata(prepare_sound):
    client = ClientSoundCard(prepare_sound(2, 4, 96000, 0))
    client.prepare_header(with_data=False, with_file_metadata=True)

    assert len(client.header) == (7 + 16 + 2048 + 1)

@pytest.mark.asyncio
async def test_header_size_without_data_and_without_file_metadata(prepare_sound):
    client = ClientSoundCard(prepare_sound(2, 4, 96000, 0))
    client.prepare_header(with_data=False, with_file_metadata=False)

    assert len(client.header) == (5 + 16 + 1)

@pytest.mark.asyncio
@pytest.mark.parametrize('sound_index', [2, 10, 20])
@pytest.mark.parametrize('duration', [4, 8, 12, 25])
@pytest.mark.parametrize('sample_rate', [96000, 192000])
@pytest.mark.parametrize('data_type', [0,1])
async def test_metadata_contents(prepare_sound, sound_index, duration, sample_rate, data_type):
    metadata_index = 7

    client = ClientSoundCard(prepare_sound(sound_index, duration, sample_rate, data_type))
    client.prepare_header(with_data=True, with_file_metadata=True)
    client.add_metadata([sound_index, client.sound_file_size_in_samples, sample_rate, data_type])

    sound_index_on_header = client.header[metadata_index: metadata_index + 4].view(np.int32)
    assert sound_index == sound_index_on_header

    sound_file_size_in_samples_on_header = client.header[metadata_index + 4: metadata_index + 4 + 4].view(np.int32)
    assert client.sound_file_size_in_samples == sound_file_size_in_samples_on_header

    sample_rate_on_header = client.header[metadata_index + 4 * 2: metadata_index + 4 * 2 + 4].view(np.int32)
    assert sample_rate == sample_rate_on_header

    data_type_on_header = client.header[metadata_index + 4 * 3: metadata_index + 4 * 3 + 4].view(np.int32)
    assert data_type == data_type_on_header

@pytest.mark.asyncio
@pytest.mark.parametrize('sound_filename_str', 
                         ['testing.filename.bin', 
                          'with some unicode chars á é í ó ú @', 
                          '.', 
                          '',
                          'extremely long string so that it might go over the size limit. let\'s repeat that so we might actually reach the maximum value. extremely long string so that it might go over the size limit.'])
async def test_file_metadata_sound_filename(prepare_sound, sound_filename_str):
    file_metadata_index = 0
    max_dimension = 169

    client = ClientSoundCard(prepare_sound(2, 4, 96000, 1))
    client.prepare_header(with_data=True, with_file_metadata=True)

    client.add_sound_filename(sound_filename_str)

    sound_filename_on_header = client.filemetadata[file_metadata_index: file_metadata_index + max_dimension]
    as_str = sound_filename_on_header.tobytes().strip(b'\0')
    assert sound_filename_str[:max_dimension] == "".join(map(chr, as_str))
 
@pytest.mark.asyncio
@pytest.mark.parametrize('testing_metadata_name', 
                         ['testing.metadata.bin', 
                          'with some unicode chars á é í ó ú @', 
                          '.', 
                          '',
                          'extremely long string so that it might go over the size limit. let\'s repeat that so we might actually reach the maximum value. extremely long string so that it might go over the size limit.'])
async def test_file_metadata_with_metadata_filename(prepare_sound, testing_metadata_name):
    file_metadata_index = 170
    max_dimension = 169

    client = ClientSoundCard(prepare_sound(2, 4, 96000, 1))
    client.prepare_header(with_data=True, with_file_metadata=True)

    client.add_metadata_filename(testing_metadata_name)

    metadata_filename_on_header = client.filemetadata[file_metadata_index: file_metadata_index + max_dimension]
    as_str = metadata_filename_on_header.tobytes().strip(b'\0')
    assert testing_metadata_name[:max_dimension] == "".join(map(chr, as_str))
 
@pytest.mark.asyncio
@pytest.mark.parametrize('testing_description_name', 
                         ['testing.description.bin', 
                          'with some unicode chars á é í ó ú @', 
                          '.', 
                          '',
                          'extremely long string so that it might go over the size limit. let\'s repeat that so we might actually reach the maximum value. extremely long string so that it might go over the size limit.'])
async def test_file_metadata_with_description_filename(prepare_sound, testing_description_name):
    description_filename_index = 340
    max_dimension = 169

    client = ClientSoundCard(prepare_sound(2, 4, 96000, 1))
    client.prepare_header(with_data=True, with_file_metadata=True)

    client.add_description_filename(testing_description_name)

    metadata_filename_on_header = client.filemetadata[description_filename_index: description_filename_index + max_dimension]
    as_str = metadata_filename_on_header.tobytes().strip(b'\0')
    assert testing_description_name[:max_dimension] == "".join(map(chr, as_str))
 