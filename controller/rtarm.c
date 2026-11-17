/* rtarm: 1 kHz joint-space controller for a 7-DoF arm over UDP.
 * Builds with qcc for QNX 8.0 (timer pulses on a channel, SCHED_FIFO) and with gcc on Linux
 * (clock_nanosleep TIMER_ABSTIME) as the baseline. Same control law, same wire protocol (proto.h).
 *
 *   rtarm -p <plant_ip> [-P 47400] [-s seconds] [-r prio] [-w watchdog_ms] [-l tick_log.csv]
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <math.h>
#include <netinet/in.h>
#include <pthread.h>
#include <sched.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
#ifdef __QNX__
#include <sys/neutrino.h>
#include <sys/siginfo.h>
#endif
#include "proto.h"

#define PERIOD_NS 1000000LL
static const double HOME[RTARM_NJ] = {0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785};
static const double KP[RTARM_NJ] = {600, 600, 600, 600, 250, 150, 50};
static const double KD[RTARM_NJ] = {50, 50, 50, 50, 30, 25, 15};
static const double TAU_MAX[RTARM_NJ] = {87, 87, 87, 87, 12, 12, 12};

static uint64_t now_ns(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000000ull + (uint64_t)t.tv_nsec;
}

/* ---- periodic tick source ---- */
#ifdef __QNX__
static int chid = -1;
static void tick_init(int pprio) {
    /* explicit pulse priority: the receiving thread runs at the pulse's priority, so it must match -r */
    chid = ChannelCreate(_NTO_CHF_PRIVATE);
    int coid = ConnectAttach(0, 0, chid, _NTO_SIDE_CHANNEL, 0);
    struct sigevent ev; SIGEV_PULSE_INIT(&ev, coid, pprio, _PULSE_CODE_MINAVAIL, 0);
    timer_t tid; if (timer_create(CLOCK_MONOTONIC, &ev, &tid) == -1) { perror("timer_create"); exit(1); }
    struct itimerspec it = {{0, PERIOD_NS}, {0, PERIOD_NS}};
    timer_settime(tid, 0, &it, NULL);
}
static void tick_wait(void) { struct _pulse p; MsgReceivePulse(chid, &p, sizeof p, NULL); }
#else
static struct timespec next;
static void tick_init(int pprio) { (void)pprio; clock_gettime(CLOCK_MONOTONIC, &next); }
static void tick_wait(void) {
    next.tv_nsec += PERIOD_NS;
    while (next.tv_nsec >= 1000000000L) { next.tv_nsec -= 1000000000L; next.tv_sec++; }
    while (clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL) == EINTR) {}
}
#endif

static double clampd(double v, double m) { return v > m ? m : (v < -m ? -m : v); }

