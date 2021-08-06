all:
	g++ -Wall -c common.cpp
	g++ -Wall cliente.cpp common.o -lpthread -o cliente
	g++ -Wall servidor.cpp common.o -lpthread -o servidor
clean:
	rm common.o cliente servidor
