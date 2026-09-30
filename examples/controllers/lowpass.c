#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

static double input_slots[1];
static double parameters[1] = {0.35};
static double filtered_state;

EXPORT void fmi_reset(void) {
    input_slots[0] = 0.0;
    filtered_state = 0.0;
}

EXPORT void fmi_set_real(int value_reference, double value) {
    switch (value_reference) {
        case 10: input_slots[0] = value; break;
        case 20: parameters[0] = value; break;
        default: break;
    }
}

EXPORT void fmi_do_step(double dt) {
    filtered_state = filtered_state + dt * (input_slots[0] - filtered_state) / parameters[0];
}

EXPORT double fmi_get_output(void) {
    return filtered_state;
}
