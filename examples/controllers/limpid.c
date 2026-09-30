#include <math.h>
#include <stddef.h>

#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

static double input_slots[3];
static double parameters[6] = {0.2, 3.0, 2.5, -2.5, 1.4, 0.4};
static double states[2];
static double output_value;

EXPORT void fmi_reset(void) {
    input_slots[0] = 0.0;
    input_slots[1] = 0.0;
    input_slots[2] = 0.0;
    states[0] = 0.0;
    states[1] = 0.0;
    output_value = 0.0;
}

EXPORT void fmi_set_real(int value_reference, double value) {
    switch (value_reference) {
        case 10: input_slots[2] = value; break; /* setpoint */
        case 11: input_slots[1] = value; break; /* measurement */
        case 12: input_slots[0] = value; break; /* feedforward */
        case 20: parameters[4] = value; break;  /* Kp */
        case 21: parameters[5] = value; break;  /* Ki */
        case 22: parameters[0] = value; break;  /* Kd */
        case 23: parameters[1] = value; break;  /* N */
        case 24: parameters[3] = value; break;  /* yMin */
        case 25: parameters[2] = value; break;  /* yMax */
        default: break;
    }
}

EXPORT void fmi_do_step(double dt) {
    const double error = input_slots[2] - input_slots[1];
    states[0] = states[0] + dt * error;
    states[1] = states[1] + dt * parameters[1] * (error - states[1]);
    const double raw = parameters[4] * error + parameters[5] * states[0]
        + parameters[0] * parameters[1] * (error - states[1]) + input_slots[0];
    output_value = fmin(fmax(raw, parameters[3]), parameters[2]);
}

EXPORT double fmi_get_output(void) {
    return output_value;
}
