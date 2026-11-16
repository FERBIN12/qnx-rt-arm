# Linux baseline: make linux   |   QNX 8.0 (source qnxsdp-env.sh first): make qnx
CFLAGS=-O2 -Wall -Wextra -std=gnu11
linux: controller/rtarm.c controller/proto.h
	mkdir -p build && gcc $(CFLAGS) -o build/rtarm-linux controller/rtarm.c -lm -lpthread
qnx: controller/rtarm.c controller/proto.h
	mkdir -p build && qcc -Vgcc_ntox86_64 $(CFLAGS) -o build/rtarm-qnx controller/rtarm.c -lm -lsocket
clean:
	rm -rf build
