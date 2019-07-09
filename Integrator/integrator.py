import numpy as np
import piecewise
import tensorflow_probability as tfp
tfd = tfp.distributions
tfb = tfp.bijectors
import matplotlib.pyplot as plt
import tensorflow as tf
import corner

def ewma(data,window):
    """
    Function to caluclate the Exponentially weighted moving average.

    Parameters
    ----------
    data : np.ndarray, float64
        A single dimensional numpy array
    window : int64
        The decay window

    Returns
    -------
    int64
        The EWMA for the last point in the data array
    """

    if len(data) < window:
        return data[-1]

    weights = np.exp(np.linspace(-1.,0.,window))
    weights /= weights.sum()
    a = np.convolve(data, weights, mode='full')[:len(data)]
    a[:window] = a[window]
    return a[-1]

class BijectorFactory:
    def __init__(self):
        self._bijectors = {}

    def register_bijector(self, key, bijector):
        self._bijectors[key] = bijector

    def create(self, key, **kwargs):
        bijector = self._bijectors.get(key)
        if not bijector:
            raise ValueError(key)
        return bijector(**kwargs)

factory = BijectorFactory()
factory.register_bijector('linear', piecewise.PiecewiseLinear)
#factory.register_bijector('quadratic', piecewise.PiecewiseQuadratic)
#factory.register_bijector('quadratic_const', piecewise.PiecewiseQuadraticConst)

class Integrator():
    def __init__(self, func, ndims, layers=4, mode='quadratic', nbins=25, **kwargs):
        self.func = func
        self.ndims = ndims
        self.mode = mode
        self.nbins = nbins
        self.layers = layers

        self.losses = []
        self.integrals = []
        self.vars = []
        self.global_step = 0

        self.bijectors = []

        self.labels = [r'$x_{}$'.format(i) for i in range(self.ndims)]

        arange = np.arange(ndims)
        permute = np.hstack([arange[1:],arange[0]])
        kwargs['D'] = ndims
        kwargs['d'] = ndims//2
        kwargs['nbins'] = nbins
        for i in range(ndims):
            kwargs['layer_id'] = i
            self.bijectors.append(factory.create(mode,**kwargs))
            self.bijectors.append(tfb.Permute(permutation=permute))

        self.bijectors = tfb.Chain(list(reversed(self.bijectors))) 

        self.base_dist = tfd.Uniform(low=ndims*[0.],high=ndims*[1.])
        self.base_dist = tfd.Independent(distribution=self.base_dist,
                reinterpreted_batch_ndims=1,
                )

        self.dist = tfd.TransformedDistribution(
                distribution=self.base_dist,
                bijector=self.bijectors,
                )

        self.saver = tf.train.Saver()

    def _loss_fn(self,nsamples):
        x = self.dist.sample(nsamples)
        logq = self.dist.log_prob(x)
        p = self.func(x)
        q = self.dist.prob(x)
        xsec = p/q
        p = p/tf.reduce_mean(xsec)
        mean, var = tf.nn.moments(xsec,axes=[0])
        return tf.reduce_mean(p/q*(tf.log(p)-logq)), mean, var/nsamples, x, p, q

    def make_optimizer(self,learning_rate=1e-4,nsamples=500):
        self.loss, self.integral, self.var, self.x, self.p, self.q = self._loss_fn(nsamples) 
        optimizer = tf.train.AdamOptimizer(learning_rate)
        grads = optimizer.compute_gradients(self.loss)
        self.opt_op = optimizer.apply_gradients(grads)

    def optimize(self,sess,**kwargs):
        # Break out the possible keyword arguments
        if 'epochs' in kwargs:
            epochs = kwargs['epochs']
        else:
            epochs =  1000

        if 'learning_rate' in kwargs:
            learning_rate = kwargs['learning_rate']
        else:
            learning_rate=1e-4

        if 'nsamples' in kwargs:
            nsamples = kwargs['nsamples']
        else:
            nsamples = 500

        if 'printout' in kwargs:
            printout = kwargs['printout']
        else:
            printout = 100

        if 'profiler' in kwargs:
            profiler = kwargs['profiler']
            if 'options' in kwargs:
                options = kwargs['options']
            else:
                options = None
        else:
            profiler = None
            options = None

        # Preform training
        for epoch in range(epochs):
            if profiler is not None:
                run_metadata = tf.RunMetadata()
            else:
                run_metadata = None
            _, np_loss, np_integral, np_var, xpts, ppts, qpts = sess.run([self.opt_op, self.loss, self.integral, self.var, self.x, self.p, self.q],options=options,run_metadata=run_metadata)
            if profiler is not None:
                profiler.add_step(epoch, run_metadata)
            self.global_step += 1
            self.losses.append(np_loss)
            self.integrals.append(np_integral)
            self.vars.append(np_var)
            if epoch % printout == 0:
                print("Epoch %4d: loss = %e, integral = %e +/- %e"   
                        %(epoch, np_loss, ewma(self.integrals,10), np.sqrt(ewma(self.vars,10)))) 
                if 'plot' in kwargs:
                    figure = corner.corner(xpts, labels=self.labels, show_titles=True, title_kwargs={"fontsize": 12}, range=self.ndims*[[0,1]])
                    plt.savefig('fig_{:04d}.pdf'.format(epoch))
                    plt.close()
