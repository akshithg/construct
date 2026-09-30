#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

static double input_slots[3];
static double parameters[4] = {0.35, 1.1, 1.8, 0.2};
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
        case 10: input_slots[2] = value; break;
        case 11: input_slots[1] = value; break;
        case 12: input_slots[0] = value; break;
        case 20: parameters[1] = value; break;
        case 21: parameters[3] = value; break;
        case 22: parameters[2] = value; break;
        case 23: parameters[0] = value; break;
        default: break;
    }
}

EXPORT void fmi_do_step(double dt) {
    const double outer_error = input_slots[2] - input_slots[1];
    states[0] = states[0] + dt * outer_error;
    const double rate_command = parameters[1] * outer_error + parameters[3] * states[0];
    const double inner_error = rate_command - input_slots[0];
    states[1] = states[1] + dt * inner_error;
    output_value = parameters[2] * inner_error + parameters[0] * states[1];
}

EXPORT double fmi_get_output(void) {
    return output_value;
}
