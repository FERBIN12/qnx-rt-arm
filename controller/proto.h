/* Wire protocol between the controller (QNX 8.0 target) and the MuJoCo plant (Linux host).
 * Little-endian, packed, UDP. One state packet per plant step, one command packet per control tick. */
#ifndef RTARM_PROTO_H
#define RTARM_PROTO_H
#include <stdint.h>
#define RTARM_NJ 7
#define RTARM_STATE_MAGIC 0x52544153u /* "RTAS" */
#define RTARM_CMD_MAGIC   0x52544143u /* "RTAC" */
#define RTARM_FLAG_ESTOP  0x1u
#pragma pack(push, 1)
typedef struct {
    uint32_t magic, seq;
    double   t_sim;              /* plant time [s] */
    double   q[RTARM_NJ];        /* joint position [rad] */
    double   qd[RTARM_NJ];       /* joint velocity [rad/s] */
    double   g[RTARM_NJ];        /* gravity+bias torque from the plant model, like a robot driver reports it [Nm] */
} rtarm_state_t;
typedef struct {
    uint32_t magic, seq;         /* seq of the state this command answers */
    uint32_t flags;
    uint32_t tick;               /* controller tick counter */
    uint64_t t_ctrl_ns;          /* controller monotonic time at send */
    double   tau[RTARM_NJ];      /* joint torque command [Nm] */
} rtarm_cmd_t;
#pragma pack(pop)
#endif
