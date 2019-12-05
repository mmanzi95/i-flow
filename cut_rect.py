""" Test cut efficiency with rectangular cuts """

import numpy as np
import tensorflow as tf
import tensorflow_probability as tfp
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, Point
from descartes.patch import PolygonPatch
import corner

from flow.integration import integrator
from flow.integration import couplings
from flow.splines.spline import _knot_positions, _search_sorted
from flow.splines.spline import _gather_squeeze

tfd = tfp.distributions  # pylint: disable=invalid-name
tf.keras.backend.set_floatx('float64')

CUT_VALUE = 0.05
ALPHA = 1.0
COLOR = ['red', 'magenta', 'green', 'blue', 'black']


def func(pts_x):
    """ Calculate function for testing. """
    return tf.where(pts_x[:, 0] > CUT_VALUE, tf.pow(pts_x[:, 0], -ALPHA), 0)


class Cheese:
    """ Class to store the cheese function. """

    def __init__(self, nholes):
        """ Init cheese function holes. """

        # Create random holes
        self.position = np.random.random((nholes, 2))
        self.radius = 0.1*np.random.random(nholes)+0.05

        # Create shape
        holes = Point(self.position[0]).buffer(self.radius[0])
        for i in range(1, nholes):
            circle = Point(self.position[i]).buffer(self.radius[i])
            holes = holes.union(circle)

        self.cheese = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        self.cheese = self.cheese.symmetric_difference(holes)

    def __call__(self, pts):
        """ Calculate a swiss cheese like function. """
        mask = np.zeros_like(pts[:, 0], dtype=np.float64)
        for i, position in enumerate(pts):
            point = Point(position[0], position[1])
            mask[i] = float(self.cheese.contains(point))

        return mask

    def plot(self, pts=None, filename=None):
        """ Plot the cheese. """
        patch = PolygonPatch(self.cheese, facecolor='yellow',
                             alpha=0.5, zorder=1)
        fig = plt.figure()
        axis = fig.add_subplot(111)
        if pts is not None:
            plt.scatter(pts[:, 0], pts[:, 1], s=5, zorder=2)
        axis.add_patch(patch)
        plt.xlim([0, 1])
        plt.ylim([0, 1])
        if filename is not None:
            plt.savefig('{}.png'.format(filename))
        plt.show()

    @property
    def area(self):
        """ Get the area of cheese surface. """
        return self.cheese.area


class Ring:
    """ Class to store the ring function. """

    def __init__(self, radius1, radius2):
        """ Init ring function. """

        # Ensure raidus1 is the large one
        if radius1 < radius2:
            radius1, radius2 = radius2, radius1

        # Create shape
        # self.ring = Point((0.5, 0.5)).buffer(radius1)
        # hole = Point((0.5, 0.5)).buffer(radius2)
        # self.ring = self.ring.symmetric_difference(hole)
        self.radius12 = radius1**2
        self.radius22 = radius2**2

    def __call__(self, pts):
        """ Calculate a ring like function. """
        radius = tf.reduce_sum((pts-0.5)**2, axis=-1)
        out_of_bounds = (radius < self.radius22) | (radius > self.radius12)
        ret = tf.where(out_of_bounds, tf.zeros_like(radius), tf.ones_like(radius))
        return ret

    def plot(self, pts=None, filename=None, lines=None):
        """ Plot the ring. """
        return
        patch = PolygonPatch(self.ring, facecolor='red',
                             alpha=0.5, zorder=1)
        fig = plt.figure()
        axis = fig.add_subplot(111)
        if pts is not None:
            plt.scatter(pts[:, 0], pts[:, 1], s=5, zorder=2)
        if lines is not None:
            for i in range(5):
                position = float(i)/10.0 + 0.1
                plt.axvline(x=position, color=COLOR[i])
        axis.add_patch(patch)
        plt.xlim([0, 1])
        plt.ylim([0, 1])
        if filename is not None:
            plt.savefig('{}.png'.format(filename))
        plt.show()

    @property
    def area(self):
        """ Get the area of ring surface. """
        return np.pi*(self.radius12 - self.radius22)

class Rectangle:
    """ Class to store a rectangular function. """

    def __init__(self, cut1, cut2, cut3, cut4, cut5, cut6):
        """ Init function. """

        self.cut1 = cut1
        self.cut2 = cut2
        self.cut3 = cut3
        self.cut4 = cut4
        self.cut5 = cut5
        self.cut6 = cut6

    def __call__(self, pts):
        """ Calculate the function. """
        out_of_bounds = ((pts[:,0] < self.cut1 ) | (pts[:,1] < self.cut2 ) | (pts[:,2] < self.cut3 ) | (pts[:,3] > self.cut4 ) | (pts[:,4] > self.cut5 ) | (pts[:,5] > self.cut6 ))
        ret = tf.where(out_of_bounds, tf.zeros_like(tf.reduce_sum(pts, axis=-1)), tf.ones_like(tf.reduce_sum(pts, axis=-1)))
        return ret

