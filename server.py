import asyncio
import struct
import numpy as np
from asyncio import IncompleteReadError


class SoundCardTCPServer(object):
    
    def __init__(self, addr, port):
      self.address = addr
      self.port = port

    async def start_server(self):
        # init connection to soundcard through the usb connection

        # Start server to listen for incoming requests
        asrv = await asyncio.start_server(self._handle_request, self.address, int(self.port))
        print("SoundCardTCPServer started and waiting for requests")
        while True:
            await asyncio.sleep(10)

    async def _handle_request(self, reader, writer):
        addr = writer.get_extra_info('peername')
 
        print(f'Request received from {addr}. Handling received data.')
        msg = await self._recv_data(reader)

    async def _recv_data(self, stream):
        # get first 7 bytes to know which type of frame we are going to receive
        preamble_size = 7
        preamble_bytes = await stream.readexactly(preamble_size)
        print(preamble_bytes)

        # size of header will depend on preamble data (index 4 defines type of frame)
        frame_type = preamble_bytes[4]
        print(frame_type)
        header_size = 7 + 16 + 1
        if frame_type == 128:
            header_size += 32768 + 2048
        elif frame_type == 129:
            header_size = 2048

        header_bytes = await stream.readexactly(header_size - preamble_size)
        print('remaining of the header received correctly')

        checksum = sum(preamble_bytes + header_bytes[:-1]) & 0xFF
        print(f'header checksum: {header_bytes[-1]}, calculated: {checksum}')

        # TODO: send the first command to the soundcard here

        data_size = 7 + 4 + 32768 + 1
        while True:
            try:
                chunk = await stream.readexactly(data_size)                
            except IncompleteReadError as e:
                break

            # calculate checksum for verification
            checksum = sum(chunk[:-1]) & 0xFF
            print(f'checksum received: {chunk[-1]}, checksum local: {checksum}')
            
            # TODO: send chunk directly to the soundcard if the checksum is the same

            #print(chunk)



        #size_msg = await stream.readexactly(4)
        #size, = struct.unpack('i', size_msg)
        #msg = await stream.readexactly(size)
        #print(msg)
        return preamble_bytes

if __name__ == "__main__":
    srv = SoundCardTCPServer("localhost", 9999)
    asyncio.get_event_loop().run_until_complete(srv.start_server())