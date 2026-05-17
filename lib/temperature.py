from math import log

# steinhart-hart coefficients for the thermistor
_A = 0.9086268490e-3
_B = 2.045041393e-4
_C = 1.912131738e-7

# thermistor reference value
_R_REF   = 10000.0

# total ADC steps
_ADC_MAX = 65535.0

# sanity limits for ADC readings
_ADC_MIN_VALID = 1000
_ADC_MAX_VALID = 65000


class Temperature:
    @staticmethod
    def compute(adc, units='c'):
        if adc < _ADC_MIN_VALID or adc > _ADC_MAX_VALID:
            return 0

        r_th = _R_REF * (_ADC_MAX / adc - 1.0)

        ln_r = log(r_th)
        inv_t = _A + _B * ln_r + _C * ln_r * ln_r * ln_r
        t_c = 1.0 / inv_t - 273.15

        if units == 'f':
            return t_c * 9.0 / 5.0 + 32.0
        return t_c
