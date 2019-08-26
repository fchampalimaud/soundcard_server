import asyncio
import time

from .protocol import Protocol
from .communication import Communication
from .tools import WindowConfiguration, generate_sound


async def tcp_send_sound_client(loop):
    sound_index = 4
    duration = 12
    sample_rate = 96000
    data_type = 0

    # define a WindowConfiguration to be applied to the generated sound in the next step
    window_config = WindowConfiguration(left_duration=0,
                                        left_apply_window_start=True,
                                        left_apply_window_end=False,
                                        left_window_function='Blackman',
                                        right_duration=0.01,
                                        right_apply_window_start=False,
                                        right_apply_window_end=True,
                                        right_window_function='Bartlett')

    # generate the sound
    wave_int = generate_sound(fs=sample_rate,                 # sample rate in Hz
                              duration=duration,              # duration of the sound in seconds
                              frequency_left=1500,            # frequency of the sinusoidal signal generated in Hz for the left channel
                              frequency_right=1200,           # frequency of the sinusoidal signal generated in Hz for the right channel
                              window_configuration=window_config
                              )

    # initialize the Protocol with the data from the generate_sound
    # (use your own functions to generate your binary sounds if you need something different)
    protocol = Protocol(wave_int)
    # prepare header (it will define the size of the first command that will be sent to the Sound Card)
    protocol.prepare_header(with_data=True, with_file_metadata=True)
    # add the metadata information regarding the sound and which index will the sound be written to
    protocol.add_metadata([sound_index, protocol.sound_file_size_in_samples, sample_rate, data_type])

    # initialize communication
    comm = Communication(protocol, loop)
    await comm.open()

    initial_time = time.time()

    # start creating message to send according to the protocol
    # NOTE: if on calling prepare_header with_file_metadata was False, the next elements aren't required
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

    # NOTE: These two methods are required depending on the parameters given to the 'prepare_header' Protocol method
    protocol.add_filemetadata()
    protocol.add_first_data_block()

    # force the calculation of the checksum
    protocol.update_header_checksum()

    # send header to server
    comm.send_header(protocol.header)

    # receive reply
    reply = await comm.get_reply()

    # if reply is an error, simply return (ou maybe try again would be more adequate)
    if reply[0] != 2:
        return

    # ex. gets the timestamp as per the Harp protocol to verify timings if you wish
    timestamp = protocol.convert_timestamp(reply[5: 5 + 6])

    # send rest of data
    print(f'Sending...')
    # Communication.send_sound calculates the duration that it took to send each packet
    packet_sending_timings = await comm.send_sound()

    msg = await comm.get_final_reply()

    # wait for the server's response after sending everything
    if msg == b'OK':
        total_time = (time.time() - initial_time)
        bandwidth = (((32768 * len(packet_sending_timings)) / total_time) * 8) / 2**20
        print(f'Elapsed time: {int(round(total_time * 1000))} ms')
        print(f'Bandwidth: {round(bandwidth, 1)} Mbit/s')

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(tcp_send_sound_client(loop))
    loop.close()
