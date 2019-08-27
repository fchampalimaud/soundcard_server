import asyncio
import time


class Communication:
    def __init__(self, protocol, loop, address='localhost', port=9999):
        self._reader = None
        self._writer = None
        self._address = address
        self._port = port
        self._protocol = protocol
        self._loop = loop

        self._reply_size = 5 + 6 + 1

    async def open(self):
        self._reader, self._writer = await asyncio.open_connection(self._address, self._port, loop=self._loop)

    def send_header(self, header):
        self.send_data(header)

    def send_data(self, data):
        self._writer.write(bytes(data))

    async def get_reply(self):
        return await self._reader.readexactly(self._reply_size)

    async def send_sound(self):
        packet_sending_timings = []

        # cycle through the sound data and send the packets to the server
        for i in range(1, self._protocol.commands_to_send):
            # clean the remaining elements for the last packet which might be smaller than 32K
            if i == self._protocol.commands_to_send - 1:
                self._protocol.clean_data_cmd()

            self._protocol.write_data_index(i)
            self._protocol.write_data_block(i)
            self._protocol.update_data_checksum()

            start = time.time()

            # write to socket
            self.send_data(self._protocol.data_cmd)

            # to guarantee that the buffer is not getting filled completely. It will continue immediately if there's still space in the buffer
            await self._writer.drain()

            # receive ok
            reply = await self.get_reply()

            packet_sending_timings.append(time.time() - start)

            # gets the timestamp as per the Harp protocol
            timestamp = self._protocol.convert_timestamp(reply[5: 5 + 6])

            if reply[0] != 2:
                return (packet_sending_timings, "ErrorWhileTransferringData")

        self._writer.write_eof()
        return (packet_sending_timings, "Success")

    async def get_final_reply(self):
        return await self._reader.readexactly(2)
