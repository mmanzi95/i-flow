import tensorflow as tf
from flow.splines.spline import _padded, _knot_positions, _gather_squeeze, _search_sorted
import numpy as np

DEFAULT_MIN_BIN_WIDTH = 1e-3
DEFAULT_MIN_BIN_HEIGHT = 1e-3

def quadratic_spline(inputs,
                     unnormalized_widths,
                     unnormalized_heights,
                     inverse=False,
                     left=0., right=1., bottom=0., top=1.,
                     min_bin_width=DEFAULT_MIN_BIN_WIDTH,
                     min_bin_height=DEFAULT_MIN_BIN_HEIGHT):

    if not inverse: 
        out_of_bounds = (inputs < left) | (inputs > right)
        tf.where(out_of_bounds, left, inputs)
    else:
        out_of_bounds = (inputs < bottom) | (inputs > top)
        tf.where(out_of_bounds, bottom, inputs)

    if inverse:
        inputs = (inputs - bottom) / (top - bottom)
    else:
        inputs = (inputs - left) / (right - left)

    num_bins = unnormalized_widths.shape[-1]

    if min_bin_width * num_bins > 1.0:
        raise ValueError('Minimal bin width too large for the number of bins')
    if min_bin_height * num_bins > 1.0:
        raise ValueError('Minimal bin height too large for the number of bins')

    widths = tf.nn.softmax(unnormalized_widths, axis=-1)
    widths = min_bin_width + (1 - min_bin_width * num_bins) * widths

    unnormalized_heights_exp = tf.math.exp(unnormalized_heights)

    if unnormalized_heights_exp.shape[-1] == num_bins - 1:
        # Set boundary heights s.t. after normalization they are exactly 1.
        first_widths = 0.5 * widths[..., 0]
        last_widths = 0.5 * widths[..., -1]
        numerator = (0.5 * first_widths * unnormalized_heights_exp[...,0]
                    + 0.5 * last_widths * unnormalized_heights_exp[...,-1]
                    + tf.reduce_sum(((unnormalized_heights_exp[..., :-1]
                        + unnormalized_heights_exp[..., 1:]) / 2)
                        * widths[..., 1:-1], axis=-1))

        constant = numerator / (1. - 0.5 * first_widths - 0.5 * last_widths)
        constant = constant[..., tf.newaxis]
        unnormalized_heights_exp = tf.concat([constant, unnormalized_heights_exp, constant], axis=-1)

    unnormalized_area = tf.reduce_sum(((unnormalized_heights_exp[..., :-1]
                                      + unnormalized_heights_exp[..., 1:]) / 2.) 
                                      * widths, axis=-1)[..., tf.newaxis]

    heights = unnormalized_heights_exp / unnormalized_area
    heights = min_bin_height + (1. - min_bin_height) * heights

    bin_left_cdf = tf.cumsum(((heights[..., :-1] + heights[..., 1:]) / 2.) * widths, axis=-1)
    bin_left_cdf = _padded(bin_left_cdf,lhs=0.)

    bin_locations = _knot_positions(widths,0.)

    if inverse:
        bin_idx = _search_sorted(bin_left_cdf, inputs)
    else:
        bin_idx = _search_sorted(bin_locations, inputs)

    input_bin_locations = _gather_squeeze(bin_locations, bin_idx)
    input_bin_widths = _gather_squeeze(widths, bin_idx)

    input_left_cdf = _gather_squeeze(bin_left_cdf, bin_idx)
    input_left_heights = _gather_squeeze(heights, bin_idx)
    input_right_heights = _gather_squeeze(heights, bin_idx+1)

    a = 0.5 * (input_right_heights - input_left_heights) * input_bin_widths
    b = input_left_heights * input_bin_widths
    c = input_left_cdf

    if inverse:
        c_ = c - inputs
        alpha = tf.where(a > 1e-3, (-b + tf.sqrt(b**2 - 4*a*c_)) / (2*a), -c_/b)
        outputs = alpha * input_bin_widths + input_bin_locations
    else:
        alpha = (inputs - input_bin_locations) / input_bin_widths
        outputs = a * alpha**2 + b * alpha + c

    outputs = tf.clip_by_value(outputs, 0, 1)
    logabsdet = tf.math.log((alpha * (input_right_heights - input_left_heights)
            + input_left_heights))
    
    if inverse:
        outputs = outputs * (right - left) + left
        logabsdet = -logabsdet - tf.math.log(top - bottom) + tf.math.log(right - left)
    else:
        outputs = outputs * (top - bottom) + bottom
        logabsdet = logabsdet + tf.math.log(top - bottom) - tf.math.log(right - left)

    return outputs, logabsdet
        
if __name__ == '__main__':
    import numpy as np

    nbatch = 10000
    ndims = 10
    num_bins = 32

    unnormalized_widths = np.random.random((nbatch,ndims,num_bins))
    unnormalized_heights = np.random.random((nbatch,ndims,num_bins+1))

    def call_spline_fn(inputs, inverse=False):
        return quadratic_spline(
                inputs=inputs,
                unnormalized_widths=unnormalized_widths,
                unnormalized_heights=unnormalized_heights,
                inverse=inverse
        )

    inputs = np.random.random((nbatch,ndims))
    outputs, logabsdet = call_spline_fn(inputs, inverse=False)
    inputs_inv, logabsdet_inv = call_spline_fn(outputs, inverse=True)

    print(np.allclose(inputs,inputs_inv))