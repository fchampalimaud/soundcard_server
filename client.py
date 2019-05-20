import asyncio
import numpy as np

from pybpod_soundcard_module.utils.generate_sound import generate_sound, WindowConfiguration

@asyncio.coroutine
def tcp_send_sound_client(loop):
    reader, writer = yield from asyncio.open_connection('localhost', 9999,
                                                        loop=loop)

    # generate sound
    window_config = WindowConfiguration( left_duration = 0,
                                     left_apply_window_start = True,
                                     left_apply_window_end = False,
                                     left_window_function = 'Blackman',
                                     right_duration = 0.1,
                                     right_apply_window_start = False,
                                     right_apply_window_end = True,
                                     right_window_function = 'Bartlett')

    wave_int = generate_sound(fs=96000,                 # sample rate in Hz
                              duration=4,               # duration of the sound in seconds
                              frequency_left=1500,      # frequency of the sinusoidal signal generated in Hz for the left channel
                              frequency_right=1200,     # frequency of the sinusoidal signal generated in Hz for the right channel
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
    header = np.zeros(preamble_size + metadata_size + data_chunk_size + file_metadata_size + checksum_size, dtype=np.uint8)
    header[:preamble_size] = [2, 255, int('0x10', 16), int('0x88', 16), 128, 255, 1 ]

    print(header[:preamble_size])

    # TODO: prepare rest of first request according to the protocol before sending anything
    # TODO: this should be extracted from here
    # add metadata information to header


    # add first block of data to header
    header[preamble_size + metadata_size:preamble_size + metadata_size + data_chunk_size] = wave_int8[:data_chunk_size]

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
        # TODO: for the last command_to_send, we should clear all data so that the remaining of the 32kb 
        #       of data is empty instead of data from the last command
        if i == commands_to_send - 2:
            data_cmd[data_cmd_data_index:] = 0
        data_cmd[data_cmd_data_index: data_cmd_data_index + len(data_block)] = data_block

        # sum all bytes as a byte and save that in the last index as the checksum
        data_cmd[-1] = data_cmd.sum(dtype=np.int8)
        print(f'checksum idx: {i}, {data_cmd[-1].view(np.uint8)}')

        # NOTE: on the last chunk, which is smaller, for some reason, it is trying to send 32780 bytes instead of 32768
        # write to socket
        writer.write(bytes(data_cmd))




    print('Close the socket')
    writer.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(tcp_send_sound_client(loop))
loop.close()
