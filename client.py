import asyncio
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

    # start creating message to send according to the protocol
    


    message = 4
    print(message.to_bytes(4, byteorder="little"))
    writer.write(message.to_bytes(4, byteorder="little"))

    message = b'1234'
    writer.write(bytes(message))

    print('Close the socket')
    writer.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(tcp_send_sound_client(loop))
loop.close()
