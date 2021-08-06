#include "common.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>

#include <sys/types.h>
#include <sys/socket.h>

#include <iostream>
#include <string>
#include <vector>
#include <set>

using namespace std;

#define BUFSZ 500

struct client_data {
    int csock;
    struct sockaddr_storage cstorage;
};

struct subscription {
    int sock;
    set<string> tags;
};

vector<struct subscription*> subscriptions;

void usage(int argc, char** argv) {
    printf("usage: %s <server port>\n", argv[0]);
    printf("example: %s 51511\n", argv[0]);
    exit(EXIT_FAILURE);
}

int get_index(int csock) {
    for (int i = 0; i < (int)subscriptions.size(); i++) {
        if (subscriptions[i]->sock == csock) {
            return i;
        }
    }
    return -1;
}

void delete_client_subscription(int csock) {
    for (auto it = subscriptions.begin(); it != subscriptions.end(); it++) {
        if ((*it)->sock == csock) {
            subscriptions.erase(it);
            break;
        }
    }
}

int validation_char(char letter) {
    return (letter >= 'a' && letter <= 'z') ||
           (letter >= 'A' && letter <= 'Z') ||
           (letter >= '0' && letter <= '9') ||
           strchr(",.?!:;+-*/=@#$%()[]{} \n", letter) != NULL;
}

void kill_check(char buf[]) {
    if (strcmp(buf, "##kill\n") == 0) {
        logexit("kill");
    }
}

int validation_buf(int csock, char buf[], size_t count) {
    int invalid_input = 0;
    for (size_t i = 0; i < strlen(buf); i++) {
        if (!validation_char(buf[i])) {
            invalid_input = 1;
            break;
        }
    }
    if (buf[strlen(buf) - 1] != '\n' || invalid_input || count == 0) {
        delete_client_subscription(csock);
        return 1;
    }
    return 0;
}

set<string> extract_tags_buf(string bufstring) {
    set<string> extracted_tags = {};
    for (int i = 0; i < (int)bufstring.length(); i++) {
        if (bufstring[i] == '#') {
            int start = i + 1;

            while (bufstring[i + 1] != ' ' && bufstring[i + 1] != '\n') {
                i++;
            }

            extracted_tags.insert(bufstring.substr(start, i - start + 1));
        }
    }
    return extracted_tags;
}

set<int> find_sockets(set<string> tags, int current_socket) {
    set<int> sockets = {};
    for (auto it_client = subscriptions.begin(); it_client != subscriptions.end(); it_client++) {
        if ((*it_client)->sock == current_socket) {
            continue;
        }
        for (auto it_tag = tags.begin(); it_tag != tags.end(); it_tag++) {
            if ((*it_client)->tags.find(*it_tag) != (*it_client)->tags.end()) {
                sockets.insert((*it_client)->sock);
                break;
            }
        } 
    }  
    return sockets;
}

void add_tag(string bufstring, int index, char buf[]) {
    memset(buf, 0, strlen(buf));
    string substr = bufstring.substr(1, bufstring.size() - 2); //remove + e \n

    if (substr.find(' ') != string::npos) {
        return;
    }
    if (subscriptions[index]->tags.find(substr) != subscriptions[index]->tags.end()) {
        sprintf(buf, "already subscribed +%s\n", substr.c_str());
    }
    else {
        sprintf(buf, "subscribed +%s\n", substr.c_str());
        subscriptions[index]->tags.insert(substr);
    }
}

void remove_tag(string bufstring, int index, char buf[]) {
    memset(buf, 0, BUFSZ);
    string substr = bufstring.substr(1, bufstring.size() - 2); //remove + e \n

    if (subscriptions[index]->tags.find(substr) != subscriptions[index]->tags.end()) {
        sprintf(buf, "unsubscribed -%s\n", substr.c_str());
        subscriptions[index]->tags.erase(substr);
    }
    else {
        sprintf(buf, "not subscribed -%s\n", substr.c_str());
    }
}

