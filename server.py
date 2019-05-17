import asyncio
import struct
import numpy as np


class SoundCardTCPServer(object):
    
    def __init__(self, addr, port):
      self.address = addr
      self.port = port

    async def start_server(self):
        # init connection to soundcard

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
        # TODO: here we will add the handling of the data to be sent, by blocks of 2048
        preamble_size = 7
        preamble_bytes = await stream.readexactly(preamble_size)
        dt = np.dtype(np.int8)
        dt = dt.newbyteorder('<')
        preamble = np.frombuffer(preamble_bytes, dtype=dt, count=-1)
        print(preamble)

        # size of header will depend on preamble data
        # TODO: interpret preamble data
        print(preamble[4])
        header = np.zeros(7+16+32768+2048+1, dtype=np.int8)

        header_bytes = await stream.readexactly(34840 - preamble_size)
        print("remaining of the header received correctly")

        #size_msg = await stream.readexactly(4)
        #size, = struct.unpack('i', size_msg)
        #msg = await stream.readexactly(size)
        #print(msg)
        return preamble

if __name__ == "__main__":
    srv = SoundCardTCPServer("localhost", 9999)
    asyncio.get_event_loop().run_until_complete(srv.start_server())