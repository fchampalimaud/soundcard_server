import asyncio
import struct
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
        # TODO: try except to capture the Keyboard CTRL + C so that we can close the usb connection properly
        # TODO: another alternative would be to open and close the connection per request but that seems be slower
        while True:
            await asyncio.sleep(10)

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
        #size_msg = await stream.readexactly(4)
        #size, = struct.unpack('i', size_msg)
        #msg = await stream.readexactly(size)
        #print(msg)
        return preamble_bytes

if __name__ == "__main__":
    srv = SoundCardTCPServer("localhost", 9999)
    asyncio.get_event_loop().run_until_complete(srv.start_server())