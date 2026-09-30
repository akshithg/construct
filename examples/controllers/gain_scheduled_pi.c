#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

static double input_slots[3];
static double parameters[5] = {0.5, 0.65, 1.0, 2.2, 0.25};
static double integral_state;
static double output_value;

EXPORT void fmi_reset(void) {
    input_slots[0] = 0.0;
    input_slots[1] = 0.0;
    input_slots[2] = 0.0;
    integral_state = 0.0;
    output_value = 0.0;
}

EXPORT void fmi_set_real(int value_reference, double value) {
    switch (value_reference) {
        case 10: input_slots[2] = value; break;
        case 11: input_slots[1] = value; break;
        case 12: input_slots[0] = value; break;
        case 20: parameters[2] = value; break;
        case 21: parameters[3] = value; break;
        case 22: parameters[4] = value; break;
        case 23: parameters[1] = value; break;
        case 24: parameters[0] = value; break;
        default: break;
    }
}

EXPORT void fmi_do_step(double dt) {
    const double error = input_slots[2] - input_slots[1];
    const double kp = input_slots[0] <= parameters[0] ? parameters[2] : parameters[3];
    const double ki = input_slots[0] <= parameters[0] ? parameters[4] : parameters[1];
    integral_state = integral_state + dt * error;
    output_value = kp * error + ki * integral_state;
}

EXPORT double fmi_get_output(void) {
    return output_value;
}
