#include <math.h>

#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

static double input_slots[1];
static double parameters[2] = {1.2, 2.0};
static double limited_state;

EXPORT void fmi_reset(void) {
    input_slots[0] = 0.0;
    limited_state = 0.0;
}

EXPORT void fmi_set_real(int value_reference, double value) {
    switch (value_reference) {
        case 10: input_slots[0] = value; break;
        case 20: parameters[1] = value; break;
        case 21: parameters[0] = value; break;
        default: break;
    }
}

EXPORT void fmi_do_step(double dt) {
    const double requested_delta = input_slots[0] - limited_state;
    const double applied_delta = fmin(
        fmax(requested_delta, -parameters[0] * dt),
        parameters[1] * dt
    );
    limited_state = limited_state + applied_delta;
}

EXPORT double fmi_get_output(void) {
    return limited_state;
}
