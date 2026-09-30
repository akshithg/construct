#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

static double input_slots[2];
static double parameters[1] = {1.8};
static double output_value;

EXPORT void fmi_reset(void) {
    input_slots[0] = 0.0;
    input_slots[1] = 0.0;
    output_value = 0.0;
}

EXPORT void fmi_set_real(int value_reference, double value) {
    switch (value_reference) {
        case 10: input_slots[1] = value; break;
        case 11: input_slots[0] = value; break;
        case 20: parameters[0] = value; break;
        default: break;
    }
}

EXPORT void fmi_do_step(double dt) {
    (void)dt;
    output_value = parameters[0] * (input_slots[1] - input_slots[0]);
}

EXPORT double fmi_get_output(void) {
    return output_value;
}
