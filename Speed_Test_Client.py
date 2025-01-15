import socket
import struct
import threading
import time
from typing import List, Dict
import sys

# Constants
MAGIC_COOKIE = 0xabcddcba
OFFER_MSG_TYPE = 0x2
REQUEST_MSG_TYPE = 0x3
PAYLOAD_MSG_TYPE = 0x4

# ANSI Colors for better readability
COLORS = {
    'GREEN': '\033[32m',
    'BLUE': '\033[34m',
    'RED': '\033[31m',
    'YELLOW': '\033[33m',
    'CYAN': '\033[36m',
    'RESET': '\033[0m',
    'BOLD': '\033[1m'
}


class SpeedTestClient:
    def __init__(self):
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            self.udp_socket.bind(('', 13117))

        except Exception as e:
            print(f"{COLORS['RED']}Failed to initialize client: {e}{COLORS['RESET']}")
            raise

    def _get_user_input(self) -> tuple[int, int, int]:
        """
        Get and validate user input.
        Returns: tuple of (file_size, tcp_count, udp_count)
        """
        while True:
            try:
                file_size = int(input(f"{COLORS['CYAN']}Enter file size (bytes): {COLORS['RESET']}"))
                tcp_count = int(input(f"{COLORS['CYAN']}Enter number of TCP connections: {COLORS['RESET']}"))
                udp_count = int(input(f"{COLORS['CYAN']}Enter number of UDP connections: {COLORS['RESET']}"))

                if file_size <= 0:
                    raise ValueError("File size must be positive")

                if tcp_count < 0:
                    raise ValueError("TCP connections cannot be negative")

                if udp_count < 0:
                    raise ValueError("UDP connections cannot be negative")

                if tcp_count + udp_count == 0:
                    raise ValueError("Must have at least one connection")

                return file_size, tcp_count, udp_count

            except ValueError as e:
                print(f"{COLORS['RED']}Error: {e}. Please try again.{COLORS['RESET']}")

    def start(self):
        """Main client loop"""
        print(f"{COLORS['BOLD']}=== Speed Test Client ==={COLORS['RESET']}")
        try:

            file_size, tcp_count, udp_count = self._get_user_input()  # get user input

            while True:  # infinity loop with the same user's parameters
                try:

                    print(f"\n{COLORS['YELLOW']}Client started, listening for offer requests...{COLORS['RESET']}")
                    server_ip, server_ports = self._wait_for_offer()  # waiting for server offer
                    print(f"{COLORS['GREEN']}Received offer from {server_ip}{COLORS['RESET']}\n")
                    self._run_speed_test(server_ip, server_ports, file_size, tcp_count, udp_count) # start speed test

                    # finish
                    print(f"\nAll transfers complete, listening to offer requests\n")

                except Exception as e:
                    print(f"{COLORS['RED']}Error: {e}{COLORS['RESET']}")
                    time.sleep(1)

        except KeyboardInterrupt:
            print(f"\n{COLORS['YELLOW']}Shutting down client...{COLORS['RESET']}")

    def _wait_for_offer(self):
        """Wait for a server offer broadcast"""

        self.udp_socket.settimeout(10.0)  # timeout for offer of 10 second
        while True:
            try:
                data, addr = self.udp_socket.recvfrom(1024)

                if len(data) >= 9:  # package size check: magic cookie (4) + msg type (1) + UDP port (2) + TCP port (2)
                    magic, msg_type, udp_port, tcp_port = struct.unpack('!IbHH', data[:9])

                    if magic == MAGIC_COOKIE and msg_type == OFFER_MSG_TYPE:
                        return addr[0], (udp_port, tcp_port)

            except Exception as e:
                print(f"Error receiving offer: {e}")

    def _run_speed_test(self, server_ip, server_ports, file_size, tcp_count, udp_count):
        """Run the speed test with specified parameters"""
        threads = []

        # TCP transfers
        for i in range(tcp_count):
            thread = threading.Thread(target=self._tcp_transfer, args=(server_ip, server_ports[1], file_size, i + 1))
            thread.start()
            threads.append(thread)

        # UDP transfers
        for i in range(udp_count):
            thread = threading.Thread(target=self._udp_transfer, args=(server_ip, server_ports[0], file_size, i + 1))
            thread.start()
            threads.append(thread)

        # waiting for all transfers to complete
        for thread in threads:
            thread.join()

    def _tcp_transfer(self, server_ip, server_port, file_size, transfer_num):
        """Handle a single TCP transfer"""
        sock = None
        print(f"Trying to connect to TCP port {server_port}")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)  # 10 seconds timeout for connection
            try:
                sock.connect((server_ip, server_port))  # connect to server

            except socket.timeout:
                raise ConnectionError("Connection timed out")
            except ConnectionRefusedError:
                raise ConnectionError("Server refused connection")
            except socket.gaierror:
                raise ConnectionError("Invalid server address")

            sock.send(f"{file_size}\n".encode())  # send file size request

            start_time = time.time()
            bytes_received = 0

            while bytes_received < file_size:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                bytes_received += len(chunk)

            duration = time.time() - start_time
            speed = (file_size * 8) / duration  # bits per second units

            print(f"{COLORS['GREEN']}TCP Transfer No.{transfer_num}")
            print(f"{COLORS['GREEN']}Total time: {duration:.2f} seconds")
            print(f"{COLORS['GREEN']}Speed: {speed/1000000:.2f} Mbps")

        except Exception as e:
            print(f"{COLORS['RED']}Error in TCP Transfer No.{transfer_num}")
            print(f"{COLORS['RED']}{str(e)}")
        finally:
            if sock:
                sock.close()

    def _udp_transfer(self, server_ip, server_port, file_size, transfer_num):
        """Handle a single UDP transfer"""
        sock = None

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # send the request
            request = struct.pack('!IbQ', MAGIC_COOKIE, REQUEST_MSG_TYPE, file_size)
            sock.sendto(request, (server_ip, server_port))

            start_time = time.time()
            bytes_received = 0
            segments_received = set()
            total_segments = None
            last_packet_time = time.time()

            while True:
                if time.time() - last_packet_time > 1.0:  # check if too much time has passed since the last packet
                    break

                try:
                    sock.settimeout(1.0)
                    data, _ = sock.recvfrom(2048)
                    last_packet_time = time.time()

                    if len(data) < 21:  # Header size
                        continue

                    # parse header
                    magic, msg_type, total_segs, seg_num = struct.unpack('!IbQQ', data[:21])

                    if magic != MAGIC_COOKIE or msg_type != PAYLOAD_MSG_TYPE:
                        continue

                    payload = data[21:]
                    if total_segments is None:
                        total_segments = total_segs

                    if seg_num not in segments_received:
                        segments_received.add(seg_num)
                        bytes_received += len(payload)

                except socket.timeout:
                    continue

            duration = time.time() - start_time
            speed = (bytes_received * 8) / (duration * 1_000_000)  # Mbps
            success_rate = len(segments_received) / total_segments * 100 if total_segments else 0

            print(f"{COLORS['BLUE']}UDP Transfer No.{transfer_num}")
            print(f"{COLORS['BLUE']}Total time: {duration:.2f} seconds")
            print(f"{COLORS['BLUE']}Speed: {speed:.2f} Mbps")
            print(f"{COLORS['BLUE']}Success rate: {success_rate:.1f}%")

        except Exception as e:
            print(f"{COLORS['RED']}Error in UDP Transfer No.{transfer_num}")
            print(f"{str(e)}")
        finally:
            if sock:
                sock.close()


if __name__ == "__main__":
    try:
        client = SpeedTestClient()
        client.start()
    except Exception as e:
        print(f"{COLORS['RED']}Fatal error: {e}{COLORS['RESET']}")
