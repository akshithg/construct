#include <math.h>

#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

static double input_slots[2];
static double parameters[7] = {0.8, 8.0, 0.12, 3.0, 0.6, -3.0, 1.7};
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
        case 10: input_slots[1] = value; break;
        case 11: input_slots[0] = value; break;
        case 20: parameters[6] = value; break;
        case 21: parameters[4] = value; break;
        case 22: parameters[2] = value; break;
        case 23: parameters[1] = value; break;
        case 24: parameters[5] = value; break;
        case 25: parameters[3] = value; break;
        case 26: parameters[0] = value; break;
        default: break;
    }
}

EXPORT void fmi_do_step(double dt) {
    const double error = input_slots[1] - input_slots[0];
    states[1] = states[1] + dt * parameters[1] * (error - states[1]);
    const double raw = parameters[6] * error + states[0]
        + parameters[2] * parameters[1] * (error - states[1]);
    output_value = fmin(fmax(raw, parameters[5]), parameters[3]);
    states[0] = states[0] + dt * (
        parameters[4] * error + parameters[0] * (output_value - raw)
    );
}

EXPORT double fmi_get_output(void) {
    return output_value;
}
