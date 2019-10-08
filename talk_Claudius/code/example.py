import numpy as np
import tensorflow as tf
import tensorflow_probability as tfp
from flow.integration import integrator
from flow.integration import couplings
from absl import flags
from absl import app
import matplotlib.pyplot as plt
import corner
import vegas

tfb = tfp.bijectors
tfd = tfp.distributions

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

def build_dense(in_features, out_features,options):
    invals = tf.keras.layers.Input(in_features, dtype=tf.float64)
    h = tf.keras.layers.Dense(in_features, activation='relu')(invals)
    h = tf.keras.layers.Dense((in_features+out_features)//2, activation='relu')(h)
    h = tf.keras.layers.Dense((in_features+out_features)//2, activation='relu')(h)
    h = tf.keras.layers.Dense(out_features, activation='relu')(h)
    outputs = tf.keras.layers.Dense(out_features, kernel_initializer='zeros',bias_initializer='zeros')(h)
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

def build_network(masks, num_bins = 10, blob = 20):
    bijectors = []
    for mask in masks:
        bijectors.append(couplings.PiecewiseRationalQuadratic(mask,build_dense,
                                                              num_bins = num_bins,
                                                              blob = blob))

    bijectors = tfb.Chain(list(reversed(bijectors)))
   
    ndims = len(masks[0])
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

def func(x):
    return tf.py_function(func=func_4cam, inp=[x], Tout=tf.float64)

def func_np(x):
    return func_4cam(x)

def func_rec(x):
    res = np.nan_to_num((x[...,0]**2+x[...,1]**2)/((1-x[...,0])*(1-x[...,1])))
    return np.where((x[...,0]<0.85) & (x[...,1]<0.85), res, 0.)
    
def func_circ(x):
    res = np.nan_to_num((x[...,0]**2+x[...,1]**2)/((1-x[...,0])*(1-x[...,1])))
    return np.where(np.sqrt(x[...,0]**2 +  x[...,1]**2)<0.95, res, 0.)    

location = np.random.rand(8)

def func_4cam(x):
    dx1=dx2=0
    for i in range(4):
        dx1 += (x[...,i] - location[i]) ** 2
        dx2 += (x[...,i] - location[i+4]) ** 2
    scale=50.
    return (np.exp(-scale*dx1)+np.exp(-scale*dx2))

def func_4d(x):
    dx = (x[...,0] - 0.5) ** 2 + (x[...,1] - 0.5) ** 2 + 4.*(x[...,0] - 0.5)*(x[...,1] - 0.5) + (x[...,2] - 0.75) ** 2 + (x[...,3] - 0.5) ** 2
    return np.exp(-4.*dx)

def main(argv):
    del argv

    
    # Configuration settings
    tf.config.experimental_run_functions_eagerly(FLAGS.eager)
    printout = FLAGS.printout
    hist2d_kwargs={'smooth':2}

    ndims = 4

    # Plot matrix element
    if FLAGS.matrix:
        pts = []
        weights = []
        for _ in range(10):
            x = np.random.random((100000,ndims))
            pts.append(x)
            weights.append(func(x))

        pts = np.concatenate(pts)
        weights = np.concatenate(weights)

        figure = corner.corner(pts, weights=weights, labels = [r'$x_{{{}}}$'.format(i) for i in range(ndims)],
                               show_titles=True, title_kwargs={'fontsize': 12},
                               range=ndims*[[0,1]], **hist2d_kwargs)
        plt.savefig('matrix.png')
        plt.close()

    # Create the masks for the bijectors
    masks = []
    masks.append(mask_alternating(ndims))
    masks.append(mask_alternating(ndims, False))
    masks.append(mask_split(ndims))
    masks.append(mask_split(ndims, False))
    masks = np.array(masks)
    print(masks)

    # Build the integrator
    dist = build_network(masks)
    optimizer = tf.keras.optimizers.Adam(FLAGS.lr, clipnorm = 5.0)
    integrate = integrator.Integrator(func, dist, optimizer)
    min_loss = 1e3
    try:
        for epoch in range(FLAGS.epochs):
            if epoch % printout == 0 and FLAGS.plot:
                samples = integrate.sample(10000)
                figure = corner.corner(samples, labels = [r'$x_{{{}}}$'.format(x) for x in range(ndims)],
                                       show_titles=True, title_kwargs={'fontsize': 12},
                                       range=ndims*[[0,1]], **hist2d_kwargs)

            loss, integral, error = integrate.train_one_step(FLAGS.nsamples, integral=True)
            if loss<min_loss:
                min_loss = loss
                integrate.save()
            if epoch % printout == 0:
                print('Epoch: {:4d} Loss = {:8e} Integral = {:8e} +/- {:8e}'
                        .format(epoch, loss, integral, error))
                if FLAGS.plot:
                    figure.suptitle('loss = {:8e}'.format(loss.numpy()), fontsize=16, x=0.75)
                    plt.savefig('fig_{:04d}.png'.format(epoch))
                    plt.close()
                    del figure
                    del samples
    except KeyboardInterrupt:
        if FLAGS.plot:
            plt.close()
    integrate.load()
    #print('Epoch: {:4d} Loss = {:8e} Integral = {:8e} +/- {:8e}'.format(epoch, loss, integral, error))

    n_integral=100000
    final_integral,final_variance = integrate.integrate(n_integral)
    print("Final result: "+str(final_integral.numpy()) +"  +/-  "+str(np.sqrt(final_variance/n_integral)))

    # Plot matrix element
    if FLAGS.matrix:
        pts = []
        weights = []
        for _ in range(10):
            x = integrate.sample(100000)
            pts.append(x)
            
        pts = np.concatenate(pts)

        figure = corner.corner(pts, labels = [r'$x_{{{}}}$'.format(i) for i in range(ndims)],
                               show_titles=True, title_kwargs={'fontsize': 12},
                               range=ndims*[[0,1]], **hist2d_kwargs)
        plt.savefig('matrix-trained.png')
        plt.close()



    
    if FLAGS.acceptance:
        weights = []
        for i in range(10):
            weights.append(integrate.acceptance(10000).numpy()/final_integral)
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
        
        # unweigthed plot:
        x_sam = np.random.rand(100000,ndims)
        wghts = func_np(x_sam)

        average = np.mean(wghts)
        max_wgt = np.max(wghts)

        print('Acceptance w/o optimization = {}'.format(average/max_wgt))

        print(len(wghts) - np.count_nonzero(wghts), np.count_nonzero(wghts))

        wghts = wghts[np.nonzero(wghts)]
        print(len(wghts) - np.count_nonzero(wghts), np.count_nonzero(wghts))

        print(np.min(wghts), np.max(wghts))

        plt.hist(wghts, bins=np.logspace(np.log10(np.min(wghts))-1e-2, 
                                           np.log10(np.max(wghts))+1e-2, 100))
        plt.yscale('log')
        plt.xscale('log')
        plt.savefig('efficiency_untrained.png')
        plt.close()

        
    print("Now performing integral with VEGAS")
    print("Stratified Sampling OFF")
    integ = vegas.Integrator(ndims*[[0, 1]])
    integ(func_np, nitn=20, neval=FLAGS.nsamples,max_nhcube=1)
    result = integ(func_np, nitn=10, neval=n_integral,max_nhcube=1)
    print(result.summary())
    print('result = %s    Q = %.2f' % (result, result.Q))

    print("Stratified Sampling ON")
    integ2 = vegas.Integrator(ndims*[[0, 1]])
    integ2(func_np, nitn=20, neval=FLAGS.nsamples)
    result2 = integ2(func_np, nitn=10, neval=n_integral)
    print(result2.summary())
    print('result = %s    Q = %.2f' % (result2, result2.Q))


        
if __name__ == '__main__':
    app.run(main)