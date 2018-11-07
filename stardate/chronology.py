import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import h5py
import tqdm
from lhf import setup, run_mcmc, make_plots
from isochrones import StarModel
import pandas as pd
import emcee
import corner

from isochrones.mist import MIST_Isochrone
mist = MIST_Isochrone()

plotpar = {'axes.labelsize': 25,
           'font.size': 25,
           'legend.fontsize': 25,
           'xtick.labelsize': 25,
           'ytick.labelsize': 25,
           'text.usetex': True}
plt.rcParams.update(plotpar)


class star(object):

    def __init__(self, iso_params, prot, prot_err, savedir=".", suffix=""):
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
        savedir: str
            (optional) The name of the directory where the samples will be
            saved.
        suffix: str
            (optional) The id or name of the star to use in the filename.
        """

        self.iso_params = iso_params
        self.prot = prot
        self.prot_err = prot_err
        self.savedir = savedir
        self.suffix = suffix

    def fit(self, inits=[1., 9., 0., .5, .01], nwalkers=24, max_n=100000,
            iso_only=False):
        """
        params
        ------
        inits: list
            A list of default initial values to use for mass, age, feh,
            distance and Av, if alternatives are not provided.
        nwalkers: int
            The number of walkers to use with emcee.
        max_n: int
            The maximum number of samples to obtain.
        iso_only: boolean
            If true only the isochronal likelihood function will be used.
        """

        # Set the initial values
        mass_init, age_init, feh_init, distance_init, Av_init = inits
        eep_init = mist.eep_from_mass(mass_init, age_init, feh_init)

        # sample in linear eep, log10(age), linear feh, ln(distance) and
        # linear Av.
        p_init = np.array([eep_init, age_init, feh_init,
                           np.log(distance_init), Av_init])

        np.random.seed(42)

        # Set up the backend
        # Don't forget to clear it in case the file already exists
        filename = "{0}/{1}_samples.h5".format(self.savedir,
                                               str(self.suffix).zfill(4))
        backend = emcee.backends.HDFBackend(filename)
        nwalkers, ndim = 24, 5
        backend.reset(nwalkers, ndim)

        # Set up the StarModel object needed to calculate the likelihood.
        mod = StarModel(mist, **self.iso_params)  # StarModel isochrones obj
        args = [mod, self.prot, self.prot_err, iso_only]  # lnprob arguments

        # Run the MCMC
        sampler = run_mcmc(self.iso_params, args, p_init, backend, ndim=ndim,
                           nwalkers=nwalkers, max_n=max_n)

        self.sampler = sampler
        return sampler


    def age(self, burnin=10000):
        """
        params
        ------
        burnin: int
            The number of samples to cut off at the beginning of the MCMC
            when calculating the posterior percentiles.
        Returns the median age and lower and upper uncertainties.
        Age is log10(Age/yrs).
        """
        samples = self.sampler.flatchain
        asamps = samples[burnin:, 1]
        a = np.median(asamps)
        errp = np.percentile(asamps, 84) - a
        errm = a - np.percentile(asamps, 16)
        return a, errm, errp, asamps


    def eep(self, burnin=10000):
        """
        params
        ------
        burnin: int
            The number of samples to cut off at the beginning of the MCMC
            when calculating the posterior percentiles.
        Returns the median mass and lower and upper uncertainties in units of
        solar mass.
        """
        samples = self.sampler.flatchain
        esamps = samples[burnin:, 0]
        e = np.median(esamps)
        errp = np.percentile(esamps, 84) - e
        errm = e - np.percentile(esamps, 16)
        return e, errm, errp, esamps


    def mass(self, burnin=10000):
        """
        params
        ------
        burnin: int
            The number of samples to cut off at the beginning of the MCMC
            when calculating the posterior percentiles.
        Returns the median mass and lower and upper uncertainties in units of
        solar mass.
        """
        samples = self.sampler.flatchain
        msamps = mist.mass(samples[burnin:, 0], samples[burnin:, 1],
                           samples[burnin:, 2])
        m = np.median(msamps)
        errp = np.percentile(msamps, 84) - m
        errm = m - np.percentile(esamps, 16)
        return m, errm, errp, msamps


    def feh(self, burnin=10000):
        """
        params
        ------
        burnin: int
            The number of samples to cut off at the beginning of the MCMC
            when calculating the posterior percentiles.
        Returns the median metallicity and lower and upper uncertainties.
        """
        samples = self.sampler.flatchain
        fsamps = samples[burnin:, 2]
        f = np.median(fsamps)
        errp = np.percentile(fsamps, 84) - f
        errm = f - np.percentile(fsamps, 16)
        return f, errm, errp, fsamps


    def distance(self, burnin=10000):
        """
        params
        ------
        burnin: int
            The number of samples to cut off at the beginning of the MCMC
            when calculating the posterior percentiles.
        Returns the median distance and lower and upper uncertainties in
        parsecs.
        """
        samples = self.sampler.flatchain
        dsamps = np.exp(samples[burnin:, 3])
        d = np.median(dsamps)
        errp = np.percentile(dsamps, 84) - d
        errm = d - np.percentile(dsamps, 16)
        return d, errm, errp, dsamps


    def Av(self, burnin=10000):
        """
        params
        ------
        burnin: int
            The number of samples to cut off at the beginning of the MCMC
            when calculating the posterior percentiles.
        Returns the median distance and lower and upper uncertainties in
        parsecs.
        """
        samples = self.sampler.flatchain
        avsamps = samples[burnin:, 4]
        a_v = np.median(avsamps)
        errp = np.percentile(avsamps, 84) - a_v
        errm = a_v - np.percentile(avsamps, 16)
        return a_v, errm, errp, avsamps


    def make_plots(self, truths=[None, None, None, None, None], burnin=10000):
        """
        params
        ------
        truths: list
            A list of true values to give to corner.py that will be plotted
            in corner plots. If an entry is "None", no line will be plotted.
            Default = [None, None, None, None, None]
        burnin: int
            The number of burn in samples at the beginning of the MCMC to
            throw away. The default is 100000.
        """

        nwalkers, nsteps, ndim = np.shape(self.sampler.chain)
        print("nsteps = ", nsteps, "burnin = ", burnin)
        assert burnin < nsteps, "The number of burn in samples to throw" \
            "away can't exceed the number of steps."

        samples = self.sampler.flatchain

        print("Plotting age posterior")
        age_gyr = (10**samples[burnin:, 1])*1e-9
        plt.hist(age_gyr)
        plt.xlabel("Age [Gyr]")
        med, std = np.median(age_gyr), np.std(age_gyr)
        if truths[1]:
            plt.axvline(10**(truths[1])*1e-9, color="tab:orange",
                        label="$\mathrm{True~age~[Gyr]}$")
        plt.axvline(med, color="k", label="$\mathrm{Median~age~[Gyr]}$")
        plt.axvline(med - std, color="k", linestyle="--")
        plt.axvline(med + std, color="k", linestyle="--")
        plt.savefig("{0}/{1}_marginal_age".format(self.savedir,
                                                  str(self.suffix).zfill(4)))
        plt.close()

        print("Plotting production chains...")
        plt.figure(figsize=(16, 9))
        for j in range(ndim):
            plt.subplot(ndim, 1, j+1)
            plt.plot(self.sampler.chain[:, burnin:, j].T, "k", alpha=.1)
        plt.savefig("{0}/{1}_chains".format(self.savedir,
                                            str(self.suffix).zfill(4)))
        plt.close()

        print("Making corner plot...")
        labels = ["$\mathrm{EEP}$",
                  "$\log_{10}(\mathrm{Age~[yr]})$",
                  "$\mathrm{[Fe/H]}$",
                  "$\ln(\mathrm{Distance~[Kpc])}$",
                  "$A_v$"]
        corner.corner(samples[burnin:, :], labels=labels, truths=truths);
        plt.savefig("{0}/{1}_corner".format(self.savedir,
                                            str(self.suffix).zfill(4)))
        plt.close()

        # Make mass histogram
        samples = self.sampler.flatchain
        mass_samps = mist.mass(samples[:, 0], samples[:, 1], samples[:, 2])
        plt.hist(mass_samps, 50);
        if truths[0]:
                plt.axvline(truths[0], color="tab:orange",
                            label="$\mathrm{True~mass~}[M_\odot]$")
        plt.savefig("{0}/{1}_marginal_mass".format(self.savedir,
                                                   str(self.suffix).zfill(4)))
        plt.close()