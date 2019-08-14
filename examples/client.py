import asyncio
import time
import numpy as np

from tools import generate_sound, WindowConfiguration
from protocol import Protocol


async def tcp_send_sound_client(loop):
    reader, writer = await asyncio.open_connection('localhost', 9999, loop=loop)

    sound_index = 4
    duration = 12
    sample_rate = 96000
    data_type = 0

    # generate sound
    window_config = WindowConfiguration(left_duration=0,
                                        left_apply_window_start=True,
                                        left_apply_window_end=False,
                                        left_window_function='Blackman',
                                        right_duration=0.01,
                                        right_apply_window_start=False,
                                        right_apply_window_end=True,
                                        right_window_function='Bartlett')

    wave_int = generate_sound(fs=sample_rate,                 # sample rate in Hz
                              duration=duration,              # duration of the sound in seconds
                              frequency_left=1500,            # frequency of the sinusoidal signal generated in Hz for the left channel
                              frequency_right=1200,           # frequency of the sinusoidal signal generated in Hz for the right channel
                              window_configuration=window_config
                              )

    protocol = Protocol(wave_int)
    protocol.prepare_header(with_data=True, with_file_metadata=True)
    protocol.add_metadata([sound_index, protocol.sound_file_size_in_samples, sample_rate, data_type])

    # with open('testing9secs.bin', 'wb') as f:
    #        wave_int8.tofile(f)

    initial_time = time.time()

    # start creating message to send according to the protocol
    sound_filename_str = 'my_sound_filename.bin'
    metadata_filename_str = 'my_metadata_filename.bin'
    description_filename_str = 'my_description_filename.txt'

    metadata_filename_content_str = 'metadata content (can be binary)'
    description_filename_content_str = 'my sound is the best'

    protocol.add_sound_filename(sound_filename_str)
    protocol.add_metadata_filename(metadata_filename_str)
    protocol.add_description_filename(description_filename_str)

    protocol.add_metadata_filename_content(metadata_filename_content_str)
    protocol.add_description_filename_content(description_filename_content_str)

    protocol.add_filemetadata()
    protocol.add_first_data_block()
    protocol.update_header_checksum()

    # send header
    writer.write(bytes(protocol.header))

    start = time.time()

    # receive reply
    reply_size = 5 + 6 + 1
    reply = await reader.readexactly(reply_size)

    # if reply is an error, simply return (ou maybe try again would be more adequate)
    if reply[0] != 2:
        return

    timestamp = protocol.convert_timestamp(reply[5: 5 + 6])
    # send rest of data
    packet_sending_timings = []

    # get number of commands to send
    commands_to_send = protocol.commands_to_send

    print(f'Number of packets to send: {commands_to_send}')
    print(f'Sending...')

    for i in range(1, commands_to_send):
        # clean the remaining elements for the last packet which might be smaller than 32K
        if i == commands_to_send - 1:
            protocol.clean_data_cmd()

        protocol.write_data_index(i)
        protocol.write_data_block(i)
        protocol.update_data_checksum()

        start = time.time()

        # write to socket
        writer.write(bytes(protocol.data_cmd))

        # to guarantee that the buffer is not getting filled completely. It will continue immediately if there's still space in the buffer
        await writer.drain()

        # receive ok
        reply_size = 5 + 6 + 1
        reply = await reader.readexactly(reply_size)

        packet_sending_timings.append(time.time() - start)

        timestamp = protocol.convert_timestamp(reply[5: 5 + 6])

        if reply[0] != 2:
            return

    writer.write_eof()

    msg = await reader.readexactly(2)
    if msg == b'OK':
        print(f'Mean time for sending each packet: {round(np.mean(packet_sending_timings) * 1000, 2)} ms')
        total_time = (time.time() - initial_time)
        bandwidth = (((32768 * len(packet_sending_timings)) / total_time) * 8) / 2**20
        print(f'Bandwidth: {round(bandwidth, 1)} Mbit/s')
        print(f'Elapsed time: {int(round(total_time * 1000))} ms')
        print('Transfer completed successfully.')

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(tcp_send_sound_client(loop))
    loop.close()
