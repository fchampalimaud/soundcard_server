import asyncio
import struct
import numpy as np


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
        print("remaining of the header received correctly")

        # TODO: while until end to send the data
        data_size = 7 + 4 + 32768 + 1
        index = 0
        while True:
            index += 1
            chunk = await stream.readexactly(data_size)
            if not chunk:
                break

            # calculate checksum for verification
            print(f'chunk {chunk[7:7 + 4]}, checksum: {chunk[-1]}')
            
            # TODO: send chunk directly? or check checksum first?

            #print(chunk)



        #size_msg = await stream.readexactly(4)
        #size, = struct.unpack('i', size_msg)
        #msg = await stream.readexactly(size)
        #print(msg)
        return preamble_bytes

if __name__ == "__main__":
    srv = SoundCardTCPServer("localhost", 9999)
    asyncio.get_event_loop().run_until_complete(srv.start_server())