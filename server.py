import asyncio
import array
import usb.core
import usb.util
import numpy as np
from asyncio import IncompleteReadError


class SoundCardTCPServer(object):
    
    def __init__(self, addr, port):
      self.address = addr
      self.port = port

    async def start_server(self):
        # init connection to soundcard through the usb connection
        self._dev = usb.core.find(idVendor=0x04d8, idProduct=0xee6a)

        if self._dev is None:
            print( 'SoundCard not found. Please connect it to the USB port before proceeding.')
            # return
        else:
            # set the active configuration. With no arguments, the first configuration will be the active one
            # note: some devices reset when setting an already selected configuration so we should check for it before
            self._cfg = self._dev.get_active_configuration()
            if self._cfg is None or self._cfg.bConfigurationValue != 1:
                self._dev.set_configuration(1)

        # Start server to listen for incoming requests
        asrv = await asyncio.start_server(self._handle_request, self.address, int(self.port))
        print('SoundCardTCPServer started and waiting for requests')
        while True:
            await asyncio.sleep(10)

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

        # calculate checksum for verification
        checksum = sum(preamble_bytes + header_bytes[:-1]) & 0xFF

        # TODO: send the first command to the soundcard here
        if checksum == header_bytes[-1]:
            # convert data before sending to board (only needed until new firmware is ready)
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
            
            print('header sent to board successfully... waiting for remaining data...')
            pass

        data_size = 7 + 4 + 32768 + 1
        while True:
            try:
                chunk = await stream.readexactly(data_size)
            except IncompleteReadError as e:
                break

            # calculate checksum for verification
            checksum = sum(chunk[:-1]) & 0xFF
            
            # TODO: send chunk directly to the soundcard if the checksum is the same
            if checksum == chunk[-1]:
                # send to board
                pass

        writer.write('OK'.encode())
        print('Data request processed successfully!')
        return preamble_bytes

if __name__ == "__main__":
    srv = SoundCardTCPServer("localhost", 9999)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(srv.start_server())
    except KeyboardInterrupt as k:
        print(f'Event captured: {k}')
        srv.close()