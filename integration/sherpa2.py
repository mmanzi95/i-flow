import numpy as np

from vector import *
from channels import SChannelDecay, Propagator

import logging
logger = logging.getLogger('eejjj')

hbarc2 = 0.3893e9
mt = 173.21
gt = 2
mw = 80.385

class eetojjj:

    def __init__(self,alphas,ecms=91.2):
        self.cutoff = 1e-2
        self.ecms = ecms
        self.prop = Propagator(0.01)
        self.decayIso = SChannelDecay()
        self.decayGluon = SChannelDecay(0.99)
        self.channels = {}
#        self.channels[0] = self.ChannelIso
        self.channels[0] = self.ChannelA1
        self.channels[1] = self.ChannelA2
        self.channels[2] = self.ChannelA3
        self.channels[3] = self.ChannelA4
        self.channels[4] = self.ChannelC1
        self.channels[5] = self.ChannelC2
        self.channels[6] = self.ChannelC3
        self.channels[7] = self.ChannelC4
        self.channels[8] = self.ChannelB1
        self.channels[9] = self.ChannelB2
        self.channels[10] = self.ChannelB3
        self.channels[11] = self.ChannelB4

        self.weights = {}
        self.weights[0] = self.WeightA1
        self.weights[1] = self.WeightA2
        self.weights[2] = self.WeightA3
        self.weights[3] = self.WeightA4
        self.weights[4] = self.WeightC1
        self.weights[5] = self.WeightC2
        self.weights[6] = self.WeightC3
        self.weights[7] = self.WeightC4
        self.weights[8] = self.WeightB1
        self.weights[9] = self.WeightB2
        self.weights[10] = self.WeightB3
        self.weights[11] = self.WeightB4

        self.index = 0

    def PhaseSpace(self,channels,rans,pa,pb):
        logger.debug('channels = {}'.format(channels))
        s1min = self.cutoff
        s1max = np.where(channels < 4, (self.ecms-self.cutoff)**2, self.ecms**2)
        s1 = self.prop.GeneratePoint(s1min,s1max,rans[:,0])

        s2min = self.cutoff
        s2max = np.where(channels < 4, (self.ecms-np.sqrt(s1))**2, s1)
        s2 = self.prop.GeneratePoint(s2min,s2max,rans[:,1])

        q1, q2 = self.decayIso.GeneratePoint(pa+pb, s1,
                np.where(channels < 4, s2, 0),
                np.array([rans[:,2], rans[:,3]]).T)

        q3, q4 = self.decayGluon.GeneratePoint(q1,
                np.where(np.logical_or(channels < 4,channels > 7), 0, s2),
                np.where(channels < 8, 0, s2),
                np.array([rans[:,4], rans[:,5]]).T)

        q5, q6 = self.decayGluon.GeneratePoint(np.where(channels[:,np.newaxis] < 4, q2,
            np.where(channels[:,np.newaxis] < 8, q3, q4)),
            0.0, 0.0, np.array([rans[:,6],rans[:,7]]).T)

        condlist = [channels[:,np.newaxis] < 4, channels[:,np.newaxis] < 8, channels[:,np.newaxis] < 12]

        p1choice = [q3,q5,q3]
        p2choice = [q5,q2,q2]
        p3choice = [q4,q6,q5]
        p4choice = [q6,q4,q6]

        k1 = np.select(condlist, p1choice)
        k2 = np.select(condlist, p2choice)
        k3 = np.select(condlist, p3choice)
        k4 = np.select(condlist, p4choice)

        condlist_perm = [np.mod(channels[:,np.newaxis], 4) == 0, 
                np.mod(channels[:,np.newaxis], 4) == 1,
                np.mod(channels[:,np.newaxis], 4) == 2,
                np.mod(channels[:,np.newaxis], 4) == 3]

        p1perm = [k1,k1,k2,k2]
        p2perm = [k2,k2,k1,k1]
        p3perm = [k3,k4,k3,k4]
        p4perm = [k4,k3,k4,k3]

        p1 = np.select(condlist_perm, p1perm)
        p2 = np.select(condlist_perm, p2perm)
        p3 = np.select(condlist_perm, p3perm)
        p4 = np.select(condlist_perm, p4perm)

        return p1, p2, p3, p4

    def GenerateMomenta(self,channels,rans,pa,pb):
        return self.ChannelA1(rans,pa,pb)

    def ChannelA(self,rans,pa,pb):
        s134 = self.prop.GeneratePoint(self.cutoff,self.ecms**2,rans[:,0])
        s13 = self.prop.GeneratePoint(self.cutoff,s134,rans[:,1])
        p134, p2 = self.decayIso.GeneratePoint(pa+pb,s134,0.0,np.array([rans[:,2], rans[:,3]]).T)
        p13, p4 = self.decayGluon.GeneratePoint(p134,s13,0.0,np.array([rans[:,4], rans[:,5]]).T)
        p1, p3 = self.decayGluon.GeneratePoint(p13,0.0,0.0,np.array([rans[:,6], rans[:,7]]).T)

        return p1, p2, p3, p4

    def ChannelB(self,rans,pa,pb):
        s13 = self.prop.GeneratePoint(self.cutoff,(self.ecms-self.cutoff)**2,rans[:,0])
        s24 = self.prop.GeneratePoint(self.cutoff,(self.ecms-np.sqrt(s13))**2,rans[:,1])
        p13, p24 = self.decayIso.GeneratePoint(pa+pb,s13,s24,np.array([rans[:,2], rans[:,3]]).T)
        p1, p3 = self.decayGluon.GeneratePoint(p13,0.0,0.0,np.array([rans[:,4], rans[:,5]]).T)
        p2, p4 = self.decayGluon.GeneratePoint(p24,0.0,0.0,np.array([rans[:,6], rans[:,7]]).T)

        return p1, p2, p3, p4

    def ChannelC(self,rans,pa,pb):
        s134 = self.prop.GeneratePoint(self.cutoff,self.ecms**2,rans[:,0])
        s34 = self.prop.GeneratePoint(self.cutoff,s134,rans[:,1])
        p134, p2 = self.decayIso.GeneratePoint(pa+pb,s134,0.0,np.array([rans[:,2], rans[:,3]]).T)
        p1, p34 = self.decayGluon.GeneratePoint(p134,0.0,s34,np.array([rans[:,4], rans[:,5]]).T)
        p3, p4 = self.decayGluon.GeneratePoint(p34,0.0,0.0,np.array([rans[:,6], rans[:,7]]).T)

        return p1, p2, p3, p4

    def ChannelA1(self,rans,pa,pb):
        p1, p2, p3, p4 = self.ChannelA(rans,pa,pb)
        return p1, p2, p3, p4

    def ChannelA2(self,rans,pa,pb):
        p1, p2, p4, p3 = self.ChannelA(rans,pa,pb)
        return p1, p2, p3, p4

    def ChannelA3(self,rans,pa,pb):
        p2, p1, p3, p4 = self.ChannelA(rans,pa,pb)
        return p1, p2, p3, p4

    def ChannelA4(self,rans,pa,pb):
        p2, p1, p4, p3 = self.ChannelA(rans,pa,pb)
        return p1, p2, p3, p4

    def ChannelC1(self,rans,pa,pb):
        p1, p2, p3, p4 = self.ChannelC(rans,pa,pb)
        return p1, p2, p3, p4

    def ChannelC2(self,rans,pa,pb):
        p1, p2, p4, p3 = self.ChannelC(rans,pa,pb)
        return p1, p2, p3, p4

    def ChannelC3(self,rans,pa,pb):
        p2, p1, p3, p4 = self.ChannelC(rans,pa,pb)
        return p1, p2, p3, p4

    def ChannelC4(self,rans,pa,pb):
        p2, p1, p4, p3 = self.ChannelC(rans,pa,pb)
        return p1, p2, p3, p4

    def ChannelB1(self,rans,pa,pb):
        p1, p2, p3, p4 = self.ChannelB(rans,pa,pb)
        return p1, p2, p3, p4

    def ChannelB2(self,rans,pa,pb):
        p2, p1, p3, p4 = self.ChannelB(rans,pa,pb)
        return p1, p2, p3, p4

    def ChannelB3(self,rans,pa,pb):
        p1, p2, p4, p3 = self.ChannelB(rans,pa,pb)
        return p1, p2, p3, p4

    def ChannelB4(self,rans,pa,pb):
        p2, p1, p4, p3 = self.ChannelB(rans,pa,pb)
        return p1, p2, p3, p4

    def Weight1(self,pa,pb,p1,p2,p3,p4):
        p13 = p1+p3
        p134 = p13+p4
        ws134 = self.prop.GenerateWeight(self.cutoff,self.ecms**2,p134)
        ws13 = self.prop.GenerateWeight(self.cutoff,Dot(p134,p134),p13)
        wp134_2 = self.decayIso.GenerateWeight(pa+pb,Mass2(p134),0.0,p134,p2)
        wp13_4 = self.decayGluon.GenerateWeight(p13+p4,Mass2(p13),0.0,p13,p4)
        wp1_3 = self.decayGluon.GenerateWeight(p1+p3,0.0,0.0,p1,p3)

        return np.maximum(ws134*ws13*wp134_2*wp13_4*wp1_3,1e-7)

    def Weight2(self,pa,pb,p1,p2,p3,p4):
        p13 = p1+p3
        p24 = p2+p4
        ws13 = self.prop.GenerateWeight(self.cutoff,self.ecms**2,p13)
        ws24 = self.prop.GenerateWeight(self.cutoff,(self.ecms-Mass(p13))**2,p24)
        wp13_24 = self.decayIso.GenerateWeight(pa+pb,Mass2(p13),Mass2(p24),p13,p24)
        wp1_3 = self.decayGluon.GenerateWeight(p1+p3,0.0,0.0,p1,p3)
        wp2_4 = self.decayGluon.GenerateWeight(p2+p4,0.0,0.0,p2,p4)

        return np.maximum(ws24*ws13*wp13_24*wp2_4*wp1_3,1e-7)

    def Weight3(self,pa,pb,p1,p2,p3,p4):
        p34 = p3+p4
        p134 = p34+p1
        ws134 = self.prop.GenerateWeight(self.cutoff,self.ecms**2,p134)
        ws34 = self.prop.GenerateWeight(self.cutoff,Dot(p134,p134),p34)
        wp134_2 = self.decayIso.GenerateWeight(pa+pb,Mass2(p134),0.0,p134,p2)
        wp1_34 = self.decayGluon.GenerateWeight(p34+p1,0.0,Mass2(p34),p1,p34)
        wp3_4 = self.decayGluon.GenerateWeight(p3+p4,0.0,0.0,p3,p4)

        return np.maximum(ws134*ws34*wp134_2*wp1_34*wp3_4,1e-7)

    def WeightA1(self,pa,pb,p1,p2,p3,p4):
        return self.Weight1(pa,pb,p1,p2,p3,p4)

    def WeightA2(self,pa,pb,p1,p2,p3,p4):
        return self.Weight1(pa,pb,p1,p2,p4,p3)

    def WeightA3(self,pa,pb,p1,p2,p3,p4):
        return self.Weight1(pa,pb,p2,p1,p3,p4)

    def WeightA4(self,pa,pb,p1,p2,p3,p4):
        return self.Weight1(pa,pb,p2,p1,p4,p3)

    def WeightB1(self,pa,pb,p1,p2,p3,p4):
        return self.Weight2(pa,pb,p1,p2,p3,p4)

    def WeightB2(self,pa,pb,p1,p2,p3,p4):
        return self.Weight2(pa,pb,p1,p2,p4,p3)

    def WeightB3(self,pa,pb,p1,p2,p3,p4):
        return self.Weight2(pa,pb,p2,p1,p3,p4)

    def WeightB4(self,pa,pb,p1,p2,p3,p4):
        return self.Weight2(pa,pb,p2,p1,p4,p3)

    def WeightC1(self,pa,pb,p1,p2,p3,p4):
        return self.Weight3(pa,pb,p1,p2,p3,p4)

    def WeightC2(self,pa,pb,p1,p2,p3,p4):
        return self.Weight3(pa,pb,p1,p2,p4,p3)

    def WeightC3(self,pa,pb,p1,p2,p3,p4):
        return self.Weight3(pa,pb,p2,p1,p3,p4)

    def WeightC4(self,pa,pb,p1,p2,p3,p4):
        return self.Weight3(pa,pb,p2,p1,p4,p3)

    def ChannelIso(self,rans,pa,pb):
        #        s12 = self.prop.GeneratePoint(1e-1,self.ecms**2,rans[:,2])
        p1, p2 = self.decayIso.GeneratePoint(pa+pb,mt**2,mt**2,np.array([rans[:,0], rans[:,1]]).T)

        return p1, p2

    def WeightIso(self,pa,pb,p1,p2):
        return self.decayIso.GenerateWeight(pa+pb,mt**2,mt**2,p1,p2)

    def GeneratePointIso(self,rans):
        pa = Vector4(self.ecms/2*np.ones(np.shape(rans)[0]),
                np.zeros(np.shape(rans)[0]),
                np.zeros(np.shape(rans)[0]),
                self.ecms/2*np.ones(np.shape(rans)[0]))
        pb = Vector4(self.ecms/2*np.ones(np.shape(rans)[0]),
                np.zeros(np.shape(rans)[0]),
                np.zeros(np.shape(rans)[0]),
                -self.ecms/2*np.ones(np.shape(rans)[0]))

        p1, p2 = self.ChannelIso(rans,pa,pb)

        wsum = self.WeightIso(pa,pb,p1,p2)
        lome = np.array(sherpa.process.CSMatrixElementVec(np.array([pa,pb,p1,p2])))
        dxs = lome*wsum*hbarc2/self.ecms**2/2.0

        return np.nan_to_num(dxs)


    def ChannelTT(self, rans, pa, pb):
        #s13 = self.prop.GeneratePoint(self.cutoff,(self.ecms-self.cutoff)**2,rans[:,0],mass=mt,width=gt)
        #s24 = self.prop.GeneratePoint(self.cutoff,(self.ecms-np.sqrt(s13))**2,rans[:,1],mass=mt,width=gt)
        s13 = self.prop.GeneratePoint((mw+self.cutoff)**2,(self.ecms-mw-self.cutoff)**2,rans[:,0],mass=mt,width=gt)
        s24 = self.prop.GeneratePoint((mw+self.cutoff)**2,(self.ecms-np.sqrt(s13))**2,rans[:,1],mass=mt,width=gt)
        """
        plt.hist(np.sqrt(s13),color='red',bins=np.linspace(0,500,500),label='s13')
        plt.hist(np.sqrt(s24),color='blue',bins=np.linspace(0,500,500),label='s24')
        plt.yscale('log')
        plt.legend()
        plt.savefig('figs/invariant_{:04d}.pdf'.format(self.index))
        plt.close()
        """
        p13, p24 = self.decayIso.GeneratePoint(pa+pb,s13,s24,np.array([rans[:,2], rans[:,3]]).T) 
        p1, p3 = self.decayIso.GeneratePoint(p13,mw**2,0.0,np.array([rans[:,4], rans[:,5]]).T)
        p2, p4 = self.decayIso.GeneratePoint(p24,mw**2,0.0,np.array([rans[:,6], rans[:,7]]).T)


        logger.debug('s13_mean = {}'.format(np.mean(s13)))
        logger.debug('s24_mean = {}'.format(np.mean(s13)))

        return p1, p2, p3, p4

    def WeightTT(self, pa, pb, p1, p2, p3, p4):
        p13 = p1+p3
        p24 = p2+p4
        #ws13 = self.prop.GenerateWeight(self.cutoff,self.ecms**2,p13,mass=mt,width=gt)
        #ws24 = self.prop.GenerateWeight(self.cutoff,(self.ecms-Mass(p13))**2,p24,mass=mt,width=gt)
        ws13 = self.prop.GenerateWeight((mw+self.cutoff)**2,(self.ecms-mw-self.cutoff)**2,p13,mass=mt,width=gt)
        ws24 = self.prop.GenerateWeight((mw+self.cutoff)**2,(self.ecms-Mass(p13))**2,p24,mass=mt,width=gt)
        wp13_24 = self.decayIso.GenerateWeight(pa+pb,Mass2(p13),Mass2(p24),p13,p24)
        wp1_3 = self.decayIso.GenerateWeight(p1+p3,mw**2,0.0,p1,p3)
        wp2_4 = self.decayIso.GenerateWeight(p2+p4,mw**2,0.0,p2,p4)
        logger.debug('p1W = {}, m1W = {}'.format(p1,Mass2(p1)))
        logger.debug('p2W = {}, m2W = {}'.format(p2,Mass2(p2)))
        """
        plt.hist(ws13,color='red',label='ws13',bins=np.logspace(0,7,500))
        plt.hist(ws24,color='blue',label='ws24',bins=np.logspace(0,7,500))
        plt.yscale('log')
        plt.xscale('log')
        plt.legend()
        plt.savefig('figs/prop_weights_{:04d}.pdf'.format(self.index))
        plt.close()

        plt.hist(ws24*ws13*wp13_24*wp2_4*wp1_3,bins=np.logspace(-1,7,500))
        plt.yscale('log')
        plt.xscale('log')
        plt.savefig('figs/weights_{:04d}.pdf'.format(self.index))
        plt.close()
        """
        return np.maximum(ws24*ws13*wp13_24*wp2_4*wp1_3,1e-7)
        

    def GeneratePointTT(self, rans):
        #rans = np.maximum(rans,0.)
        #rans = np.minimum(rans,1.)
        pa = Vector4(self.ecms/2*np.ones(np.shape(rans)[0]),
                np.zeros(np.shape(rans)[0]),
                np.zeros(np.shape(rans)[0]),
                self.ecms/2*np.ones(np.shape(rans)[0]))
        pb = Vector4(self.ecms/2*np.ones(np.shape(rans)[0]),
                np.zeros(np.shape(rans)[0]),
                np.zeros(np.shape(rans)[0]),
                -self.ecms/2*np.ones(np.shape(rans)[0]))

        p1,p2,p3,p4 = self.ChannelTT(rans,pa,pb)
       
        logger.debug('p1 = {}, m1 = {}'.format(p1,Mass2(p1)))
        logger.debug('p2 = {}, m2 = {}'.format(p2,Mass2(p2)))
        logger.debug('p3 = {}, m3 = {}'.format(p3,Mass2(p3)))
        logger.debug('p4 = {}, m4 = {}'.format(p4,Mass2(p4)))

        wsum = self.WeightTT(pa, pb, p1, p2, p3, p4)

        #lome = np.array(sherpa.process.CSMatrixElementVec(np.array([pa,pb,p1,p2,p3,p4])))
        lome = np.array(sherpa.process.CSMatrixElementVec(np.array([pa,pb,p1,p3,p2,p4])))

        logger.debug('wsum = {}'.format(wsum))
        logger.debug('lome = {}'.format(lome))
        logger.debug('ecm = {}'.format(self.ecms))
        dxs = lome*wsum*hbarc2/self.ecms**2/2.0
        """
        plt.hist(lome,bins=np.logspace(-10,5,500))
        plt.yscale('log')
        plt.xscale('log')
        plt.savefig('figs/ME_{:04d}.pdf'.format(self.index))
        plt.close()

        plt.hist(dxs,bins=np.logspace(-6,10,500))
        plt.yscale('log')
        plt.xscale('log')
        plt.savefig('figs/dsig_{:04d}.pdf'.format(self.index))
        plt.close()
        """
        self.index += 1

        #print(np.mean(dxs))

        return np.maximum(np.nan_to_num(dxs),1e-7)

    def GeneratePoint(self,rans,channel):
        pa = Vector4(self.ecms/2*np.ones(np.shape(rans)[0]),
                np.zeros(np.shape(rans)[0]),
                np.zeros(np.shape(rans)[0]),
                self.ecms/2*np.ones(np.shape(rans)[0]))
        pb = Vector4(self.ecms/2*np.ones(np.shape(rans)[0]),
                np.zeros(np.shape(rans)[0]),
                np.zeros(np.shape(rans)[0]),
                -self.ecms/2*np.ones(np.shape(rans)[0]))

        p1, p2, p3, p4 = self.PhaseSpace(channel,rans,pa,pb)
        logger.debug(p1)

