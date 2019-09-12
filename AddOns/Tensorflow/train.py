import numpy as np
import tensorflow as tf
import tensorflow_probability as tfp
from flow.integration import integrator
from flow.integration import couplings
from absl import flags
from absl import app
import matplotlib.pyplot as plt
import corner

tfb = tfp.bijectors
tfd = tfp.distributions

tf.keras.backend.set_floatx('float64')

FLAGS = flags.FLAGS
flags.DEFINE_float('lr', 1e-3, 'Learning rate')
flags.DEFINE_integer('epochs', 100, 'Number of epochs', short_name='e')
flags.DEFINE_integer('nsamples', 1000, 'Number of samples per epoch', short_name='s')
flags.DEFINE_integer('nlayers', 4, 'Number of bijector layers', short_name='l')
flags.DEFINE_bool('eager', None, 'Whether to execute eagerly')
flags.DEFINE_bool('acceptance', None, 'Whether to calculate acceptance after training', short_name='a')
flags.DEFINE_integer('printout', 10, 'How often to print out the status of the loss')
flags.DEFINE_bool('plot', None, 'Whether to plot the corner plots during training', short_name='p')
flags.DEFINE_bool('matrix', None, 'Whether to brute force plot the matrix elements', short_name='m')

sherpa_module = tf.load_op_library('.libs/libSherpaTF.so')
call_sherpa = sherpa_module.call_sherpa

def build_dense(in_features, out_features):
    invals = tf.keras.layers.Input(in_features, dtype=tf.float64)
    h = tf.keras.layers.Dense(128, activation='relu')(invals)
    h = tf.keras.layers.Dense(128, activation='relu')(h)
    outputs = tf.keras.layers.Dense(out_features)(h)
    model = tf.keras.models.Model(invals, outputs)
    model.summary()
    return model

def mask_alternating(ndims, even=True):
    mask = np.zeros(ndims)
    start = 0 if even else 1
    mask[start::2] += 1
    return mask
    
def mask_split(ndims, first=True):
    mask = np.zeros(ndims)
    midpoint = ndims // 2
    if not first:
        mask[midpoint:] += 1
    else:
        mask[:midpoint] += 1
    return mask

def mask_random(ndims):
    return np.random.shuffle(mask_split(ndims))

def mask_flip(mask):
    return 1-mask

def build_network(channel_masks, ps_masks, num_bins = 32, blob = None):
    bijectors = []
    for mask in channel_masks:
        bijectors.append(couplings.PiecewiseLinear(mask,build_dense,
                                                   num_bins = num_bins,
                                                   blob = blob))

    for bijector in bijectors:
        for layer in bijector.transform_net.layers:
            layer.trainable = False

    for mask in ps_masks:
        bijectors.append(couplings.PiecewiseRationalQuadratic(mask,build_dense,
                                                              num_bins = num_bins,
                                                              blob = blob))

    bijectors = tfb.Chain(list(reversed(bijectors)))
   
    ndims = len(ps_masks[0])
    low = np.zeros(ndims,dtype=np.float64)
    high = np.ones(ndims,dtype=np.float64)
    base_dist = tfd.Uniform(low=low, high=high)
    base_dist = tfd.Independent(distribution = base_dist,
                                reinterpreted_batch_ndims=1,
                                )

    dist = tfd.TransformedDistribution(
            distribution = base_dist,
            bijector = bijectors,
    )

    return dist

def parse_input():
    nparts = 0
    try:
        with open('Run.dat') as f:
            for line in f:
                if line.startswith('#'):
                    continue
                line = line.strip().split(';')[:-1]
                for tokens in line:
                    tokens = tokens.strip()
                    if tokens.startswith('Process'):
                        tokens = tokens.split('->')[1]
                        nparts += len(tokens.split())
                    elif tokens.startswith('Decay'):
                        nparts += 1
            return nparts
    except FileNotFoundError:
        raise FileNotFoundError('A Run.dat file is required.')