int main(int argc, char **argv) {
    const char *plant = "10.0.2.2", *logpath = NULL; int port = 47400, prio = 0; double secs = 20, wd_ms = 20;
    for (int c; (c = getopt(argc, argv, "p:P:s:r:w:l:")) != -1;) switch (c) {
        case 'p': plant = optarg; break; case 'P': port = atoi(optarg); break; case 's': secs = atof(optarg); break;
        case 'r': prio = atoi(optarg); break; case 'w': wd_ms = atof(optarg); break; case 'l': logpath = optarg; break;
        default: fprintf(stderr, "usage: rtarm -p ip [-P port] [-s secs] [-r prio] [-w watchdog_ms] [-l log.csv]\n"); return 2; }
    if (prio > 0) {
        struct sched_param sp = {.sched_priority = prio};
        int e = pthread_setschedparam(pthread_self(), SCHED_FIFO, &sp);
        fprintf(stderr, "rtarm: SCHED_FIFO prio %d %s\n", prio, e ? strerror(e) : "ok");
    }
    int s = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in dst = {.sin_family = AF_INET, .sin_port = htons(port)}; inet_pton(AF_INET, plant, &dst.sin_addr);
    long n = (long)(secs * 1000.0);
    uint64_t *tk = calloc(n, sizeof *tk); uint32_t *st = calloc(n, sizeof *st); uint8_t *es = calloc(n, 1);
    rtarm_state_t x; memset(&x, 0, sizeof x); int have = 0; uint64_t last_rx = 0; int estop = 0; uint32_t estop_tick = 0;
    double q0[RTARM_NJ]; for (int j = 0; j < RTARM_NJ; j++) q0[j] = HOME[j];
    tick_init(prio > 0 ? prio : 10);
    rtarm_cmd_t cmd = {.magic = RTARM_CMD_MAGIC};
    sendto(s, &cmd, sizeof cmd, 0, (struct sockaddr *)&dst, sizeof dst); /* hello: plant learns our address */
    for (long k = 0; k < n; k++) {
        tick_wait();
        uint64_t t = now_ns(); tk[k] = t;
        /* drain every state that arrived since the last tick, keep the newest */
        rtarm_state_t in; ssize_t r;
        while ((r = recvfrom(s, &in, sizeof in, MSG_DONTWAIT, NULL, NULL)) == (ssize_t)sizeof in)
            if (in.magic == RTARM_STATE_MAGIC) { x = in; have = 1; last_rx = t; }
        st[k] = have ? x.seq : 0;
        /* watchdog: no fresh state within wd_ms -> latch e-stop (damping + gravity only) */
        if (have && !estop && (double)(t - last_rx) > wd_ms * 1e6) { estop = 1; estop_tick = (uint32_t)k;
            fprintf(stderr, "rtarm: WATCHDOG e-stop at tick %ld, last state %.1f ms ago\n", k, (t - last_rx) / 1e6); }
        es[k] = (uint8_t)estop;
        double ts = k * 1e-3;
        for (int j = 0; j < RTARM_NJ; j++) {
            double qd_ref = 0, q_ref = q0[j];
            if (!estop && j < 4) { double A = (j == 1 || j == 3) ? 0.35 : 0.5, w = 2 * M_PI * 0.25;
                q_ref += A * sin(w * ts); qd_ref = A * w * cos(w * ts); }
            double u = estop ? x.g[j] - KD[j] * x.qd[j]
                             : x.g[j] + KP[j] * (q_ref - x.q[j]) + KD[j] * (qd_ref - x.qd[j]);
            cmd.tau[j] = have ? clampd(u, TAU_MAX[j]) : 0.0;
        }
        cmd.seq = x.seq; cmd.tick = (uint32_t)k; cmd.flags = estop ? RTARM_FLAG_ESTOP : 0; cmd.t_ctrl_ns = now_ns();
        sendto(s, &cmd, sizeof cmd, 0, (struct sockaddr *)&dst, sizeof dst);
    }
    /* timing report */
    double mn = 1e18, mx = 0, sum = 0, sum2 = 0; long over = 0;
    for (long k = 1; k < n; k++) { double p = (double)(tk[k] - tk[k - 1]) / 1e3; /* us */
        mn = p < mn ? p : mn; mx = p > mx ? p : mx; sum += p; sum2 += p * p; if (p > 1100.0) over++; }
    double mean = sum / (n - 1), sd = sqrt(sum2 / (n - 1) - mean * mean);
    printf("rtarm %s: ticks=%ld period_us mean=%.2f sd=%.2f min=%.1f max=%.1f late>1.1ms=%ld estop=%d",
#ifdef __QNX__
           "qnx",
#else
           "linux",
#endif
           n, mean, sd, mn, mx, over, estop);
    if (estop) printf(" estop_tick=%u", estop_tick);
    printf("\n");
    if (logpath) { FILE *f = fopen(logpath, "w"); fprintf(f, "tick,t_ns,state_seq,estop\n");
        for (long k = 0; k < n; k++) fprintf(f, "%ld,%llu,%u,%u\n", k, (unsigned long long)tk[k], st[k], es[k]);
        fclose(f); }
    return 0;
}
