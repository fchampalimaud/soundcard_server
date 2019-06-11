import asyncio
import array
import usb.core
import usb.util
import time
import math
import numpy as np
from asyncio import IncompleteReadError


class SoundCardTCPServer(object):
    
    def __init__(self, addr, port):
      self.address = addr
      self.port = port

    async def start_server(self):
        # init connection to soundcard through the usb connection
        self.open()

        # Start server to listen for incoming requests
        asrv = await asyncio.start_server(self._handle_request, self.address, int(self.port))
        print('SoundCardTCPServer started and waiting for requests')
        while True:
            await asyncio.sleep(10)

    def open(self):
        print('Opening USB connection')
        self._dev = usb.core.find(idVendor=0x04d8, idProduct=0xee6a)
        if self._dev is None:
            print( 'SoundCard not found. Please connect it to the USB port before proceeding.')
        else:
            # set the active configuration. With no arguments, the first configuration will be the active one
            # note: some devices reset when setting an already selected configuration so we should check for it before
            _cfg = self._dev.get_active_configuration()
            if _cfg is None or _cfg.bConfigurationValue != 1:
                self._dev.set_configuration(1)

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

    async def _handle_request(self, reader, writer):
        addr = writer.get_extra_info('peername')
 
        print(f'Request received from {addr}. Handling received data.')
        msg = await self._recv_data(writer, reader)

    async def _recv_data(self, writer, stream):
        start = time.time()

        # get first 7 bytes to know which type of frame we are going to receive
        preamble_size = 7
        preamble_bytes = await stream.readexactly(preamble_size)

        # size of header will depend on preamble data (index 4 defines type of frame)
        frame_type = preamble_bytes[4]
        header_size = 7 + 16 + 1
        if frame_type == 128:
            header_size += 32768 + 2048
        elif frame_type == 129:
            header_size = 2048

        header_bytes = await stream.readexactly(header_size - preamble_size)

        print(f'Time to receive complete first package: {time.time() - start}')

        # prepare message to reply to client (5 bytes for preamble, 6 bytes for timestamp and 1 for checksum)
        reply = np.zeros(5 + 6 + 1, dtype=np.int8)
        # prepare with 'ok' reply by default
        reply[:5] = np.array([2, 10, 128, 255, 16], dtype=np.int8)

        # calculate checksum for verification
        checksum = sum(preamble_bytes + header_bytes[:-1]) & 0xFF

        # TODO: send the first command to the soundcard here
        if checksum == header_bytes[-1]:
            print(f'Start of conversion of header package')
            start = time.time()
            # NOTE: convert data before sending to board (only needed until new firmware is ready)
            int32_size = np.dtype(np.int32).itemsize
            # Metadata command length: 'c' 'm' 'd' '0x80' + random + metadata + 32768 + 2048 + 'f'
            metadata_cmd_header_size = 4 + int32_size + (4 * int32_size)
            metadata_cmd = np.zeros(metadata_cmd_header_size + 32768 + 2048 + 1, dtype=np.int8)

            metadata_cmd[0] = ord('c')
            metadata_cmd[1] = ord('m')
            metadata_cmd[2] = ord('d')
            metadata_cmd[3] = 0x80
            metadata_cmd[-1] = ord('f')

            rand_val = np.random.randint(-32768, 32768, size=1, dtype=np.int32)
            # copy that random data
            metadata_cmd[4: 4 + int32_size] = rand_val.view(np.int8)
            # metadata
            metadata_cmd[8: 8 + (4 * int32_size)] = np.frombuffer(header_bytes[:4 * int32_size], dtype=np.int8)
            # add first data block of data to the metadata_cmd
            metadata_cmd_data_index = metadata_cmd_header_size
            metadata_cmd[metadata_cmd_data_index: metadata_cmd_data_index + 32768] = np.frombuffer(header_bytes[16: 16 + 32768], dtype=np.int8)
            # add user metadata (2048 bytes) to metadata_cmd
            user_metadata_index = metadata_cmd_data_index + 32768
            metadata_cmd[user_metadata_index: user_metadata_index + 2048] = np.frombuffer(header_bytes[16 + 32768: 16 + 32768 + 2048], dtype=np.int8)

            # send info
            # Metadata command reply: 'c' 'm' 'd' '0x80' + random + error
            metadata_cmd_reply = array.array('b', [0] * (4 + int32_size + int32_size))

            print(f'Time to convert header package: {time.time() - start}')

            print(f'Start sending data to device')
            start = time.time()
            
            # send metadata_cmd and get it's reply
            try:
                res_write = self._dev.write(0x01, metadata_cmd.tobytes(), 100)
            except usb.core.USBError as e:
                # TODO: we probably should try again
                print("something went wrong while writing to the device")
                return

            assert res_write == len(metadata_cmd)

            try:
                ret = self._dev.read(0x81, metadata_cmd_reply, 100)
            except usb.core.USBError as e:
                # TODO: we probably should try again

                print("something went wrong while reading from the device")
                return

            # get the random received and the error received from the reply command
            rand_val_received = int.from_bytes(metadata_cmd_reply[4: 4 + int32_size], byteorder='little', signed=True)
            error_received = int.from_bytes(metadata_cmd_reply[8: 8 + int32_size], byteorder='little', signed=False)

            assert rand_val_received == rand_val[0]
            assert error_received == 0

            # if reached here, send ok reply to client (prepare timestamp first, and calculate checksum first)
            reply[5: 5 + 6] = self._get_timestamp()
            print(f'timestamp as bytes: {reply[5: 5 + 6]}')
            # calculate checksum
            checksum = sum(reply) & 0xFF
            reply[-1] = np.array([checksum], dtype=np.int8)

            # send reply to client
            writer.write(bytes(reply))

            print(f'Time to send first package to device: {time.time() - start}')
            
            print('header sent to board successfully... waiting for remaining data...')
            pass

            data_size = 7 + 4 + 32768 + 1

            # NOTE: Convert data before sending
            # prepare command to send and to receive
            # Data command length:     'c' 'm' 'd' '0x81' + random + dataIndex + 32768 + 'f'
            data_cmd = np.zeros(4 + int32_size + int32_size + 32768 + 1, dtype=np.int8)
            data_cmd_data_index = 4 + int32_size + int32_size

            data_cmd[0] = ord('c')
            data_cmd[1] = ord('m')
            data_cmd[2] = ord('d')
            data_cmd[3] = 0x81
            data_cmd[-1] = ord('f')

            # Data command reply:     'c' 'm' 'd' '0x81' + random + error
            data_cmd_reply = array.array('b', [0] * (4 + int32_size + int32_size))

            chunk_conversion_timings = []
            chunk_sending_timings = []

            #update reply value
            reply[2] = np.array([132], dtype=np.int8)
            print('\tStart conversion and sending of chunks data')

            while True:
                try:
                    chunk = await stream.readexactly(data_size)
                except IncompleteReadError as e:
                    break

                # calculate checksum for verification
                checksum = sum(chunk[:-1]) & 0xFF
                
                # TODO: send chunk directly to the soundcard if the checksum is the same
                if checksum == chunk[-1]:
                    start = time.time()

                    # send to board
                    # it has to be as an np.array of int32 so that we can get a view as int8s
                    rand_val = np.random.randint(-32768, 32768, size=1, dtype=np.int32)
                    # copy that random data
                    data_cmd[4: 4 + int32_size] = rand_val.view(np.int8)

                    # write dataIndex to the data_cmd
                    data_cmd[8: 8 + int32_size] = np.frombuffer(chunk[7:7 + int32_size], dtype=np.int32).view(np.int8)

                    # write data from chunk to cmd
                    data_block = chunk[7 + int32_size: 7 + int32_size + 32768]
                    data_cmd[data_cmd_data_index: data_cmd_data_index + len(data_block)] = np.frombuffer(data_block, dtype=np.int8)

                    chunk_conversion_timings.append(time.time() - start)

                    start = time.time()

                    # send data to device
                    try:
                        res_write = self._dev.write(0x01, data_cmd.tobytes(), 100)
                    except usb.core.USBError as e:
                        # TODO: we probably should try again
                        print("something went wrong while writing to the device")
                        return

                    # TODO: we probably should try again
                    assert res_write == len(data_cmd)

                    try:
                        ret = self._dev.read(0x81, data_cmd_reply, 100)
                    except usb.core.USBError as e:
                        # TODO: we probably should try again

                        print("something went wrong while reading from the device")
                        return

                    # get the random received and the error received from the reply command
                    rand_val_received = int.from_bytes(data_cmd_reply[4: 4 + int32_size], byteorder='little', signed=True)
                    error_received = int.from_bytes(data_cmd_reply[8: 8 + int32_size], byteorder='little', signed=False)

                    assert rand_val_received == rand_val[0]
                    assert error_received == 0

                    chunk_sending_timings.append(time.time() - start)

                    reply[5: 5 + 6] = self._get_timestamp()
                    reply[-1] = 0
                    # calculate checksum
                    checksum = sum(reply) & 0xFF
                    reply[-1] = np.array([checksum], dtype=np.int8)

                    writer.write(bytes(reply))

            print(f'chunks_conversion_timings mean: {np.mean(chunk_conversion_timings)}')
            print(f'chunks_sending_timings mean: {np.mean(chunk_sending_timings)}')

        writer.write('OK'.encode())
        print('Data request processed successfully!')
        return preamble_bytes
    
    def _get_timestamp(self):
        curr = time.time()

        dec, integer = math.modf(curr)

        dec = dec / 32 * 10.0**6

        result = np.zeros(6, dtype=np.int8)
        result[:4] = np.array([int(integer)], dtype=np.uint32).view(np.int8)
        result[4:] = np.array([dec], dtype=np.uint16).view(np.int8)

        return result

if __name__ == "__main__":
    srv = SoundCardTCPServer("localhost", 9999)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(srv.start_server())
    except KeyboardInterrupt as k:
        print(f'Event captured: {k}')
        srv.close()