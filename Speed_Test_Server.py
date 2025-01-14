import socket
import threading
import struct
import random
import time
from typing import Tuple

# constants values
MAGIC_COOKIE = 0xabcddcba
OFFER_MSG_TYPE = 0x2
REQUEST_MSG_TYPE = 0x3
PAYLOAD_MSG_TYPE = 0x4

# ANSI Colors
COLORS = {
    'GREEN': '\033[32m',
    'BLUE': '\033[34m',
    'RED': '\033[31m',
    'YELLOW': '\033[33m',
    'RESET': '\033[0m',
    'BOLD': '\033[1m'
}


class SpeedTestServer:
    def __init__(self):
        try:
            # initialize TCP and UDP server sockets
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # Bind to random available ports
            self.udp_socket.bind(('', 0))
            self.tcp_socket.bind(('', 0))
            self.tcp_socket.listen(5)

            # allocated ports
            self.udp_port = self.udp_socket.getsockname()[1]
            self.tcp_port = self.tcp_socket.getsockname()[1]

            # server IP
            hostname = socket.gethostname()
            self.server_ip = socket.gethostbyname(hostname)

            print(f"{COLORS['GREEN']}Server started, listening on IP address {self.server_ip}{COLORS['RESET']}")

        except Exception as e:
            print(f"{COLORS['RED']}Failed to initialize server: {e}{COLORS['RESET']}")
            raise

    def start(self):
        try:
            """Start the server's main threads"""

            threads = [
                threading.Thread(target=self._broadcast_offers),
                threading.Thread(target=self._handle_tcp_connections),
                threading.Thread(target=self._handle_udp_requests)
            ]

            # start all the threads
            for t in threads:
                t.daemon = True
                t.start()

            # keep main thread alive
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down server...")
        except Exception as e:
            print(f"{COLORS['RED']}Server error: {e}{COLORS['RESET']}")

    def _broadcast_offers(self):
        """Broadcasts offer messages every second"""
        broadcast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        broadcast.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while True:
            try:
                # create offer message
                offer_message = struct.pack('!IbHH', MAGIC_COOKIE, OFFER_MSG_TYPE, self.udp_port, self.tcp_port)

                # send offer message
                broadcast.sendto(offer_message, ('<broadcast>', 13117))
                time.sleep(1)

            except Exception as e:
                print(f"{COLORS['RED']}Error broadcasting offer: {e}{COLORS['RESET']}")
                time.sleep(1)

    def _handle_tcp_connections(self):
        """Handles incoming TCP connections"""
        while True:
            try:
                client, addr = self.tcp_socket.accept()
                threading.Thread(target=self._handle_tcp_client, args=(client, addr)).start()

            except Exception as e:
                print(f"{COLORS['RED']}Error accepting TCP connection: {e}{COLORS['RESET']}")

    def _handle_tcp_client(self, client, addr):
        """Handles a single TCP client connection"""
        try:
            client.settimeout(5.0)  # timeout for receiving data
            data = client.recv(1024)  # get requested file size
            if not data:
                raise ConnectionError("Client disconnected")

            # Get requested file size
            file_size = int(data.decode().strip())
            if file_size <= 0:
                raise ValueError("File size must be positive")

            # send random data
            sent = 0
            chunk_size = 1024

            while sent < file_size:
                remaining = file_size - sent
                chunk = min(chunk_size, remaining)
                data = bytes([random.randint(0, 255) for _ in range(chunk)])
                client.send(data)
                sent += chunk

        except Exception as e:
            print(f"{COLORS['RED']}Error handling TCP client {addr}: {e}{COLORS['RESET']}")
        finally:
            client.close()

    def _handle_udp_requests(self):
        """Handles incoming UDP requests"""
        while True:
            try:
                try:
                    data, addr = self.udp_socket.recvfrom(1024)
                except socket.error as e:
                    print(f"{COLORS['RED']}Network error receiving UDP request: {e}{COLORS['RESET']}")
                    continue

                # checks packet format
                if not data:
                    print(f"{COLORS['RED']}Received empty UDP packet{COLORS['RESET']}")
                    continue

                # magic cookie and message type checking
                if len(data) >= 13:  # minimum size check: magic cookie (4) + msg type (1) + file size (8)
                    magic, msg_type, file_size = struct.unpack('!IbQ', data[:13])

                    if magic == MAGIC_COOKIE and msg_type == REQUEST_MSG_TYPE:  # type check
                        udp_thread = threading.Thread(target=self._handle_udp_client, args=(addr, file_size)).start()

                    else:
                        print(f"{COLORS['RED']}Received invalid UDP packet format{COLORS['RESET']}")

            except Exception as e:
                print(f"{COLORS['RED']}Error handling UDP request: {e}{COLORS['RESET']}")

    def _handle_udp_client(self, addr: Tuple[str, int], file_size: int):
        """Handles a single UDP client request"""
        try:
            # total segments calculation
            segment_size = 1024
            total_segments = (file_size + segment_size - 1) // segment_size

            # send all data segments
            for segment_num in range(total_segments):

                # calculate segment's size
                remaining = file_size - (segment_num * segment_size)
                curr_segment_size = min(segment_size, remaining)

                # creating random payload
                payload = bytes([random.randint(0, 255) for _ in range(curr_segment_size)])

                # creating and sending the packet
                header = struct.pack('!IbQQ', MAGIC_COOKIE, PAYLOAD_MSG_TYPE, total_segments, segment_num)
                packet = header + payload
                self.udp_socket.sendto(packet, addr)

                time.sleep(0.001)  # preventing overwhelming the network

        except Exception as e:
            print(f"{COLORS['RED']}Error handling UDP client {addr}: {e}{COLORS['RESET']}")


if __name__ == "__main__":
    try:
        server = SpeedTestServer()
        server.start()
    except Exception as e:
        print(f"{COLORS['RED']}Fatal error: {e}{COLORS['RESET']}")