#            if np.sqrt(np_var)/np_integral < stopping:
#                break

        print("Epoch %4d: loss = %e, integral = %e +/- %e"   
                %(epoch, np_loss, ewma(self.integrals,10), np.sqrt(ewma(self.vars,10)))) 
        if 'plot' in kwargs:
            figure = corner.corner(xpts, labels=self.labels, show_titles=True, title_kwargs={"fontsize": 12}, range=self.ndims*[[0,1]])
            plt.savefig('fig_{:04d}.pdf'.format(epoch))
            plt.close()

    def save(self,sess,name):
        save_path = self.saver.save(sess, name)
        print("Model saved at: {}".format(save_path))

    def load(self,sess,name):
        self.saver.restore(sess, name)
        print("Model resotred")

    def _plot(self,axis,labelsize=17,titlesize=20):
        axis.set_xlabel('epoch',fontsize=titlesize)
        axis.tick_params(axis='both',reset=True,which='both',direction='in',size=labelsize)
        return axis
    
    def plot_loss(self,axis,labelsize=17,titlesize=20,start=0):
        axis.plot(self.losses[start:])
        axis.set_ylabel('loss',fontsize=titlesize)
        axis.set_yscale('log')
        axis = self._plot(axis,labelsize,titlesize)
        return axis

    def plot_integral(self,axis,labelsize=17,titlesize=20,start=0):
        axis.plot(self.integrals[start:])
        axis.set_ylabel('integral',fontsize=titlesize)
        axis = self._plot(axis,labelsize,titlesize)
        return axis

    def plot_variance(self,axis,labelsize=17,titlesize=20,start=0):
        axis.plot(self.vars[start:])
        axis.set_ylabel('variance',fontsize=titlesize)
        axis.set_yscale('log')
        axis = self._plot(axis,labelsize,titlesize)
        return axis

    def integrate(self,sess,nsamples=10000,plot=False,acceptance=False):
        x = self.dist.sample(nsamples)
        q = self.dist.prob(x)
        p = self.func(x)
        integral, var = tf.nn.moments(p/q,axes=[0])
        error = tf.sqrt(var/nsamples)

        tf_results = [integral,error]
        if plot:
            tf_results.append(x)
        if acceptance:
            r = p/q
            tf_results.append(r)

        results = sess.run(tf_results)
        if plot:
            figure = corner.corner(results[2], labels=self.labels, show_titles=True, title_kwargs={"fontsize": 12}, range=self.ndims*[[0,1]])
            plt.savefig('xsec_final.pdf')
            plt.close()

        if acceptance:
            plt.hist(results[-1],bins=np.logspace(np.log10(np.min(results[-1])),
                                                  np.log10(np.max(results[-1])),
                                                  50)) 
            plt.yscale('log')
            plt.xscale('log')
            plt.savefig('acceptance.pdf')
            plt.close()
            return results[0], results[1], np.mean(results[-1])/np.max(results[-1])


        return results[0], results[1]

if __name__ == '__main__':
    import tensorflow as tf
    def normalChristina(x):
        return 0.8* tf.exp((-0.5*((x[:,0]-0.5)* (50 *(x[:,0]-0.5) -  15* (x[:,1]-0.5)) + (-15*(x[:,0]-0.5) + 5*(x[:,1]-0.5))* (x[:,1]-0.5)))) + x[:,2]

    integrator = Integrator(normalChristina, 3, mode='linear',unet=True,hot=True)
    integrator.make_optimizer(nsamples=1000)
    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        integrator.optimize(sess,epochs=1000)
        print(integrator.integrate(sess,100000,acceptance=True))

    fig, (ax1, ax2, ax3) = plt.subplots(1,3,figsize=(16,5))
    ax1 = integrator.plot_loss(ax1)
    ax2 = integrator.plot_integral(ax2)
    ax3 = integrator.plot_variance(ax3)
    plt.show() 