#    def plot(self, pts=None, filename=None, lines=None):
#        """ Plot the ring. """
#        return
#        patch = PolygonPatch(self.ring, facecolor='red',
#                             alpha=0.5, zorder=1)
#        fig = plt.figure()
#        axis = fig.add_subplot(111)
#        if pts is not None:
#            plt.scatter(pts[:, 0], pts[:, 1], s=5, zorder=2)
#        if lines is not None:
#            for i in range(5):
#                position = float(i)/10.0 + 0.1
#                plt.axvline(x=position, color=COLOR[i])
#        axis.add_patch(patch)
#        plt.xlim([0, 1])
#        plt.ylim([0, 1])
#        if filename is not None:
#            plt.savefig('{}.png'.format(filename))
#        plt.show()
#
    @property
    def volume(self):
        """ Get the volume. """
        return (1.-self.cut1)*(1.-self.cut2)*(1.-self.cut3)*self.cut4*self.cut5*self.cut6


def get_spline(inputs, widths, heights, derivatives):
    """ Get the points of the splines to plot. """
    min_bin_width = 1e-15
    min_bin_height = 1e-15
    min_derivative = 1e-15

    num_bins = widths.shape[-1]

    widths = tf.nn.softmax(widths, axis=-1)
    widths = min_bin_width + (1 - min_bin_width * num_bins) * widths
    cumwidths = _knot_positions(widths, 0)
    widths = cumwidths[..., 1:] - cumwidths[..., :-1]

    derivatives = ((min_derivative + tf.nn.softplus(derivatives))
                   / (tf.cast(min_derivative + tf.math.log(2.), tf.float64)))

    heights = tf.nn.softmax(heights, axis=-1)
    heights = min_bin_height + (1 - min_bin_height * num_bins) * heights
    cumheights = _knot_positions(heights, 0)
    heights = cumheights[..., 1:] - cumheights[..., :-1]

    bin_idx = _search_sorted(cumwidths, inputs)

    input_cumwidths = _gather_squeeze(cumwidths, bin_idx)
    input_bin_widths = _gather_squeeze(widths, bin_idx)

    input_cumheights = _gather_squeeze(cumheights, bin_idx)
    delta = heights / widths
    input_delta = _gather_squeeze(delta, bin_idx)

    input_derivatives = _gather_squeeze(derivatives, bin_idx)
    input_derivatives_p1 = _gather_squeeze(derivatives[..., 1:], bin_idx)

    input_heights = _gather_squeeze(heights, bin_idx)

    theta = (inputs - input_cumwidths) / input_bin_widths
    theta_one_minus_theta = theta * (1 - theta)

    numerator = input_heights * (input_delta * theta**2
                                 + input_derivatives
                                 * theta_one_minus_theta)
    denominator = input_delta + ((input_derivatives + input_derivatives_p1
                                  - 2 * input_delta)
                                 * theta_one_minus_theta)
    outputs = input_cumheights + numerator / denominator

    return outputs, cumwidths, cumheights


def plot_spline(widths, heights, derivatives, color):
    """ Plot the spline. """
    nsamples = 10000
    # nodes = 5

    pts_x = np.linspace(0, 1, nsamples).reshape(nsamples, 1)
    widths = np.array([widths.numpy().tolist()]*nsamples)
    heights = np.array([heights.numpy().tolist()]*nsamples)
    derivatives = np.array([derivatives.numpy().tolist()]*nsamples)

    outputs, widths, heights = get_spline(pts_x, widths, heights, derivatives)

    plt.plot(pts_x, outputs, zorder=1, color=color)
    plt.scatter(widths.numpy(), heights.numpy(), s=20, color='red', zorder=2)
    # plt.axhline(y=CUT_VALUE)
    # plt.axvline(x=CUT_VALUE)


def build(in_features, out_features, options):
    " Build the NN. """
    del options

    invals = tf.keras.layers.Input(in_features, dtype=tf.float64)
    hidden = tf.keras.layers.Dense(128, activation='relu')(invals)
    #hidden = tf.keras.layers.Dense(128, activation='relu')(hidden)
    hidden = tf.keras.layers.Dense(128, activation='relu')(hidden)
    hidden = tf.keras.layers.Dense(128, activation='relu')(hidden)
    outputs = tf.keras.layers.Dense(out_features, bias_initializer='zeros',
                                    kernel_initializer='zeros')(hidden)
    model = tf.keras.models.Model(invals, outputs)
    model.summary()
    return model


