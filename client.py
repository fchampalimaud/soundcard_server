import asyncio
import numpy as np

from pybpod_soundcard_module.utils.generate_sound import generate_sound, WindowConfiguration

@asyncio.coroutine
def tcp_send_sound_client(loop):
    reader, writer = yield from asyncio.open_connection('localhost', 9999,
                                                        loop=loop)

    sound_index = 4
    duration = 4
    sample_rate = 96000
    data_type = 0

    # generate sound
    window_config = WindowConfiguration( left_duration = 0,
                                     left_apply_window_start = True,
                                     left_apply_window_end = False,
                                     left_window_function = 'Blackman',
                                     right_duration = 0.1,
                                     right_apply_window_start = False,
                                     right_apply_window_end = True,
                                     right_window_function = 'Bartlett')

    wave_int = generate_sound(fs=sample_rate,                 # sample rate in Hz
                              duration=duration,              # duration of the sound in seconds
                              frequency_left=1500,            # frequency of the sinusoidal signal generated in Hz for the left channel
                              frequency_right=1200,           # frequency of the sinusoidal signal generated in Hz for the right channel
                              window_configuration=window_config
                              )

    int32_size = np.dtype(np.int32).itemsize
    # work with a int8 view of the wave_int (which is int32)
    wave_int8 = wave_int.view(np.int8)

    # get number of commands to send
    sound_file_size_in_samples = len(wave_int8) // 4
    commands_to_send = int(sound_file_size_in_samples * 4 // 32768 + (
        1 if ((sound_file_size_in_samples * 4) % 32768) is not 0 else 0))

    # start creating message to send according to the protocol
    preamble_size = 7
    metadata_size = 16
    data_chunk_size = 32768
    file_metadata_size = 2048
    checksum_size = 1
    header = np.zeros(preamble_size + metadata_size + data_chunk_size + file_metadata_size + checksum_size, dtype=np.int8)
    header[:preamble_size] = [2, 255, int('0x10', 16), int('0x88', 16), 128, 255, 1 ]

    # TODO: this should be extracted from here
    metadata = np.array([sound_index, duration, sample_rate, data_type ], dtype=np.int32)
    header[preamble_size: preamble_size + metadata_size] = metadata.view(np.int8)

    filemetadata_index = preamble_size + metadata_size + data_chunk_size
    filemetadata = np.zeros(2048, dtype=np.int8)
    sound_filename = np.array('testing_filename', 'c').view(dtype=np.int8)
    sound_filename_size = len(sound_filename) if len(sound_filename) < 169 else 169
    filemetadata[0:sound_filename_size] = sound_filename

    metadata_filename = np.array('testing_metadata_name', 'c').view(dtype=np.int8)
    metadata_filename_size = len(metadata_filename) if len(metadata_filename) < 169 else 169
    filemetadata[170:170 + metadata_filename_size] = metadata_filename

    description_filename = np.array('testing_description_name', 'c').view(dtype=np.int8)
    description_filename_size = len(description_filename) if len(description_filename) < 169 else 169
    filemetadata[340:340 + description_filename_size] = description_filename

    metadata_filename_content = np.array('testing_content_from_metadata_filename', 'c').view(dtype=np.int8)
    metadata_filename_content_size = len(metadata_filename_content) if len(metadata_filename_content) < 1023 else 1023
    filemetadata[512:512 + metadata_filename_content_size] = metadata_filename_content

    description_filename_content = np.array('testing_content_from_description_filename', 'c').view(dtype=np.int8)
    description_filename_content_size = len(description_filename_content) if len(description_filename_content) < 511 else 511
    filemetadata[1536:1536 + description_filename_content_size] = description_filename_content

    header[filemetadata_index: filemetadata_index + file_metadata_size] = filemetadata

    # add first block of data to header
    header[preamble_size + metadata_size:preamble_size + metadata_size + data_chunk_size] = wave_int8[:data_chunk_size]
    # calculate checksum and add it to the frame
    header[-1] = header.sum()

    # send preamble first
    writer.write(bytes(header[:preamble_size]))

    # send remaining of the header
    writer.write(bytes(header[preamble_size:]))

    # send rest of data
    # prepare data_cmd
    data_cmd = np.zeros(7 + int32_size + 32768 + 1, dtype=np.int8)
    data_cmd_data_index = 7
    # add data_cmd header
    data_cmd[:preamble_size] = [2, 255, int('0x04', 16), int('0x80', 16), 132, 255, 132]

    for i in range(1, commands_to_send):
        # write dataIndex
        data_cmd[7: 7 + int32_size] = np.array([i], dtype=np.int32).view(np.int8)

        # write data from wave_int to cmd
        wave_idx = i * 32768
        data_block = wave_int8[wave_idx: wave_idx + 32768]

        # clean the remaining elements for the last chunk which might be smaller than 32K
        if i == commands_to_send - 1:
            data_cmd[data_cmd_data_index:] = 0
        data_cmd[data_cmd_data_index: data_cmd_data_index + len(data_block)] = data_block

        # clean last byte so we can calculate the correct checksum
        data_cmd[-1] = 0
        # sum all bytes with overflow to calculate the checksum
        data_cmd[-1] = data_cmd.sum(dtype=np.int8)

        # write to socket
        writer.write(bytes(data_cmd))

    print('Close the socket')
    writer.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(tcp_send_sound_client(loop))
loop.close()
