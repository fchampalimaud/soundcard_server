import asyncio
import time
import numpy as np

from generate_sound import generate_sound, WindowConfiguration


class ClientSoundCard(object):

    def __init__(self, wave_int):
        self.wave_int8 = wave_int.view(np.int8)
        self.int32_size = np.dtype(np.int32).itemsize

        # get number of commands to send
        self.sound_file_size_in_samples = len(self.wave_int8) // 4
        self.commands_to_send = int(self.sound_file_size_in_samples * 4 // 32768 + (
            1 if ((self.sound_file_size_in_samples * 4) % 32768) is not 0 else 0))
    
    def prepare_header(self, with_data=True, with_file_metadata=True):
        # TODO: change this according to the parameters
        self._metadata_size = 16
        self._data_chunk_size = 32768
        self._file_metadata_size = 2048
        checksum_size = 1
       
        self._metadata_index = 5 if with_data == False and with_file_metadata == False else 7
        self._preamble_size = self._metadata_index

        self._data_index = self._metadata_index + self._metadata_size
        self._filemetadata_index = self._metadata_index + self._metadata_size + self._data_chunk_size

        if with_data == True and with_file_metadata == True:
            self.header = np.zeros(self._metadata_index + self._metadata_size + self._data_chunk_size + self._file_metadata_size + checksum_size, dtype=np.int8)
            self.header[:self._metadata_index] = [2, 255, int('0x10', 16), int('0x88', 16), 128, 255, 1 ]
        elif with_data == False and with_file_metadata == True:
            self.header = np.zeros(self._metadata_index + self._metadata_size + self._file_metadata_size + checksum_size, dtype=np.int8)
            self.header[:self._metadata_index] = [2, 255, int('0x14', 16), int('0x08', 16), 129, 255, 1 ]
        elif with_data == False and with_file_metadata == False:
            self.header = np.zeros(self._metadata_index + self._metadata_size + checksum_size, dtype=np.int8)
            self.header[:self._metadata_index] = [2, 20, 130, 255, 1]

        self.filemetadata = np.zeros(2048, dtype=np.int8)

        # prepare data_cmd
        self.data_cmd = np.zeros(7 + self.int32_size + 32768 + 1, dtype=np.int8)
        self._data_cmd_data_index = 7
        self._data_cmd_data_chunk_index = self._data_cmd_data_index + self.int32_size
        # add data_cmd header
        self.data_cmd[:self._metadata_index] = [2, 255, int('0x04', 16), int('0x80', 16), 132, 255, 132]

    # TODO: perhaps instead of having these methods here we might create a new class
    def add_sound_filename(self, sound_filename):
        # TODO: confirm or force conversion to string
        self._add_filemetadata_info(sound_filename, 0, 169)
    
    def add_metadata_filename(self, metadata_filename):
        # TODO: confirm or force conversion to string
        self._add_filemetadata_info(metadata_filename, 170, 169)
        

    def add_description_filename(self, description_filename):
        # TODO: confirm or force conversion to string and truncate
        self._add_filemetadata_info(description_filename, 340, 169)

    def add_metadata_filename_content(self, metadata_filename_content):
        # TODO: confirm or force conversion to string and truncate
        self._add_filemetadata_info(metadata_filename_content, 512, 1023)
        
    def add_description_filename_content(self, description_filename_content):
        # TODO: confirm or force conversion to string and truncate
        self._add_filemetadata_info(description_filename_content, 1536, 511)
        pass

    def add_metadata(self, metadata):
        self.header[self._metadata_index: self._metadata_index + self._metadata_size] = np.array(metadata, dtype=np.int32).view(np.int8)

    def add_filemetadata(self):
        self.header[self._filemetadata_index: self._filemetadata_index + self._file_metadata_size] = self.filemetadata

    def add_first_data_block(self):
        self.header[self._data_index: self._data_index + self._data_chunk_size] = self.wave_int8[:self._data_chunk_size]

    def update_header_checksum(self):
        self.header[-1] = self.header.sum()

    def write_data_index(self, index):
        self.data_cmd[self._data_cmd_data_index: self._data_cmd_data_index + self.int32_size] = np.array([index], dtype=np.int32).view(np.int8)

    def clean_data_cmd(self):
        self.data_cmd[self._data_cmd_data_index:] = 0
    
    def write_data_block(self, index):
        # write data from wave_int to cmd
        wave_idx = index * 32768
        data_block = self.wave_int8[wave_idx: wave_idx + 32768]

        self.data_cmd[self._data_cmd_data_index: self._data_cmd_data_index + len(data_block)] = data_block

    def update_data_checksum(self):
        self.data_cmd[-1] = self.data_cmd[:-1].sum(dtype=np.int8)

    def _add_filemetadata_info(self, data_str, start_index, max_value):
        data_array = np.array(data_str, 'c').view(dtype=np.int8)
        data_size = min(len(data_array), max_value)
        self.filemetadata[start_index: start_index + data_size] = data_array[:data_size]