def one_blob(xd, nbins_in):
    """ Perform one_blob encoding. """
    num_identity_features = xd.shape[-1]
    y = tf.tile(((0.5/nbins_in) + tf.range(0., 1.,
                                           delta=1./nbins_in)),
                [tf.size(xd)])
    y = tf.cast(tf.reshape(y, (-1, num_identity_features,
                               nbins_in)),
                dtype=tf.float64)
    res = tf.exp(((-nbins_in*nbins_in)/2.)
                 * (y-xd[..., tf.newaxis])**2)
    res = tf.reshape(res, (-1, num_identity_features*nbins_in))
    return res


def main():
    """ Main function """
    quadratic = False
    # tf.config.experimental_run_functions_eagerly(True)

    func = Rectangle(0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
    print("Actual Volume is {}".format(func.volume))
    
    nsamples = 10000
    hist2d_kwargs = {'smooth': 2, 'plot_datapoints': True, 'plot_contours': False, 'plot_density': False}
    pts = np.random.rand(nsamples,6)
    figure = corner.corner(pts, labels=[r'$x_{{{}}}$'.format(x)
                                        for x in range(6)],
                           show_titles=True,
                           weights = func(pts).numpy(),
                           title_kwargs={'fontsize': 12},
                           range=6*[[0, 1]],
                           **hist2d_kwargs)
    plt.savefig('rectangle_corner_target.png')
    plt.show()
    bijectors = []
    num_bins = 6
    num_blob = None
    if quadratic:
        bijectors.append(couplings.PiecewiseQuadratic([1, 0, 1, 0, 1, 0], build,
                                                              num_bins=num_bins,
                                                              blob=num_blob,
                                                              options=None))
        bijectors.append(couplings.PiecewiseQuadratic([0, 1, 0, 1, 0, 1], build,
                                                              num_bins=num_bins,
                                                              blob=num_blob,
                                                              options=None))
        bijectors.append(couplings.PiecewiseQuadratic([1, 1, 0, 0, 1, 1], build,
                                                              num_bins=num_bins,
                                                              blob=num_blob,
                                                              options=None))
        bijectors.append(couplings.PiecewiseQuadratic([0, 0, 1, 1, 0, 0], build,
                                                              num_bins=num_bins,
                                                              blob=num_blob,
                                                              options=None))
        bijectors.append(couplings.PiecewiseQuadratic([1, 1, 1, 0, 0, 0], build,
                                                              num_bins=num_bins,
                                                              blob=num_blob,
                                                              options=None))
        bijectors.append(couplings.PiecewiseQuadratic([0, 0, 0, 1, 1, 1], build,
                                                              num_bins=num_bins,
                                                              blob=num_blob,
                                                              options=None))
    else:
        bijectors.append(couplings.PiecewiseRationalQuadratic([1, 0, 1, 0, 1, 0], build,
                                                              num_bins=num_bins,
                                                              blob=num_blob,
                                                              options=None))
        bijectors.append(couplings.PiecewiseRationalQuadratic([0, 1, 0, 1, 0, 1], build,
                                                              num_bins=num_bins,
                                                              blob=num_blob,
                                                              options=None))
        bijectors.append(couplings.PiecewiseRationalQuadratic([1, 1, 0, 0, 1, 1], build,
                                                              num_bins=num_bins,
                                                              blob=num_blob,
                                                              options=None))
        bijectors.append(couplings.PiecewiseRationalQuadratic([0, 0, 1, 1, 0, 0], build,
                                                              num_bins=num_bins,
                                                              blob=num_blob,
                                                              options=None))
        bijectors.append(couplings.PiecewiseRationalQuadratic([1, 1, 1, 0, 0, 0], build,
                                                              num_bins=num_bins,
                                                              blob=num_blob,
                                                              options=None))
        bijectors.append(couplings.PiecewiseRationalQuadratic([0, 0, 0, 1, 1, 1], build,
                                                              num_bins=num_bins,
                                                              blob=num_blob,
                                                              options=None))

    bijector = tfp.bijectors.Chain(list(reversed(bijectors)))
    low = np.array([0, 0, 0, 0, 0, 0], dtype=np.float64)
    high = np.array([1, 1, 1, 1, 1, 1], dtype=np.float64)
    dist = tfd.Uniform(low=low, high=high)
    dist = tfd.Independent(distribution=dist,
                           reinterpreted_batch_ndims=1)
    dist = tfd.TransformedDistribution(
        distribution=dist,
        bijector=bijector)
    lr_schedule = tf.keras.optimizers.schedules.ExponentialDecay(
        2e-3, decay_steps=100, decay_rate=0.5)
    optimizer = tf.keras.optimizers.Adam(lr_schedule, clipnorm=10.0)
    integrate = integrator.Integrator(func, dist, optimizer,
                                      loss_func='exponential')
    
    #if not quadratic:
    #    num = 0
    #    for elem in dist.bijector.bijectors:
    #
    #        for i in range(5):
    #            point = float(i)/10.0 + 0.1
    #            # transform_params = bijector.transform_net(
    #            #     one_blob(np.array([[point]]), 16))
    #            #transform_params = bijector.transform_net(np.array([[point]]))
    #            transform_params = elem.transform_net(np.array([[point]]))
    #
    #            widths = transform_params[..., :num_bins]
    #            heights = transform_params[..., num_bins:2*num_bins]
    #            derivatives = transform_params[..., 2*num_bins:]
    #            plot_spline(widths, heights, derivatives, COLOR[i])
    #
    #        plt.savefig('pretraining_{}.png'.format(num))
    #        plt.show()
    #        num += 1

    #cheese.plot(filename='cheese', lines=True)

    for epoch in range(500):
        loss, integral, error = integrate.train_one_step(20000,
                                                         integral=True)
        if epoch % 1 == 0:
            print('Epoch: {:3d} Loss = {:8e} Integral = '
                  '{:8e} +/- {:8e}'.format(epoch, loss, integral, error))
    #if not quadratic:
    #    num = 0
    #    for elem in dist.bijector.bijectors:
    #        for i in range(5):
    #            point = float(i)/10.0 + 0.1
    #            # transform_params = bijector.transform_net(
    #            #     one_blob(np.array([[point]]), 16))
    #            #transform_params = bijector.transform_net(np.array([[point]]))
    #            transform_params = elem.transform_net(np.array([[point]]))
    #            widths = transform_params[..., :num_bins]
    #            heights = transform_params[..., num_bins:2*num_bins]
    #            derivatives = transform_params[..., 2*num_bins:]
    #            plot_spline(widths, heights, derivatives, COLOR[i])
    #
    #        plt.savefig('posttraining_{}.png'.format(num))
    #        num += 1
    #        plt.show()

    nsamples = 100000
    hist2d_kwargs = {'smooth': 2, 'plot_datapoints': True, 'plot_contours': False, 'plot_density': False}
    pts = integrate.sample(nsamples)
    figure = corner.corner(pts, labels=[r'$x_{{{}}}$'.format(x)
                                        for x in range(6)],
                           show_titles=True,
                           title_kwargs={'fontsize': 12},
                           range=6*[[0, 1]],
                           **hist2d_kwargs)
    plt.savefig('rectangle_corner.png')
    plt.show()

    print(np.unique(func(pts).numpy(), return_counts=True))
    #fig = plt.figure(dpi=150,figsize=[4.,4.])
    #axis = fig.add_subplot(111)
    #radius = np.sqrt((pts[:, 0]-0.5)**2 + (pts[:, 1]-0.5)**2)
    #in_ring = np.logical_and(radius > inner, radius < outer)
    #print(np.unique(in_ring, return_counts=True))
    #color_ring = np.where(in_ring, 'blue', 'red')
    #print(color_ring)
    #inner_circle = plt.Circle((0.5, 0.5), inner, color='k', fill=False)
    #outer_circle = plt.Circle((0.5, 0.5), outer, color='k', fill=False)
    #plt.scatter(pts[:, 0], pts[:, 1], s=1, color=color_ring)#, zorder=2)
    #axis.add_artist(inner_circle)
    #axis.add_artist(outer_circle)
    #plt.xlim([0, 1])
    #plt.ylim([0, 1])
    #plt.savefig('ring.png')
    #plt.show()
    #plt.close()

    fig = plt.figure(dpi=150,figsize=[4.,4.])
    axis = fig.add_subplot(111)

    pts = np.random.rand(nsamples, 6)
    pvalue = func(pts)
    qvalue = integrate.dist.prob(pts)
    plt.scatter(qvalue.numpy(), pvalue.numpy(), s=1)
    plt.savefig('pq_scatter_rectangle.png')
    plt.show()
    plt.close()

if __name__ == '__main__':
    main()