def main(argv):
    del argv

    # Configuration settings
    tf.config.experimental_run_functions_eagerly(FLAGS.eager)
    printout = FLAGS.printout
    hist2d_kwargs={'smooth':2}

    # Read in information about the process
    nparts = parse_input()
    ndims = 3 * nparts - 4
    nchannels = nparts + 1
    nrans = ndims + nchannels

    # Plot matrix element
    if FLAGS.matrix:
        pts = []
        weights = []
        for _ in range(10):
            x = np.random.random((100000,nrans))
            pts.append(x)
            weights.append(call_sherpa(x))

        pts = np.concatenate(pts)
        weights = np.concatenate(weights)

        figure = corner.corner(pts, weights=weights, labels = [r'$x_{{{}}}$'.format(i) for i in range(nrans)],
                               show_titles=True, title_kwargs={'fontsize': 12},
                               range=nrans*[[0,1]], **hist2d_kwargs)
        plt.savefig('matrix.png')
        plt.close()

    # Create the masks for the bijectors
    channel_mask = np.zeros(nchannels)
    dims_mask = np.zeros(ndims)
    
    channel_masks = []
    channel_masks.append(np.concatenate([dims_mask,np.ones(nchannels)]))
    for i in range(1,nchannels):
        channel_masks.append(np.concatenate([dims_mask,np.zeros(i),np.ones(nchannels-i)]))
#    channel_masks.append(np.concatenate([dims_mask,mask_alternating(nchannels, False)]))
    channel_masks = np.array(channel_masks)

    ps_masks = []
    ps_masks.append(np.concatenate([mask_alternating(ndims),channel_mask]))
    ps_masks.append(np.concatenate([mask_alternating(ndims, False),channel_mask]))
    ps_masks.append(np.concatenate([mask_alternating(ndims),channel_mask]))
    ps_masks.append(np.concatenate([mask_alternating(ndims, False),channel_mask]))
#    ps_masks.append(np.concatenate([mask_split(ndims),channel_mask]))
#    ps_masks.append(np.concatenate([mask_split(ndims, False),channel_mask]))
    ps_masks = np.array(ps_masks)

    # Build the integrator
    dist = build_network(channel_masks, ps_masks)
    lr_schedule = tf.keras.optimizers.schedules.ExponentialDecay(
        FLAGS.lr,decay_steps=100,decay_rate=0.96,
    )
    optimizer = tf.keras.optimizers.Adam(FLAGS.lr, clipnorm = 5.0)
    integrate = integrator.Integrator(call_sherpa, dist, optimizer)

    try:
        for epoch in range(FLAGS.epochs):
            if epoch % printout == 0 and FLAGS.plot:
                samples = integrate.sample(10000)
                figure = corner.corner(samples, labels = [r'$x_{{{}}}$'.format(x) for x in range(nrans)],
                                       show_titles=True, title_kwargs={'fontsize': 12},
                                       range=nrans*[[0,1]], **hist2d_kwargs)

            loss, integral, error = integrate.train_one_step(FLAGS.nsamples, integral=True)
            if epoch % printout == 0:
                print('Epoch: {:4d} Loss = {:8e} Integral = {:8e} +/- {:8e}'
                        .format(epoch, loss, integral, error))

                for bijector in integrate.dist.bijector.bijectors:
                    for layer in bijector.transform_net.layers:
                        layer.trainable = not layer.trainable

                if FLAGS.plot:
                    figure.suptitle('loss = {:8e}'.format(loss.numpy()), fontsize=16, x=0.75)
                    plt.savefig('fig_{:04d}.png'.format(epoch))
                    plt.close()
                    del figure
                    del samples
    except KeyboardInterrupt:
        if FLAGS.plot:
            plt.close()
    print('Epoch: {:4d} Loss = {:8e} Integral = {:8e} +/- {:8e}'.format(epoch, loss, integral, error))

    if FLAGS.acceptance:
        weights = []
        for i in range(10):
            weights.append(integrate.acceptance(10000).numpy())
        weights = np.concatenate(weights)
        average = np.mean(weights)
        max_wgt = np.max(weights)

        print('Acceptance = {}'.format(average/max_wgt))

        print(len(weights) - np.count_nonzero(weights), np.count_nonzero(weights))

        weights = weights[np.nonzero(weights)]
        print(len(weights) - np.count_nonzero(weights), np.count_nonzero(weights))

        print(np.min(weights), np.max(weights))

        plt.hist(weights, bins=np.logspace(np.log10(np.min(weights))-1e-2, 
                                           np.log10(np.max(weights))+1e-2, 100))
        plt.yscale('log')
        plt.xscale('log')
        plt.savefig('efficiency.png')
        plt.close()

        samples = []
        for i in range(10):
            samples.append(integrate.sample(10000).numpy())
        samples = np.concatenate(samples)
        figure = corner.corner(samples, labels = [r'$x_{{{}}}$'.format(x) for x in range(nrans)],
                               show_titles=True, title_kwargs={'fontsize': 12},
                               range=nrans*[[0,1]], **hist2d_kwargs)

        plt.savefig('final_corner.png'.format(epoch))
        plt.close()

if __name__ == '__main__':
    app.run(main)
