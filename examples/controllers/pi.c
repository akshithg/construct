#include <stddef.h>

#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

static double input_slots[2];
static double parameters[2] = {0.5, 2.0};
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
        case 10: input_slots[1] = value; break; /* setpoint */
        case 11: input_slots[0] = value; break; /* measurement */
        case 20: parameters[1] = value; break;  /* Kp */
        case 21: parameters[0] = value; break;  /* Ki */
        default: break;
    }
}

EXPORT void fmi_do_step(double dt) {
    const double error = input_slots[1] - input_slots[0];
    integral_state = integral_state + dt * error;
    output_value = parameters[1] * error + parameters[0] * integral_state;
}

EXPORT double fmi_get_output(void) {
    return output_value;
}