def convert_timestamp(data: bytes):
    data = np.frombuffer(data, dtype=np.int8)

    integer = data[:4].view(np.uint32)
    dec = data[4:].view(np.uint16)

    res = integer + (dec * 10.0**-6 * 32)
    return res

async def tcp_send_sound_client(loop):
    reader, writer = await asyncio.open_connection('localhost', 9999, loop=loop)

    sound_index = 4
    duration = 8
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

    client = ClientSoundCard(wave_int)
    client.prepare_header(with_data=True, with_file_metadata=True)
    client.add_metadata([sound_index, client.sound_file_size_in_samples, sample_rate, data_type])

    #with open('testing9secs.bin', 'wb') as f:
    #        wave_int8.tofile(f)

    initial_time = time.time()

    # start creating message to send according to the protocol
    sound_filename_str = 'testing_filename'
    metadata_filename_str = 'testing_metadata_name'
    description_filename_str = 'testing_description_name'
    metadata_filename_content_str = 'testing_content_from_metadata_filename'
    description_filename_content_str = 'testing_content_from_description_filename'

    client.add_sound_filename(sound_filename_str)
    client.add_metadata_filename(metadata_filename_str)
    client.add_description_filename(description_filename_str)
    client.add_metadata_filename_content( metadata_filename_content_str)
    client.add_description_filename_content(description_filename_content_str)

    client.add_filemetadata()
    client.add_first_data_block()
    client.update_header_checksum()

    #send header
    writer.write(bytes(client.header))

    print(f'Start timing between writing complete header and getting reply from server')
    start = time.time()

    # receive reply
    reply_size = 5 + 6 + 1
    reply = await reader.readexactly(reply_size)

    # TODO: check for error
    
    print(f'Received reply from server after writing complete header. timing: {time.time() - start}')

    timestamp = convert_timestamp(reply[5: 5 + 6])

    # if reply is an error, simply return (ou maybe try again would be more adequate)
    if reply[0] is not 2:
        return

    # send rest of data
    chunk_sending_timings = []

    # get number of commands to send
    commands_to_send = client.commands_to_send

    print(f'chunks to send: {commands_to_send}')
    print(f'Sending...')

    for i in range(1, commands_to_send):
        # clean the remaining elements for the last chunk which might be smaller than 32K
        if i == commands_to_send - 1:
            client.clean_data_cmd()

        client.write_data_index(i)
        client.write_data_block(i)
        client.update_data_checksum()

        start = time.time()

        # write to socket
        writer.write(bytes(client.data_cmd))

        # to guarantee that the buffer is not getting filled completely. It will continue immediately if there's still space in the buffer
        await writer.drain()

        # receive ok
        reply_size = 5 + 6 + 1
        reply = await reader.readexactly(reply_size)
        
        chunk_sending_timings.append(time.time() - start)

        timestamp = convert_timestamp(reply[5: 5 + 6])

        #FIXME: if reply is an error, simply return (ou maybe try again would be more adequate)
        if reply[0] is not 2:
            return


    writer.write_eof()

    msg = await reader.readexactly(2)
    if msg == b'OK':
        print('Data successfully sent!')

    print(f'total time to send file: {time.time() - initial_time}')
    print(f'chunks_sending_timings median: {np.median(chunk_sending_timings)}')
    print(f'chunks_sending_timings average: {np.mean(chunk_sending_timings)}')

loop = asyncio.get_event_loop()
loop.run_until_complete(tcp_send_sound_client(loop))
loop.close()
