import os
import asyncio
import array
import usb.core
import usb.util
from usb.backend import libusb1 as libusb
import time
import math
import numpy as np
from asyncio import IncompleteReadError
from tqdm import tqdm


class SoundCardTCPServer(object):

    def __init__(self, addr, port):
        self.address = addr
        self.port = port

    async def start_server(self):
        # init connection to soundcard through the usb connection
        if self.open() is False:
            print(f'Error while trying to connect to the Harp sound card. Please make sure it is connected to the computer and try again.')
            return

        self.init_data()

        # Start server to listen for incoming requests
        asrv = await asyncio.start_server(self._handle_request, self.address, int(self.port))
        print('SoundCardTCPServer started and waiting for requests')
        while True:
            await asyncio.sleep(10)

    def open(self):
        print('Opening USB connection')
        backend = libusb.get_backend()
        # backend = libusb.get_backend(find_library=lambda x: "libusb-1.0.dll")
        self._dev = usb.core.find(backend=backend, idVendor=0x04d8, idProduct=0xee6a)
        if self._dev is None:
            return False

        print(f'backend used: {self._dev.backend}')
        if self._dev is None:
            print('SoundCard not found. Please connect it to the USB port before proceeding.')
        else:
            # set the active configuration. With no arguments, the first configuration will be the active one
            # note: some devices reset when setting an already selected configuration so we should check for it before
            _cfg = self._dev.get_active_configuration()
            if _cfg is None or _cfg.bConfigurationValue != 1:
                self._dev.set_configuration(1)
            usb.util.claim_interface(self._dev, 0)

        return True

    def restart(self):
        print('Restarting USB connection')
        self.close()
        self.open()

    def reset(self):
        """
        Resets the device, waits 700ms and tries to connect again so that the current instance of the SoundCard object can still be used.
        :note Necessary at the moment after sending a sound
        """
        print('Resetting device')
        if not self._dev:
            raise Exception("Sound card might not be connected. Please connect it before any operation.")

        # Reset command length:    'c' 'm' 'd' '0x88' + 'f'
        reset_cmd = [ord('c'), ord('m'), ord('d'), 0x88, ord('f')]
        # cmd = 'cmd' + chr(0x88) + 'f'
        wrt = self._dev.write(1, reset_cmd, 100)
        assert wrt == len(reset_cmd)

        time.sleep(700.0 / 1000.0)
        self.open()

    def close(self):
        print('Closing USB connection')
        # close usb connection
        if self._dev:
            usb.util.dispose_resources(self._dev)

    def init_data(self):
        # prepare message to reply to client (5 bytes for preamble, 6 bytes for timestamp and 1 for checksum)
        self._reply = np.zeros(5 + 6 + 1, dtype=np.int8)
        # prepare with 'ok' reply by default
        self._reply[:5] = np.array([2, 10, 128, 255, 16], dtype=np.int8)

        int32_size = np.dtype(np.int32).itemsize
        # prepare command to send and to receive
        # Data command length:     'c' 'm' 'd' '0x81' + random + dataIndex + 32768 + 'f'
        package_size = 4 + int32_size + int32_size + 32768 + 1
        # align = 64
        # padding = (align - (package_size % align)) % align

        self._data_cmd = np.zeros(package_size, dtype=np.int8)
        data_cmd_data_index = 4 + int32_size + int32_size

        self._data_cmd[0] = ord('c')
        self._data_cmd[1] = ord('m')
        self._data_cmd[2] = ord('d')
        self._data_cmd[3] = 0x81
        # self._data_cmd[package_size - 1] = ord('f')
        self._data_cmd[-1] = ord('f')

        # Data command reply:     'c' 'm' 'd' '0x81' + random + error
        self._data_cmd_reply = array.array('b', [0] * (4 + int32_size + int32_size))

    def clear_data(self):
        # FIXME: temporary, this should be changed according to the needs
        self.init_data()

    async def _handle_request(self, reader, writer):
        addr = writer.get_extra_info('peername')

        print(f'Request received from {addr}. Handling received data.')
        msg = await self._recv_data(writer, reader)

    async def _recv_data(self, writer, stream):
        start = initial_time = time.time()

        with_data = True
        with_file_metadata = True

        # get first 7 bytes to know which type of frame we are going to receive
        preamble_size = 7
        preamble_bytes = await stream.readexactly(preamble_size)

        # size of header will depend on preamble data (index 4 defines type of frame)
        frame_type = preamble_bytes[4]
        header_size = 7 + 16 + 1
        metadata_index = 7
        if frame_type == 128:
            header_size += 32768 + 2048
        elif frame_type == 129:
            header_size += 2048
            with_data = False
        elif preamble_bytes[2] == 130:
            header_size = 22
            metadata_index = 5
            with_data = False
            with_file_metadata = False

        header_bytes = await stream.readexactly(header_size - preamble_size)

        complete_header = preamble_bytes + header_bytes

        # calculate checksum for verification
        checksum = self._calc_checksum(complete_header[:-1])
        if checksum != complete_header[-1]:
            # TODO: prepare error and send error reply to client
            return

        # get total number of commands to send to the board
        sound_file_size_in_samples = np.frombuffer(complete_header[metadata_index + 4: metadata_index + 4 + 4], dtype=np.int32)[0]
        commands_to_send = self._get_total_commands_to_send(sound_file_size_in_samples)

        # NOTE: convert data before sending to board (only needed until new firmware is ready)
        int32_size = np.dtype(np.int32).itemsize
        # Metadata command length: 'c' 'm' 'd' '0x80' + random + metadata + 32768 + 2048 + 'f'
        metadata_size = 4 * int32_size
        data_size = 32768
        data_index = preamble_size + metadata_size
        file_metadata_size = 2048
        file_metadata_index = data_index + data_size

        metadata_cmd_header_size = 4 + int32_size + metadata_size
        metadata_cmd = np.zeros(metadata_cmd_header_size + data_size + file_metadata_size + 1, dtype=np.int8)

        metadata_cmd[0] = ord('c')
        metadata_cmd[1] = ord('m')
        metadata_cmd[2] = ord('d')
        metadata_cmd[3] = 0x80
        metadata_cmd[-1] = ord('f')

        rand_val = np.random.randint(-32768, 32768, size=1, dtype=np.int32)
        # copy that random data
        metadata_cmd[4: 4 + int32_size] = rand_val.view(np.int8)
        # metadata
        metadata_cmd[8: 8 + (metadata_size)] = np.frombuffer(complete_header[metadata_index: metadata_index + metadata_size], dtype=np.int8)

        # add first data block of data to the metadata_cmd
        if with_data is True:
            metadata_cmd_data_index = metadata_cmd_header_size
            metadata_cmd[metadata_cmd_data_index: metadata_cmd_data_index + data_size] = np.frombuffer(complete_header[data_index: data_index + data_size], dtype=np.int8)
        else:
            # TODO: send reply to client and read the first block of data and add it to the first command sent here
            # TODO: also, wait for one less command on the while loop later
            pass

        # add user metadata (2048 bytes) to metadata_cmd
        if with_file_metadata is True:
            user_metadata_index = metadata_cmd_data_index + data_size
            metadata_cmd[user_metadata_index: user_metadata_index + file_metadata_size] = np.frombuffer(complete_header[file_metadata_index: file_metadata_index + file_metadata_size], dtype=np.int8)

        # send info
        # Metadata command reply: 'c' 'm' 'd' '0x80' + random + error
        metadata_cmd_reply = array.array('b', [0] * (4 + int32_size + int32_size))

        print(f'Start sending data to device...')
        start = time.time()

        # send metadata_cmd and get it's reply
        try:
            res_write = self._dev.write(0x01, metadata_cmd.tobytes(), 100)
        except usb.core.USBError as e:
            # TODO: we probably should try again
            print(f"something went wrong while writing to the device {e}")
            return

        assert res_write == len(metadata_cmd)

        try:
            ret = self._dev.read(0x81, metadata_cmd_reply, 1000)
        except usb.core.USBError as e:
            # TODO: we probably should try again
            print(f"something went wrong while reading from the device: {e}")
            return

        # get the random received and the error received from the reply command
        rand_val_received = int.from_bytes(metadata_cmd_reply[4: 4 + int32_size], byteorder='little', signed=True)
        error_received = int.from_bytes(metadata_cmd_reply[8: 8 + int32_size], byteorder='little', signed=False)

        assert rand_val_received == rand_val[0]
        assert error_received == 0

        # init progress bar
        pbar = tqdm(total=commands_to_send, unit_scale=False, unit="chunks")
        pbar.update()

        # if reached here, send ok reply to client
        self._send_reply(writer)

        data_size = 7 + 4 + 32768 + 1

        chunk_conversion_timings = []
        chunk_sending_timings = []

        # update reply value
        self._reply[2] = np.array([132], dtype=np.int8)

        data_cmd_data_index = 4 + int32_size + int32_size

        while True:
            try:
                chunk = await stream.readexactly(data_size)
            except IncompleteReadError:
                break

            # calculate checksum for verification
            checksum = self._calc_checksum(chunk[:-1])

            # if checksum is different, send reply with error
            if checksum != chunk[-1]:
                self._send_reply(writer, with_error=True)
                continue

            start = time.time()

            # send to board
            # it has to be as an np.array of int32 and later get a view as int8s
            rand_val = np.random.randint(-32768, 32768, size=1, dtype=np.int32)
            # copy that random data
            self._data_cmd[4: 4 + int32_size] = rand_val.view(np.int8)

            # write dataIndex to the data_cmd
            self._data_cmd[8: 8 + int32_size] = np.frombuffer(chunk[7:7 + int32_size], dtype=np.int32).view(np.int8)

            # write data from chunk to cmd
            data_block = chunk[7 + int32_size: 7 + int32_size + 32768]
            self._data_cmd[data_cmd_data_index: data_cmd_data_index + len(data_block)] = np.frombuffer(data_block, dtype=np.int8)

            chunk_conversion_timings.append(time.time() - start)

            start = time.time()

            # send data to device
            try:
                res_write = self._dev.write(0x01, self._data_cmd.tobytes(), 100)
            except usb.core.USBError as e:
                # TODO: we probably should try again
                print(f"something went wrong while writing to the device: {e}")
                return

            # TODO: we probably should try again
            assert res_write == len(self._data_cmd)

            try:
                ret = self._dev.read(0x81, self._data_cmd_reply, 400)
            except usb.core.USBError as e:
                # TODO: we probably should try again

                print(f"something went wrong while reading from the device: {e}")
                return

            # get the random received and the error received from the reply command
            rand_val_received = int.from_bytes(self._data_cmd_reply[4: 4 + int32_size], byteorder='little', signed=True)
            error_received = int.from_bytes(self._data_cmd_reply[8: 8 + int32_size], byteorder='little', signed=False)

            assert rand_val_received == rand_val[0]
            assert error_received == 0

            chunk_sending_timings.append(time.time() - start)

            self._send_reply(writer)

            pbar.update()

        pbar.close()
        print(f'\tTime used in converting data: {np.mean(chunk_conversion_timings)} s')
        print(f'\tMean time for sending each chunk: {np.mean(chunk_sending_timings)} s')

        writer.write('OK'.encode())
        print(f'File successfully sent in {time.time() - initial_time} s{os.linesep}')
        print(f'Waiting to receive new requests...{os.linesep}')

        self.clear_data()

        return preamble_bytes

    def _get_timestamp(self):
        curr = time.time()

        dec, integer = math.modf(curr)

        dec = dec / 32 * 10.0**6

        result = np.zeros(6, dtype=np.int8)
        result[:4] = np.array([int(integer)], dtype=np.uint32).view(np.int8)
        result[4:] = np.array([dec], dtype=np.uint16).view(np.int8)

        return result

    def _get_total_commands_to_send(self, sound_file_size_in_samples):
        return int(sound_file_size_in_samples * 4 // 32768 + (
                1 if ((sound_file_size_in_samples * 4) % 32768) != 0 else 0))

    def _calc_checksum(self, data):
        return sum(data) & 0xFF

    def _send_reply(self, writer, with_error=False):
        # send reply with error
        self._reply[0] = 10 if with_error else 2
        self._reply[5: 5 + 6] = self._get_timestamp()
        checksum = self._calc_checksum(self._reply[:-1])
        self._reply[-1] = np.array([checksum], dtype=np.int8)

        writer.write(bytes(self._reply))


if __name__ == "__main__":

    # NOTE: required so that the SIGINT signal is properly captured on windows
    def wakeup():
        # Call again
        loop.call_later(0.1, wakeup)

    srv = SoundCardTCPServer("localhost", 9999)

    loop = asyncio.SelectorEventLoop()
    loop.call_later(0.1, wakeup)
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(srv.start_server())
    except KeyboardInterrupt as k:
        print(f'Event captured: {k}')
        srv.close()
