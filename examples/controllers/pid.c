#include <stddef.h>

#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

static double input_slots[2];
static double parameters[4] = {10.0, 0.15, 2.0, 0.5};
static double states[2];
static double output_value;

EXPORT void fmi_reset(void) {
    input_slots[0] = 0.0;
    input_slots[1] = 0.0;
    states[0] = 0.0;
    states[1] = 0.0;
    output_value = 0.0;
}

EXPORT void fmi_set_real(int value_reference, double value) {
    switch (value_reference) {
        case 10: input_slots[1] = value; break; /* setpoint */
        case 11: input_slots[0] = value; break; /* measurement */
        case 20: parameters[2] = value; break;  /* Kp */
        case 21: parameters[3] = value; break;  /* Ki */
        case 22: parameters[1] = value; break;  /* Kd */
        case 23: parameters[0] = value; break;  /* N */
        default: break;
    }
}

EXPORT void fmi_do_step(double dt) {
    const double error = input_slots[1] - input_slots[0];
    states[0] = states[0] + dt * error;
    states[1] = states[1] + dt * parameters[0] * (error - states[1]);
    output_value = parameters[2] * error + parameters[3] * states[0]
        + parameters[1] * parameters[0] * (error - states[1]);
}

EXPORT double fmi_get_output(void) {
    return output_value;
}
