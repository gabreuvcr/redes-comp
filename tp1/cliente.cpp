#include "common.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>

#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>

#include <iostream>
#include <string>
#include <algorithm>

using namespace std;

#define BUFSZ 500

void usage(int argc, char** argv) {
    printf("usage: %s <server IP> <server port>\n", argv[0]);
    printf("example: %s 127.0.0.1 51511\n", argv[0]);
    exit(EXIT_FAILURE);
}

struct server_data {
    int sock;
    int repeat;
};

void* client_send_thread(void* sdata) {
    struct server_data* data = (struct server_data*)sdata;
    char buf[BUFSZ];
    
    while(1) {
        memset(buf, 0, BUFSZ);
        fgets(buf, BUFSZ, stdin);

        string bufstring(buf);
        remove(bufstring.begin(), bufstring.end(), '\0');

        size_t count = send(data->sock, bufstring.c_str(), bufstring.size(), 0); 

        if (count != bufstring.size()) {
            logexit("send");
        }
    }
}

void* client_recv_thread(void* sdata) {
    struct server_data* data = (struct server_data*)sdata;
    char buf[BUFSZ];
    size_t count = 0;

    while(1) {
        memset(buf, 0, BUFSZ);
        count = recv(data->sock, buf, BUFSZ, 0);
        if (count == 0) {
            data->repeat = 0;
            pthread_exit(EXIT_SUCCESS);
        }

        if (strlen(buf) > 0) {
            printf("< %s", buf);
        }
    }
}

int main(int argc, char** argv) {
    if (argc < 3) {
        usage(argc, argv);
    }
    
    struct sockaddr_storage storage;
    if (addrparse(argv[1], argv[2], &storage) != 0) {
        usage(argc, argv);
    }

    int sock;
    sock = socket(storage.ss_family, SOCK_STREAM, 0);
    if (sock == -1) {
        logexit("socket");
    }

    struct sockaddr* addr = (struct sockaddr*)(&storage);
    if (connect(sock, addr, sizeof(storage)) != 0) {
        logexit("connect");
    }

    char addrstr[BUFSZ];
    addrtostr(addr, addrstr, BUFSZ);
    printf("connect to %s\n", addrstr);

    struct server_data* data = new struct server_data;

    if (!data) {
        logexit("new");
    }

    data->sock = sock;
    data->repeat = 1;

    pthread_t tid_send, tid_recv;
    pthread_create(&tid_send, NULL, client_send_thread, data);
    pthread_create(&tid_recv, NULL, client_recv_thread, data);

    while(data->repeat);

    close(sock);
    exit(EXIT_SUCCESS);
}
