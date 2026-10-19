/* SPDX-License-Identifier: MIT
 * Stream the kernel ring buffer to a previously validated USB log file.
 * O_DSYNC commits each record; never clear the ring or write firmware state.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static volatile sig_atomic_t stopped;
static void stop_handler(int sig) { (void)sig; stopped = 1; }
static int write_all(int fd, const char *buf, size_t len) {
    while (len) {
        ssize_t n = write(fd, buf, len);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return -1;
        buf += n;
        len -= (size_t)n;
    }
    return 0;
}
int main(int argc, char **argv) {
    if (argc != 2) { fprintf(stderr, "usage: kestrel-kmsg USB_LOG_FILE\n"); return 2; }
    int input = open("/dev/kmsg", O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    if (input < 0) { perror("/dev/kmsg"); return 1; }
    int output = open(argv[1], O_WRONLY | O_CREAT | O_APPEND | O_DSYNC | O_CLOEXEC, 0600);
    if (output < 0) { perror("USB log file"); close(input); return 1; }
    struct sigaction action;
    memset(&action, 0, sizeof(action));
    action.sa_handler = stop_handler;
    sigemptyset(&action.sa_mask);
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGINT, &action, NULL);
    /* A newly opened kmsg reader starts at the oldest available record. */
    char record[16384];
    size_t total = 0;
    int rc = 0;
    struct pollfd pfd = { .fd = input, .events = POLLIN };
    while (!stopped && total < 16U * 1024U * 1024U) {
        ssize_t n = read(input, record, sizeof(record));
        if (n > 0) {
            if (write_all(output, record, (size_t)n) < 0) { perror("USB log write"); rc = 1; break; }
            total += (size_t)n;
            continue;
        }
        if (n < 0 && (errno == EINTR || errno == EPIPE)) continue;
        if (n < 0 && errno == EAGAIN) { poll(&pfd, 1, 100); continue; }
        if (n == 0) break;
        perror("kmsg read"); rc = 1; break;
    }
    if (total >= 16U * 1024U * 1024U) {
        static const char note[] = "\nKESTREL_LOG_LIMIT_REACHED (16 MiB)\n";
        if (write_all(output, note, sizeof(note) - 1) < 0) rc = 1;
    }
    if (fdatasync(output) < 0) { perror("USB log sync"); rc = 1; }
    close(output);
    close(input);
    return rc;
}
