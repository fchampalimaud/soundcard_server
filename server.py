import asyncio
import struct


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
        size_msg = await stream.readexactly(4)
        size, = struct.unpack('i', size_msg)
        msg = await stream.readexactly(size)
        print(msg)
        return msg

if __name__ == "__main__":
    srv = SoundCardTCPServer("localhost", 9999)
    asyncio.get_event_loop().run_until_complete(srv.start_server())


# @asyncio.coroutine
# def handle_echo(reader, writer):
#     data = yield from reader.read(2048)
#     message = data.decode()
#     addr = writer.get_extra_info('peername')
#     print("Received %r from %r" % (message, addr))

#     print("Send: %r" % message)
#     writer.write(data)
#     yield from writer.drain()

#     print("Close the client socket")
#     writer.close()

# loop = asyncio.get_event_loop()
# coro = asyncio.start_server(handle_echo, '127.0.0.1', 8888, loop=loop)
# server = loop.run_until_complete(coro)

# # Serve requests until Ctrl+C is pressed
# print('Serving on {}'.format(server.sockets[0].getsockname()))
# try:
#     loop.run_forever()
# except KeyboardInterrupt:
#     pass

# # Close the server
# server.close()
# loop.run_until_complete(server.wait_closed())
# loop.close()
