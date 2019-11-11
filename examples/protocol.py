import numpy as np


class Protocol(object):
    """
    Harp Protocol implementation for the Sound Card.
    For more details, please check the Harp Protocol for the Sound Card commands in:
    https://bitbucket.org/fchampalimaud/device.soundcard/src/master/TCP%20server%20protocol.txt
    """
    def __init__(self, wave_int):
        self.wave_int8 = wave_int.view(np.int8)
        self.int32_size = np.dtype(np.int32).itemsize

        # get number of commands to send
        self.sound_file_size_in_samples = len(self.wave_int8) // 4
        self.commands_to_send = int(self.sound_file_size_in_samples * 4 // 32768 + (
            1 if ((self.sound_file_size_in_samples * 4) % 32768) != 0 else 0))

    def prepare_header(self, with_data=True, with_file_metadata=True):
        """
        This method initializes the data containers with the appropriate dimensions according to the parameters passed.
        This results in the three different supported types of commands.

        :param with_data: If the first 32kb block of data is to be included in the first command message or not.
        :param with_file_metadata: If extra information regarding the sound is to be included.
        """
        self._metadata_size = 16
        self._data_block_size = 32768
        self._file_metadata_size = 2048
        checksum_size = 1

        self._metadata_index = 5 if with_file_metadata is False else 7
        self._preamble_size = self._metadata_index

        self._data_index = self._metadata_index + self._metadata_size
        self._filemetadata_index = self._metadata_index + self._metadata_size + self._data_block_size

        if with_file_metadata is True:
            if with_data is True:
                self.header = np.zeros(self._metadata_index + self._metadata_size + self._data_block_size + self._file_metadata_size + checksum_size, dtype=np.int8)
                self.header[:self._metadata_index] = [2, 255, int('0x10', 16), int('0x88', 16), 128, 255, 1]
            else:
                self.header = np.zeros(self._metadata_index + self._metadata_size + self._file_metadata_size + checksum_size, dtype=np.int8)
                self.header[:self._metadata_index] = [2, 255, int('0x14', 16), int('0x08', 16), 129, 255, 1]
        else:
            self.header = np.zeros(self._metadata_index + self._metadata_size + checksum_size, dtype=np.int8)
            self.header[:self._metadata_index] = [2, 20, 130, 255, 1]

        self.filemetadata = np.zeros(2048, dtype=np.int8)

        # prepare data_cmd
        self.data_cmd = np.zeros(7 + self.int32_size + 32768 + 1, dtype=np.int8)
        self._data_cmd_data_index = 7
        self._data_cmd_data_block_index = self._data_cmd_data_index + self.int32_size
        # add data_cmd header
        self.data_cmd[:self._data_cmd_data_index] = [2, 255, int('0x04', 16), int('0x80', 16), 132, 255, 132]

    def add_sound_filename(self, sound_filename: str):
        """
        Adds the sound filename to the filemetadata. This will truncate the name if it is longer than 169 bytes

        :param sound_filename:
        """
        self._add_filemetadata_info(sound_filename, 0, 169)

    def add_metadata_filename(self, metadata_filename: str):
        """
        Adds the metadata filename to the filemetadata. This will truncate the name if it is longer than 169 bytes

        :param metadata_filename:
        """
        self._add_filemetadata_info(metadata_filename, 170, 169)

    def add_description_filename(self, description_filename: str):
        """
        Adds the description filename to the filemetadata. This will truncate the name if it is longer than 169 bytes

        :param description_filename:
        """
        self._add_filemetadata_info(description_filename, 340, 169)

    def add_metadata_filename_content(self, metadata_filename_content: str):
        """
        Adds the content of the metadata filename to the filemetadata. This will truncate the name if it is longer than
        1023 bytes

        :param metadata_filename_content:
        """
        self._add_filemetadata_info(metadata_filename_content, 512, 1023)

    def add_description_filename_content(self, description_filename_content: str):
        """
        Adds the content of the description filename to the filemetadata. This will truncate the name if it is longer than
        511 bytes
        :param description_filename_content:
        """
        self._add_filemetadata_info(description_filename_content, 1536, 511)

    def add_metadata(self, metadata):
        """
        Adds the metadata of the sound to the first command message.
        The accepted information comes in the form of a list with
        [sound_index, sound_file_size_in_samples, sample_rate, data_type]

        :param list metadata: The metadata information in a list form
        """
        self.header[self._metadata_index: self._metadata_index + self._metadata_size] = np.array(metadata, dtype=np.int32).view(np.int8)

    def add_filemetadata(self):
        """
        Adds the filemetadata to the first command being sent to the server.
        The execution of this method assumes that the related methods for the filemetadata information were already
        called. Those methods are: 'add_sound_filename', 'add_metadata_filename', 'add_description_filename',
        'add_metadata_filename_content' and 'add_description_filename_content'
        """
        if self._metadata_index == 5:
            return
        self.header[self._filemetadata_index: self._filemetadata_index + self._file_metadata_size] = self.filemetadata

    def add_first_data_block(self):
        """
        Adds the first block of data to the first command being sent to the server.
        .. note:: If when preparing the header the first command wasn't part of the first command, this method call
        won't do anything
        """
        if self._metadata_index == 5:
            return
        self.header[self._data_index: self._data_index + self._data_block_size] = self.wave_int8[:self._data_block_size]

    def update_header_checksum(self):
        """
        Updates the message's checksum
        """
        self.header[-1] = self.header.sum()

    def write_data_index(self, index):
        self.data_cmd[self._data_cmd_data_index: self._data_cmd_data_index + self.int32_size] = np.array([index], dtype=np.int32).view(np.int8)

    def clean_data_cmd(self):
        """
        Clears the data command information with 0.
        """
        self.data_cmd[self._data_cmd_data_index:] = 0

    def write_data_block(self, index):
        """
        Writes data block to the data command message
        :param index: Index of the data block from the sound data container
        """
        # write data from wave_int to cmd
        wave_idx = index * 32768
        data_block = self.wave_int8[wave_idx: wave_idx + 32768]

        self.data_cmd[self._data_cmd_data_block_index: self._data_cmd_data_block_index + len(data_block)] = data_block

    def update_data_checksum(self):
        """
        Updates the data command checksum
        """
        self.data_cmd[-1] = self.data_cmd[:-1].sum(dtype=np.int8)

    def _add_filemetadata_info(self, data_str, start_index, max_value):
        """
        Adds the 'data_str' information to the filemetadata, using the 'start_index' and 'max_value' as limits.
        .. note:: If the contents of data_str are larger than what is defined by the parameters, data will be truncated.
        :param data_str: The data content to be added
        :param start_index: The start index where data will be written
        :param max_value: The upper limit
        """
        data_to_save = bytearray()
        data_to_save.extend(map(ord, data_str))
        data_size = len(data_to_save) if len(data_to_save) < max_value else max_value
        self.filemetadata[start_index: start_index + data_size] = data_to_save[:data_size]

    def convert_timestamp(self, data: bytes):
        """
        Gets the timestamp as per the Harp protocol.
        :param data:
        :return:
        """
        data = np.frombuffer(data, dtype=np.int8)

        integer = data[:4].view(np.uint32)
        dec = data[4:].view(np.uint16)

        res = integer + (dec * 10.0**-6 * 32)
        return res
