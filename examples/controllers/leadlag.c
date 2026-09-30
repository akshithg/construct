#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

static double input_slots[1];
static double parameters[3] = {0.6, 0.12, 1.3};
static double lag_state;
static double output_value;

EXPORT void fmi_reset(void) {
    input_slots[0] = 0.0;
    lag_state = 0.0;
    output_value = 0.0;
}

EXPORT void fmi_set_real(int value_reference, double value) {
    switch (value_reference) {
        case 10: input_slots[0] = value; break;
        case 20: parameters[2] = value; break;
        case 21: parameters[1] = value; break;
        case 22: parameters[0] = value; break;
        default: break;
    }
}

EXPORT void fmi_do_step(double dt) {
    lag_state = lag_state + dt * (input_slots[0] - lag_state) / parameters[0];
    output_value = parameters[2] * (
        lag_state + parameters[1] * (input_slots[0] - lag_state) / parameters[0]
    );
}

EXPORT double fmi_get_output(void) {
    return output_value;
}