#        # Sort find args to sort the channels and count unique values for each channel
#        indices = tf.argsort(channel)
#        unique, counts = np.unique(channel, return_counts = True)
#        counts = np.cumsum(counts)
#        channels = dict(zip(unique,counts))
#
#        # Sort the input rans according to how you would sort the channels
#        logger.debug(channel)
#        logger.debug(indices)
#        logger.debug(rans)
#        rans = tf.gather(rans,indices)
#        logger.debug(rans)
#
##        channels = np.random.randint(0,len(self.channels),(rans.shape[0]))
##        unique, counts = np.unique(channels, return_counts = True)
##        counts = np.cumsum(counts)
##        channels = dict(zip(unique, counts))
##
###        p1, p2 = self.ChannelIso(rans,pa,pb)
#        
#        # Pass the points through the generation
#        p1 = []
#        p2 = []
#        p3 = []
#        p4 = []
#        position_old = 0
#        for channel, position in channels.items():
#            p1tmp, p2tmp, p3tmp, p4tmp = self.GenerateMomenta(
#                                                channel,rans[position_old:position],
#                                                pa[position_old:position],
#                                                pb[position_old:position])
#            p1.append(p1tmp)
#            p2.append(p2tmp)
#            p3.append(p3tmp)
#            p4.append(p4tmp)
#            position_old = position
#
#        p1 = np.concatenate(p1)
#        p2 = np.concatenate(p2)
#        p3 = np.concatenate(p3)
#        p4 = np.concatenate(p4)
#
#        # Sort the momenta back to the original
#        p1 = p1[np.argsort(indices)]
#        p2 = p2[np.argsort(indices)]
#        p3 = p3[np.argsort(indices)]
#        p4 = p4[np.argsort(indices)]

        wsum = np.array([self.Weight1(pa,pb,p1,p2,p3,p4), self.Weight1(pa,pb,p1,p2,p4,p3),
            self.Weight1(pa,pb,p2,p1,p3,p4), self.Weight1(pa,pb,p2,p1,p4,p3),
            self.Weight2(pa,pb,p1,p2,p3,p4), self.Weight2(pa,pb,p1,p2,p4,p3),
            self.Weight2(pa,pb,p2,p1,p3,p4), self.Weight2(pa,pb,p2,p1,p4,p3),
            self.Weight3(pa,pb,p1,p2,p3,p4), self.Weight3(pa,pb,p1,p2,p4,p3),
            self.Weight3(pa,pb,p2,p1,p3,p4), self.Weight3(pa,pb,p2,p1,p4,p3)])


        wsum = np.reciprocal(np.mean(np.reciprocal(wsum),axis=0))

        lome = np.array(sherpa.process.CSMatrixElementVec(np.array([pa,pb,p3,p4,p1,p2])))
        dxs = lome*wsum*hbarc2/self.ecms**2/2.0

        return np.maximum(np.nan_to_num(dxs),1e-7)

