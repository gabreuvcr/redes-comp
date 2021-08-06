import threading
import ipaddress
import socket
import sys

class Server:
    def __init__(self, port):
        self.host_ipv4 = '127.0.0.1'
        self.host_ipv6 = '::1'
        self.port = port
        self.win_size = 4
        self.tcp_sock_ipv4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock_ipv6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.connections()

    def udp_setup(self, host):
        ip_version = ipaddress.ip_address(host).version
        ip_type = socket.AF_INET if ip_version == 4 else socket.AF_INET6
        c_udp_sock = socket.socket(ip_type, socket.SOCK_DGRAM)
        c_udp_sock.bind((host, 0))
        c_udp_port = c_udp_sock.getsockname()[1]
        print(f"[srv] bind in udp port {c_udp_port}")
        return c_udp_sock, c_udp_port
    
    def recv_hello(self, c_tcp_sock, c_tcp_port):
        data = c_tcp_sock.recv(2)
        type_msg = data[:2].decode()
        if type_msg == '10':
            print(f"[cli] hello: from tcp {c_tcp_port}")

    def send_connection(self, c_tcp_sock, c_udp_port):
        data = '20'.encode() + (c_udp_port).to_bytes(4, 'big')
        c_tcp_sock.send(data)
        print(f"[srv] connection: sent udp {c_udp_port}")
    
    def recv_info_file(self, c_tcp_sock, c_tcp_port):
        data = c_tcp_sock.recv(25)
        type_msg = data[:2].decode()
        if type_msg == '30':
            file_name = data[2:17].decode().strip()
            file_size = int.from_bytes(data[17:25], 'big')
            print(f"[cli] info file: from tcp {c_tcp_port} received file {file_name} with {file_size} bytes")
            return file_name, file_size

    def send_ok(self, c_tcp_sock):
        data = '40'.encode()
        c_tcp_sock.send(data)
        print(f"[srv] ok: sent ok to the client")
    
    def send_ack(self, c_tcp_sock, seq):
        data = '70'.encode() + seq.to_bytes(4, 'big', signed=True)
        c_tcp_sock.send(data)
        print(f"[srv] ack: sent acknowledgment of seq {seq}")

    def recv_file(self, c_tcp_sock, c_udp_sock, file_name, file_size):
        upload_file = open(f"uploads/{file_name}", 'wb')
        next_seq_num, size_recv = 0, 0
        bytes_recv = {}
        while size_recv != file_size:
            data = c_udp_sock.recvfrom(1008)[0]
            type_msg = data[:2].decode()
            if type_msg == '61':
                seq_recv = int.from_bytes(data[2:6], 'big')
                if seq_recv < next_seq_num + self.win_size:
                    if seq_recv not in bytes_recv:
                        size_recv += int.from_bytes(data[6:8], 'big')
                        bytes_recv[seq_recv] = data[8:]
                    print(f"[cli] received seq {seq_recv}")
                    self.send_ack(c_tcp_sock, seq_recv)
                    if seq_recv == next_seq_num:
                        next_seq_num += 1
                else:
                    self.send_ack(c_tcp_sock, next_seq_num - 1)
        for i in range(len(bytes_recv)):
            upload_file.write(bytes_recv[i])
        upload_file.close()

    def send_fim(self, c_tcp_sock):
        data = '50'.encode()
        c_tcp_sock.send(data)
        c_tcp_sock.close()
        print(f"[srv] fim: finished connection with the client, file upload")
            
    def server_thread(self, c_tcp_sock, c_addr):
        c_host, c_tcp_port = c_addr[0], c_addr[1]
        print(f"[srv] connection from {c_host} {c_tcp_port}")
        self.recv_hello(c_tcp_sock, c_tcp_port)
        c_udp_sock, c_udp_port = self.udp_setup(c_host)
        self.send_connection(c_tcp_sock, c_udp_port)
        file_name, file_size = self.recv_info_file(c_tcp_sock, c_tcp_port)
        self.send_ok(c_tcp_sock)
        self.recv_file(c_tcp_sock, c_udp_sock, file_name, file_size)
        self.send_fim(c_tcp_sock)

    def ip_thread(self, tcp_sock, host):
        tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_sock.bind((host, self.port))
        tcp_sock.listen()
        print(f"bound to {host}, waiting connections")
        while True:
            c_tcp_sock, c_addr = tcp_sock.accept()
            c_thread = threading.Thread(target=self.server_thread, args=(c_tcp_sock, c_addr), daemon=True)
            c_thread.start()
    
    def connections(self):
        try:
            ipv4_thread = threading.Thread(target=self.ip_thread, args=(self.tcp_sock_ipv4, self.host_ipv4), daemon=True) 
            ipv6_thread = threading.Thread(target=self.ip_thread, args=(self.tcp_sock_ipv6, self.host_ipv6), daemon=True)
            ipv4_thread.start(), ipv6_thread.start()
            ipv4_thread.join(), ipv6_thread.join() 
        except KeyboardInterrupt:
            print(" interrupting...")
        except OverflowError:
            print("port must be 0-65535")

def verify_args():
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <server port>")
        print(f"example: {sys.argv[0]} 51511")
        exit(1)

if __name__ == '__main__':
    try:
        verify_args()
        port = int(sys.argv[1])
        server = Server(port)
    except ValueError:
        print("invalid arguments, port is an int")
