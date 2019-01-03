import os
import numpy as np
import pandas as pd
import h5py
import tqdm
from stardate.lhf import run_mcmc
from isochrones import StarModel
import pandas as pd
import emcee

from isochrones.mist import MIST_Isochrone
mist = MIST_Isochrone()


class star(object):

    def __init__(self, iso_params, prot, prot_err, savedir=".",
                 filename="samples", bv=None, mass=None):
        """
        params
        -------
        iso_params: dictionary
            A dictionary containing all available photometric and
            spectroscopic parameters for a star, as well as its parallax.
            All parameters should also have associated uncertainties.
            This dictionary should be similar to the standard one created for
            isochrones.py.
        prot: float
            The rotation period of the star in days.
        prot_err: float
            The uncertainty on the stellar rotation period in days.
        savedir: str (optional)
            The name of the directory where the samples will be
            saved. Default is the current working directory.
        filename: str (optional)
            The name of the h5 file which the posterior samples
            will be saved in.
        bv: float (optional)
            B-V color. In order to infer an age with only gyrochronology, a
            B-V color must be provided.
        mass: float (optional)
            In order to infer an age with only gyrochronology, a mass
            must be provided (units of Solar masses).
        """

        self.iso_params = iso_params
        self.prot = prot
        self.prot_err = prot_err
        self.savedir = savedir
        self.filename = filename
        self.bv = bv
        self.mass = mass

    def fit(self, inits=[355, np.log10(4.56*1e9), 0., 1000., .01],
            nwalkers=24, max_n=100000, thin_by=100, burnin=0,
            iso_only=False, gyro_only=False):
        """
        params
        ------
        inits: (list, optional)
            A list of initial values to use for eep, age (in
            log10[yrs]), feh, distance (in pc) and Av. The defaults are Solar
            values at 1000 pc with a small extinction.
        nwalkers: (int, optional)
            The number of walkers to use with emcee. The default is 24.
        max_n: (int, optional)
            The maximum number of samples to obtain, the default in 100000.
        thin_by: (int, optional)
            Only one in every thin_by samples will be saved. The default is
            100. Set = 1 to save every sample (note -- this substantially
            slows down the IO.
        burnin: (int, optional)
            Default = 0.
            The number of SAVED samples to throw away when accessing the
            results. This number cannot exceed the number of saved samples
            (which is max_n/thin_by).
        iso_only: (boolean, optional)
            If true only the isochronal likelihood function will be used.
        gyro_only: (boolean, optional)
            If true only the gyrochronal likelihood function will be used.
            Cannot be true if iso_only is true.
        """
        if iso_only:
            assert gyro_only == False, "You cannot set both iso_only and "\
                "gyro_only to be True."

        if gyro_only:
            assert mass, "If gyro_only is set to True, you must " \
                "provide a B-V colour and a mass."

        if burnin > max_n/thin_by:
            burnin = int(max_n/thin_by/3)
            print("Automatically setting burn in to {}".format(burnin))

        p_init = [inits[0], inits[1], inits[2], np.log(inits[3]), inits[4]]

        np.random.seed(42)

        # Create the directory if it doesn't already exist.
        if not os.path.exists(self.savedir):
            os.makedirs(self.savedir)

        # Set up the backend
        # Don't forget to clear it in case the file already exists
        filename = "{0}/{1}_samples.h5".format(self.savedir, self.filename)
        backend = emcee.backends.HDFBackend(filename)
        nwalkers, ndim = 24, 5
        backend.reset(nwalkers, ndim)

        # Set up the StarModel object needed to calculate the likelihood.
        mod = StarModel(mist, **self.iso_params)  # StarModel isochrones obj

        # lnprob arguments
        args = [mod, self.prot, self.prot_err, self.bv, self.mass, iso_only,
                gyro_only]

        # Run the MCMC
        sampler = run_mcmc(self.iso_params, args, p_init, backend, ndim=ndim,
                           nwalkers=nwalkers, max_n=max_n, thin_by=thin_by)

        self.sampler = sampler
        nwalkers, nsteps, ndim = np.shape(sampler.chain)
        self.samples = np.reshape(sampler.chain[:, burnin:, :],
                                  (nwalkers*(nsteps-burnin), ndim))

    def age_results(self, burnin=0):
        """
        Returns the median age, the upper age uncertainty, the lower age
        uncertainty and the age samples.
        Age is log10(Age/yrs).
        params
        ------
        burnin: (int, optional)
            The number of samples to throw away. Default is 0.
        """
        nwalkers, nsteps, ndim = np.shape(self.sampler.chain)
        assert nsteps > burnin, "The number of burn in samples to throw "\
            "away ({0}) cannot exceed the number of steps that were saved "\
            "({1}). Try setting the burnin keyword argument.".format(burnin,
                                                                     nsteps)
        samples = self.sampler.chain[:, burnin:, 1]
        samps = np.reshape(samples, (nwalkers*(nsteps - burnin)))
        a = np.median(samps)
        errp = np.percentile(samps, 84) - a
        errm = a - np.percentile(samps, 16)
        return a, errm, errp, samps


    def eep_results(self, burnin=0):
        """
        params
        ------
        burnin: (int, optional)
            The number of samples to throw away. Default is 0.
        Returns the median EEP and lower and upper uncertainties.
        """
        nwalkers, nsteps, ndim = np.shape(self.sampler.chain)
        assert nsteps > burnin, "The number of burn in samples to throw "\
            "away ({0}) cannot exceed the number of steps that were saved "\
            "({1}). Try setting the burnin keyword argument.".format(burnin,
                                                                     nsteps)
        samples = self.sampler.chain[:, burnin:, 0]
        samps = np.reshape(samples, (nwalkers*(nsteps - burnin)))
        e = np.median(samps)
        errp = np.percentile(samps, 84) - e
        errm = e - np.percentile(samps, 16)
        return e, errm, errp, samps


    def mass_results(self, burnin=100):
        """
        params
        ------
        burnin: (int, optional)
            The number of samples to throw away. Default is 0.
        Returns the median mass and lower and upper uncertainties in units of
        solar mass.
        """
        nwalkers, nsteps, ndim = np.shape(self.sampler.chain)
        assert nsteps > burnin, "The number of burn in samples to throw "\
            "away ({0}) cannot exceed the number of steps that were saved "\
            "({1}). Try setting the burnin keyword argument.".format(burnin,
                                                                     nsteps)
        samples = self.sampler.chain[:, burnin:, :]
        nwalkers, nsteps, ndim = np.shape(samples)
        samps = np.reshape(samples, (nwalkers*nsteps, ndim))
        msamps = mist.mass(samps[:, 0], samps[:, 1], samps[:, 2])
        m = np.median(msamps)
        errp = np.percentile(msamps, 84) - m
        errm = m - np.percentile(msamps, 16)
        return m, errm, errp, msamps


    def feh_results(self, burnin=0):
        """
        params
        ------
        burnin: (int, optional)
            The number of samples to throw away. Default is 0.
        Returns the median metallicity and lower and upper uncertainties.
        """
        nwalkers, nsteps, ndim = np.shape(self.sampler.chain)
        assert nsteps > burnin, "The number of burn in samples to throw "\
            "away ({0}) cannot exceed the number of steps that were saved "\
            "({1}). Try setting the burnin keyword argument.".format(burnin,
                                                                     nsteps)
        samples = self.sampler.chain[:, burnin:, 2]
        samps = np.reshape(samples, (nwalkers*(nsteps - burnin)))
        f = np.median(samps)
        errp = np.percentile(samps, 84) - f
        errm = f - np.percentile(samps, 16)
        return f, errm, errp, samps


    def distance_results(self, burnin=0):
        """
        params
        ------
        burnin: (int, optional)
            The number of samples to throw away. Default is 0.
        Returns the median distance and lower and upper uncertainties in
        parsecs.
        """
        nwalkers, nsteps, ndim = np.shape(self.sampler.chain)
        assert nsteps > burnin, "The number of burn in samples to throw "\
            "away ({0}) cannot exceed the number of steps that were saved "\
            "({1}). Try setting the burnin keyword argument.".format(burnin,
                                                                     nsteps)
        samples = self.sampler.chain[:, burnin:, 3]
        samps = np.reshape(samples, (nwalkers*(nsteps - burnin)))
        d = np.median(samps)
        errp = np.percentile(samps, 84) - d
        errm = d - np.percentile(samps, 16)
        return d, errm, errp, samps


    def Av_results(self, burnin=100):
        """
        params
        ------
        burnin: (int, optional)
            The number of samples to throw away. Default is 0.
        Returns the median distance and lower and upper uncertainties in
        parsecs.
        """
        nwalkers, nsteps, ndim = np.shape(self.sampler.chain)
        assert nsteps > burnin, "The number of burn in samples to throw "\
            "away ({0}) cannot exceed the number of steps that were saved "\
            "({1}). Try setting the burnin keyword argument.".format(burnin,
                                                                     nsteps)
        samples = self.sampler.chain[:, burnin:, 4]
        samps = np.reshape(samples, (nwalkers*(nsteps - burnin)))
        a_v = np.median(samps)
        errp = np.percentile(samps, 84) - a_v
        errm = a_v - np.percentile(samps, 16)
        return a_v, errm, errp, samps