if __name__ == '__main__':
    from qcd import AlphaS
    from comix import Comix
    from flow import integrator_tf20 as integrator
    import tensorflow as tf
    import matplotlib.pyplot as plt
    import os
    import argparse

    import corner

    import logging

    parser = argparse.ArgumentParser(
            description='Sherpa Event Generator with Flow integration.'
            )

    parser.add_argument('-d','--debug',action='store_true',
            help='Turn on debug logging')
    parser.add_argument('-e','--epochs',default=500,
            help='Number of epochs to train for')
    parser.add_argument('-p','--plot',action='store_true',
            help='Flag for plotting distributions')
    parser.add_argument('-l','--loss',action='store_true',
            help='Flag for plotting loss, integral, and variance')
    parser.add_argument('-n','--nsamples',default=2000,
            help='Number of samples to calculate the loss')
    parser.add_argument('-a','--acceptance',action='store_true',
            help='Calculate acceptance')

    options = parser.parse_args()
    acceptance = options.acceptance
    plot = options.plot

    logging.basicConfig()
    if options.debug:
        logging.getLogger('eejjj').setLevel(logging.DEBUG)
#        logging.getLogger('channels').setLevel(logging.DEBUG)

    alphas = AlphaS(91.1876,0.118)
    hardxs = eetojjj(alphas,500)
    in_part = [11,-11]