int handle_buf(char buf[], int csock, set<int> *sockets_to_send, set<string> *tags_to_send) {
    string bufstring(buf);
    int index = get_index(csock);
    
    if (buf[0] == '+' && strlen(buf) > 2) {
        add_tag(bufstring, index, buf);
        return 0;
    }
    else if (buf[0] == '-' && strlen(buf) > 2) {
        remove_tag(bufstring, index, buf);
        return 0;
    } else {
        *tags_to_send = extract_tags_buf(bufstring);
        *sockets_to_send = find_sockets(*tags_to_send, csock);
        return 1;
    }
}

void handle_send(char buf[], int message, int csock, set<int>* sockets) {
    size_t count = 0;
    
    if (message) {
        for (auto it = (*sockets).begin(); it != (*sockets).end(); it++) {
            count = send(*it, buf, strlen(buf), 0);
            if (count != strlen(buf)) {
                logexit("send");
            }
        }
    } else {
        count = send(csock, buf, strlen(buf), 0);
        if (count != strlen(buf)) {
            logexit("send");
        }
    }
}

void* server_thread(void* data) {
    struct client_data* cdata = (struct client_data*)data;
    struct sockaddr* caddr = (struct sockaddr*)(&(cdata->cstorage));

    char caddrstr[BUFSZ];
    addrtostr(caddr, caddrstr, BUFSZ);
    printf("[log] connection from %s\n", caddrstr);
    
    set<string> tags;
    struct subscription *client = new struct subscription;
    client->sock = cdata->csock;
    client->tags = tags;
    subscriptions.push_back(client);

    char buf[BUFSZ];

    while(1) {
        set<int> sockets_to_send = {};
        set<string> tags_to_send = {};
        memset(buf, 0, BUFSZ);

        size_t count = 0;
        unsigned int total = 0;
        do {
            count = recv(cdata->csock, buf + total, BUFSZ - total, 0);
            total += count;
        } while(count != 0 && buf[total - 1] != '\n');

        if (validation_buf(cdata->csock, buf, count)) {
            break;
        }

        char tmpbuf[BUFSZ];
        string bufstring(buf);

        for (int i = 0; i < (int)strlen(buf); i++) {
            int start = i;

            while (buf[i] != '\n') {
                i++;
            }
            
            memset(tmpbuf, 0, BUFSZ);
            strcpy(tmpbuf, (bufstring.substr(start, i - start + 1)).c_str());
            printf("[msg] %s, %d bytes: %s", caddrstr, total, tmpbuf);
            kill_check(tmpbuf);
            
            int message = handle_buf(tmpbuf, cdata->csock, &sockets_to_send, &tags_to_send);
            handle_send(tmpbuf, message, cdata->csock, &sockets_to_send);
        }
    } 
    close(cdata->csock);
    free(client);
    pthread_exit(EXIT_SUCCESS);
}

int main(int argc, char** argv) {
    if (argc < 2) {
        usage(argc, argv);
    }

    struct sockaddr_storage storage;
    if (server_sockaddr_init(argv[1], &storage) != 0) {
        usage(argc, argv);
    }

    int sock;
    sock = socket(storage.ss_family, SOCK_STREAM, 0);
    if (sock == -1) {
        logexit("socket");
    }

    int enable = 1;
    if (setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &enable, sizeof(int)) != 0) {
        logexit("setsockopt");
    }

    struct sockaddr* addr = (struct sockaddr*)(&storage);
    if (bind(sock, addr, sizeof(storage)) != 0) {
        logexit("bind");
    }

    if (listen(sock, 10) != 0) {
        logexit("listen");
    }

    char addrstr[BUFSZ];
    addrtostr(addr, addrstr, BUFSZ);
    printf("bound to %s, waiting connections\n", addrstr);

    while (1) {
        struct sockaddr_storage cstorage;
        struct sockaddr* caddr = (struct sockaddr*)(&cstorage);
        socklen_t caddrlen = sizeof(cstorage);

        int csock = accept(sock, caddr, &caddrlen);
        if (csock == -1) {
            logexit("accept");
        }
        
        struct client_data* cdata = new struct client_data; 

        if (!cdata) {
            logexit("new");
        }

        cdata->csock = csock;
        memcpy(&(cdata->cstorage), &cstorage, sizeof(cstorage));

        pthread_t tid;
        pthread_create(&tid, NULL, server_thread, cdata);
    }
    exit(EXIT_SUCCESS);
}
