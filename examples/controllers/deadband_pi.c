#include <math.h>

#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

static double input_slots[2];
static double parameters[3] = {0.75, 0.45, 1.6};
static double integral_state;
static double output_value;

EXPORT void fmi_reset(void) {
    input_slots[0] = 0.0;
    input_slots[1] = 0.0;
    integral_state = 0.0;
    output_value = 0.0;
}

EXPORT void fmi_set_real(int value_reference, double value) {
    switch (value_reference) {
        case 10: input_slots[1] = value; break;
        case 11: input_slots[0] = value; break;
        case 20: parameters[2] = value; break;
        case 21: parameters[1] = value; break;
        case 22: parameters[0] = value; break;
        default: break;
    }
}

EXPORT void fmi_do_step(double dt) {
    const double raw_error = input_slots[1] - input_slots[0];
    double effective_error = 0.0;
    if (fabs(raw_error) > parameters[0]) {
        effective_error = raw_error > 0.0
            ? raw_error - parameters[0]
            : raw_error + parameters[0];
    }
    integral_state = integral_state + dt * effective_error;
    output_value = parameters[2] * effective_error + parameters[1] * integral_state;
}

EXPORT double fmi_get_output(void) {
    return output_value;
}
