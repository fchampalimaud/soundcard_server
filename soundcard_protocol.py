import numpy as np


class SoundCardHarpProtocol(object):

    def __init__(self, wave_int):
        self.wave_int8 = wave_int.view(np.int8)
        self.int32_size = np.dtype(np.int32).itemsize

        # get number of commands to send
        self.sound_file_size_in_samples = len(self.wave_int8) // 4
        self.commands_to_send = int(self.sound_file_size_in_samples * 4 // 32768 + (
            1 if ((self.sound_file_size_in_samples * 4) % 32768) != 0 else 0))

    def prepare_header(self, with_data=True, with_file_metadata=True):
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
        self._add_filemetadata_info(sound_filename, 0, 169)

    def add_metadata_filename(self, metadata_filename: str):
        self._add_filemetadata_info(metadata_filename, 170, 169)

    def add_description_filename(self, description_filename: str):
        self._add_filemetadata_info(description_filename, 340, 169)

    def add_metadata_filename_content(self, metadata_filename_content: str):
        self._add_filemetadata_info(metadata_filename_content, 512, 1023)

    def add_description_filename_content(self, description_filename_content: str):
        self._add_filemetadata_info(description_filename_content, 1536, 511)
        pass

    def add_metadata(self, metadata):
        self.header[self._metadata_index: self._metadata_index + self._metadata_size] = np.array(metadata, dtype=np.int32).view(np.int8)

    def add_filemetadata(self):
        self.header[self._filemetadata_index: self._filemetadata_index + self._file_metadata_size] = self.filemetadata

    def add_first_data_block(self):
        if self._metadata_index == 5:
            return
        self.header[self._data_index: self._data_index + self._data_block_size] = self.wave_int8[:self._data_block_size]

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

        self.data_cmd[self._data_cmd_data_block_index: self._data_cmd_data_block_index + len(data_block)] = data_block

    def update_data_checksum(self):
        self.data_cmd[-1] = self.data_cmd[:-1].sum(dtype=np.int8)

    def _add_filemetadata_info(self, data_str, start_index, max_value):
        data_to_save = bytearray()
        data_to_save.extend(map(ord, data_str))
        data_size = len(data_to_save) if len(data_to_save) < max_value else max_value
        self.filemetadata[start_index: start_index + data_size] = data_to_save[:data_size]