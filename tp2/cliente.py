import ipaddress
import socket
import time
import sys
import os

TIME_OUT = 0.1
FIM = -5

class Client:
    def __init__(self, host, tcp_port):
        self.host = host
        self.tcp_port = tcp_port
        self.udp_port = 0
        self.ip_type = self.get_ip_version()
        self.win_size = 4
        self.tcp_sock = socket.socket(self.ip_type, socket.SOCK_STREAM)
        self.udp_sock = socket.socket(self.ip_type, socket.SOCK_DGRAM)
        self.connection()
    
    def get_ip_version(self):
        try:
            ip_version = ipaddress.ip_address(self.host).version
            return socket.AF_INET if ip_version == 4 else socket.AF_INET6
        except ValueError:
            print("host invalid")
            exit(1)

    def check_file_name(self, file_name):
        if (len(file_name) > 15 or
            len(file_name) != len(file_name.encode()) or
            file_name.count('.') != 1 or
            len(file_name.split('.')[1]) != 3):
                print("name not allowed")
                exit(1)
        while len(file_name) < 15:
            file_name += ' '
        return file_name
    
    def get_info_file(self):
        try:
            file_name = self.check_file_name(sys.argv[3])
            file_size = os.path.getsize(file_name.strip())
            return file_name, file_size
        except FileNotFoundError:
            print("file not found.")
            exit(1)
            
    def send_hello(self):
        self.tcp_sock.send(b'10')
        print("[cli] hello: sent hello to the server")

    def recv_connection(self):
        data = self.tcp_sock.recv(6)
        type_msg = data[:2].decode()
        if type_msg == '20':
            udp_port = int.from_bytes(data[2:6], 'big')
            print(f"[srv] connection: your udp port is {udp_port}")
            return udp_port
    
    def send_info_file(self, file_name, file_size):
        data = '30'.encode() + file_name.encode() + file_size.to_bytes(8, 'big')
        self.tcp_sock.send(data)
        print("[cli] info file: file informations sent to the server")
    
    def recv_ok(self):
        data = self.tcp_sock.recv(2)
        type_msg = data[:2].decode()
        if type_msg == '40':
            print(f"[srv] ok: server received file informations")
    
    def recv_fim(self):
        data = self.tcp_sock.recv(2)
        type_msg = data[:2].decode()
        if type_msg == '50':
            print(f"[log] fim: finished connection, file uploaded")
            self.tcp_sock.close()
            return

    def recv_ack(self):
        try:
            self.tcp_sock.settimeout(TIME_OUT)
            data = self.tcp_sock.recv(6)
            self.tcp_sock.settimeout(None)
            type_msg = data[:2].decode()
            if type_msg == '70':
                seq = int.from_bytes(data[2:6], 'big', signed=True)
                print(f"[srv] ack: received acknowledgment of seq {seq}")
                return seq
            elif type_msg == '50':
                    print(f"[log] fim: finished connection, file uploaded")
                    self.tcp_sock.close()
                    return FIM
        except:
            return 
            
    def file_in_list(self, file_name, file_size):
        file = open(file_name.strip(), 'rb')
        list_frames = []
        if file_size >= 1000:
            size_frame = 1000
        else:
            size_frame = file_size
        i = 0
        while file_size != 0:
            if (file_size - size_frame < 0):
                size_frame = file_size
            frame = {'seq': i, 'bytes': file.read(size_frame), 'size': size_frame}
            list_frames.append(frame)
            i += 1
            file_size -= size_frame
        return list_frames
        
    def check_window_size(self):
        if self.win_size > self.total_frames:
            print("window size is larger than the number of frames, fixing...")
            self.win_size = self.total_frames
            self.last_frame = self.total_frames
    
    def send_frame(self, j):
        data = '61'.encode() + self.list_frames[j]['seq'].to_bytes(4, 'big')
        data += (self.list_frames[j]['size']).to_bytes(2, 'big') + self.list_frames[j]['bytes']
        self.udp_sock.sendto(data, (self.host, self.udp_port))
        print(f"[cli] file: sent seq {self.list_frames[j]['seq']}/{self.total_frames - 1}")

    def timeout(self, timer):
        if timer == 0:
            return False
        return time.time() - timer >= TIME_OUT

    def go_back_n(self):
        send_base, next_seq_num = 0, 0
        timer = 0
        while True:
            if next_seq_num < send_base + self.win_size and next_seq_num < self.total_frames:
                self.send_frame(next_seq_num)
                next_seq_num += 1
            seq_recv = self.recv_ack()
            if seq_recv == FIM:
                return
            if seq_recv != None:
                if send_base == seq_recv:
                    send_base += 1
                    timer = 0
                elif timer == 0: 
                    timer = time.time()
            if self.timeout(timer):
                print("timeout, resending...")
                timer = time.time()
                next_seq_num = send_base

    def send_file(self, file_name, file_size):
        self.list_frames = self.file_in_list(file_name, file_size)
        self.total_frames = len(self.list_frames)
        self.check_window_size()        
        self.go_back_n()
        print("[log] file: finished uploading the file")

    def client_thread(self, file_name, file_size):
        self.send_hello()
        self.udp_port = self.recv_connection()
        self.send_info_file(file_name, file_size)
        self.recv_ok()
        self.send_file(file_name, file_size)

    def connection(self):
        try:
            file_name, file_size = self.get_info_file()
            self.tcp_sock.connect((self.host, self.tcp_port))
            print(f"connect to {self.host} {self.tcp_port}")
            self.client_thread(file_name, file_size)
        except KeyboardInterrupt:
            print(" interrupting...")
        except ConnectionRefusedError:
            print("server not connected")
        except socket.gaierror:
            print("name or service not known")
        except OSError:
            print("network is unreachable")
        except OverflowError:
            print("port must be 0-65535")

def verify_args():
    if len(sys.argv) < 4:
        print(f"usage: {sys.argv[0]} <server IPv4 or IPv6> <server port> <file>")
        print(f"example: {sys.argv[0]} 127.0.0.1 51511 teste.txt")
        print(f"example: {sys.argv[0]} ::1 51511 teste.txt")
        exit(1)
  
if __name__ == '__main__':
    try:
        verify_args()
        host, port= sys.argv[1], int(sys.argv[2])
        client = Client(host, port)
    except ValueError:
        print("invalid arguments, port is an int")