#    out_part = [1,-1,21,21]
    out_part = [5,-5,24,-24]
#    out_part = [1,-1]
    npart = len(out_part)
    ndims = 3*npart - 4
    sherpa = Comix(in_part,out_part)

#    x = np.random.random((100000,ndims))
#    p = hardxs.GeneratePointIso(x)
#
#    figure = corner.corner(x, labels=[r'$x_{}$'.format(i) for i in range(ndims)], weights=p, show_titles=True, title_kwargs={"fontsize": 12})
#    plt.savefig('matrix.pdf')

#    def func2(x):
#        return tf.stop_gradient(tf.py_function(hardxs.GeneratePointIso,[x],tf.float32))
#
#    integrator = integrator.Integrator(func2, ndims, mode='quadratic')
#    integrator.make_optimizer(nsamples=1000, learning_rate=1e-3)
#
#    with tf.Session(config=tf.ConfigProto(device_count={'GPU':0})) as sess:
#        try:
#            integrator.load(sess,"models/eejj.ckpt")
#        except: 
#            sess.run(tf.global_variables_initializer())
##            profiler = tf.profiler.Profiler(sess.graph)
##            options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
#            profiler = None
#            options = None
#            integrator.optimize(sess,epochs=400,printout=10,profiler=profiler,options=options)
#            integrator.save(sess,"models/eejj.ckpt")
#
#            if profiler is not None:
#                option_builder = tf.profiler.ProfileOptionBuilder
#                opts = (option_builder(option_builder.time_and_memory()).
#                        with_step(-1). # with -1, should compute the average of all registered steps.
#                        with_file_output('test.txt').
#                        select(['micros','bytes','occurrence']).order_by('micros').
#                        build())
#                # Profiling infos about ops are saved in 'test-%s.txt' % FLAGS.out
#                profiler.profile_operations(options=opts)
#        print(integrator.integrate(sess,100000,acceptance=True))
#
#    fig, (ax1, ax2, ax3) = plt.subplots(1,3,figsize=(16,5))
#    ax1 = integrator.plot_loss(ax1)
#    ax2 = integrator.plot_integral(ax2)
#    ax3 = integrator.plot_variance(ax3)
#    plt.savefig('loss.pdf') 
#    plt.close()
#
#    raise


    def func(x):
        return tf.stop_gradient(tf.py_function(hardxs.GeneratePointTT,[x],tf.float32))
    #nevents = 250000
    #hist2d_kwargs={'smooth':2}
    #x = np.random.random((nevents,ndims))
    #p = hardxs.GeneratePointTT(x)

    #figure = corner.corner(x, labels=[r'$x_{}$'.format(i) for i in range(ndims)], weights=p, show_titles=True, title_kwargs={"fontsize": 12},**hist2d_kwargs)
    #plt.savefig('matrix.pdf')
    #plt.close()
    
    #print("done plotting")
    """
    import vegas

    def generate_vegas(x):
        return hardxs.GeneratePointTT(np.array([x]))
    
    integ = vegas.Integrator(ndims*[[0.,1.]])
    integ(generate_vegas, nitn=5, neval=1000)#,max_nhcube=1)
    print("Vegas training done")
    result = integ(generate_vegas, nitn=1, neval=20000)#,max_nhcube=1)
    print(result.summary())
    print('result = %s    Q = %.2f' % (result, result.Q))

    raise
    # vegas sample for corner
    # vegas sample for acceptance
    # check vegas wgt with our estimate 1/q
    """
    nint = 250000

    integrator = integrator.Integrator(func, ndims, nbins=24, nchannels=1, mode='quadratic',name='eejjjj', hot=True, unet=False, learning_rate=5e-4)

# print / plot untrained:    
#    print(integrator.integrate(nint,
#          acceptance=acceptance,
#          fname='untrained',
#          plot=True,
#          min=1e-9,
#          max=1e3,
#          nbins=300))

    nsamples = [100]
#    nsamples.extend([8192]*50)
#    nsamples.extend([16384]*50)
    nsamples.extend([1000]*100)
    nsamples.extend([2000]*50) 
#    nsamples.extend([4000]*20)
#    nsamples.extend([8000]*10) 
#    nsamples.extend([16000]*10)
    integrator.optimize(nsamples=nsamples,printout=10,plot=plot)
#    integrator.load(sess)
    print(integrator.integrate(nint,
          acceptance=acceptance,
          fname='trained',
          plot=True,
          min=1e-9,
          max=1e3,
          nbins=300
         ))

    fig, (ax1, ax2, ax3) = plt.subplots(1,3,figsize=(16,5))
    ax1 = integrator.plot_loss(ax1)
    ax2 = integrator.plot_integral(ax2)
    ax3 = integrator.plot_variance(ax3)
    plt.savefig('loss.pdf') 