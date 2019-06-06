import asyncio
import numpy as np

from pybpod_soundcard_module.utils.generate_sound import generate_sound, WindowConfiguration

def add_filemetadata_info(filemetadata, data_str, start_index, max_value):
    data_array = np.array(data_str, 'c').view(dtype=np.int8)
    data_size = min(len(data_array), max_value)
    filemetadata[start_index: start_index + data_size] = data_array[:data_size]


async def tcp_send_sound_client(loop):
    reader, writer = await asyncio.open_connection('localhost', 9999, loop=loop)

    sound_index = 2
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
    metadata = np.array([sound_index, sound_file_size_in_samples, sample_rate, data_type], dtype=np.int32)
    header[preamble_size: preamble_size + metadata_size] = metadata.view(np.int8)

    filemetadata_index = preamble_size + metadata_size + data_chunk_size
    filemetadata = np.zeros(2048, dtype=np.int8)

    sound_filename_str = 'testing_filename'
    metadata_filename_str = 'testing_metadata_name'
    description_filename_str = 'testing_description_name'
    metadata_filename_content_str = 'testing_content_from_metadata_filename'
    description_filename_content_str = 'testing_content_from_description_filename'

    add_filemetadata_info(filemetadata, sound_filename_str, 0, 169)
    add_filemetadata_info(filemetadata, metadata_filename_str, 170, 169)
    add_filemetadata_info(filemetadata, description_filename_str, 340, 169)
    add_filemetadata_info(filemetadata, metadata_filename_content_str, 512, 1023)
    add_filemetadata_info(filemetadata, description_filename_content_str, 1536, 511)

    # add filemetadata to header
    header[filemetadata_index: filemetadata_index + file_metadata_size] = filemetadata

    # add first block of data to header
    header[preamble_size + metadata_size:preamble_size + metadata_size + data_chunk_size] = wave_int8[:data_chunk_size]
    # calculate checksum and add it to the frame
    header[-1] = header.sum()

    # send preamble first
    writer.write(bytes(header[:preamble_size]))

    # send remaining of the header
    writer.write(bytes(header[preamble_size:]))

    # receive ok
    reply_size = 5 + 6 + 1
    reply = await reader.readexactly(reply_size)
    print(reply)

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

        # to guarantee that the buffer is not getting filled completely. It will continue immediately if there's still space in the buffer
        await writer.drain()

    writer.write_eof()

    msg = await reader.readexactly(2)
    if msg == b'OK':
        print('Data successfully sent!')

loop = asyncio.get_event_loop()
loop.run_until_complete(tcp_send_sound_client(loop))
loop.close()
