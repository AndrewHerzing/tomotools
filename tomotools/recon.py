# -*- coding: utf-8 -*-
#
# This file is part of TomoTools

"""
Reconstruction module for TomoTools package.

@author: Andrew Herzing
"""
import tomopy
import numpy as np
import astra
import hyperspy.api as hs
import logging
from contextlib import contextmanager
import sys
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@contextmanager
def suppress_stdout():
    """Suppress text output from tomopy reconstruction algorithm."""
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout


def run(stack, method, rot_center=None, iterations=None, constrain=None,
        thresh=None, cuda=True, **kwargs):
    """
    Perform reconstruction of input tilt series.

    Args
    ----------
    stack :TomoStack object
       TomoStack containing the input tilt series
    method : string
        Reconstruction algorithm to use.  Must be either 'FBP' (default) or
        'SIRT'
    rot_center : float
        Location of the rotation center.  If None, position is assumed to be
        the center of the image.
    iterations : integer (only required for SIRT)
        Number of iterations for the SIRT reconstruction (for SIRT methods
        only)
    constrain : boolean
        If True, output reconstruction is constrained above value given by
        'thresh'
    thresh : integer or float
        Value above which to constrain the reconstructed data
    cuda : boolean
        If True, use the CUDA-accelerated Astra algorithms. Otherwise,
        use the CPU-based algorithms
    **kwargs : dict
        Any other keyword arguments are passed through to ``tomopy.recon``

    Returns
    ----------
    rec : Numpy array
        Containing the reconstructed volume

    """
    if stack.metadata.Tomography.tilts is None:
        raise ValueError("Tilts not defined")

    theta = stack.metadata.Tomography.tilts * np.pi / 180
    if method == 'FBP':
        if not astra.astra.use_cuda() or not cuda:
            '''ASTRA weighted-backprojection reconstruction of single slice'''
            options = {'proj_type': 'linear', 'method': 'FBP'}
            logger.info('Reconstruction volume using FBP')
            with suppress_stdout():
                rec = tomopy.recon(stack.data, theta, center=rot_center,
                                   algorithm=tomopy.astra,
                                   filter_name='ramlak',
                                   options=options, **kwargs)
            logger.info('Reconstruction complete')
        elif astra.astra.use_cuda() or cuda:
            '''ASTRA weighted-backprojection CUDA reconstruction of single
            slice'''
            logger.info('Reconstruction volume using FBP_CUDA')
            options = {'proj_type': 'cuda', 'method': 'FBP_CUDA'}
            with suppress_stdout():
                rec = tomopy.recon(stack.data, theta, center=rot_center,
                                   algorithm=tomopy.astra,
                                   filter_name='ramlak',
                                   options=options, **kwargs)
            logger.info('Reconstruction complete')
        else:
            raise Exception('Error related to ASTRA Toolbox')
    elif method == 'SIRT':
        if not iterations:
            iterations = 20
        if not astra.astra.use_cuda() or not cuda:
            '''ASTRA SIRT reconstruction of single slice'''
            if constrain:
                if not thresh:
                    thresh = 0
                logger.info("Reconstructing volume using SIRT w/ "
                            "minimum constraint. Minimum value: %s" % thresh)
                extra_options = {'MinConstraint': thresh}
                options = {'proj_type': 'linear', 'method': 'SIRT',
                           'num_iter': iterations,
                           'extra_options': extra_options}
            else:
                logger.info("Reconstructing volume using SIRT")
                options = {'proj_type': 'linear', 'method': 'SIRT',
                           'num_iter': iterations}
            with suppress_stdout():
                rec = tomopy.recon(stack.data, theta, center=rot_center,
                                   algorithm=tomopy.astra, options=options,
                                   **kwargs)
            logger.info('Reconstruction complete')
        elif astra.astra.use_cuda() or cuda:
            '''ASTRA CUDA-accelerated SIRT reconstruction'''
            if constrain:
                if not thresh:
                    thresh = 0
                logger.info("Reconstructing volume using SIRT_CUDA w/ "
                            "minimum constraint. Minimum value: %s" % thresh)
                extra_options = {'MinConstraint': thresh}
                options = {'proj_type': 'cuda', 'method': 'SIRT_CUDA',
                           'num_iter': iterations,
                           'extra_options': extra_options}
            else:
                logger.info("Reconstructing volume using SIRT_CUDA")
                options = {'proj_type': 'cuda', 'method': 'SIRT_CUDA',
                           'num_iter': iterations}
            with suppress_stdout():
                rec = tomopy.recon(stack.data, theta, center=rot_center,
                                   algorithm=tomopy.astra, options=options,
                                   ncore=1, **kwargs)
            logger.info('Reconstruction complete')
        else:
            raise Exception('Error related to ASTRA Toolbox')
    else:
        raise ValueError('Unknown reconstruction algorithm:' + method)
    return rec


def check_sirt_error(sinogram, algorithm, tol, constrain, cuda):
    """
    Determine the optimum number of SIRT iterations.

    Evaluates the difference between SIRT reconstruction and input data
    at each iteration and terminates when the change between iterations is
    below tolerance.

    Args
    ----------
    sinogram : Hyperspy Signal2D
        Single slice from a tomogram for reconstruction evaluation.
    tol : float
        Fractional change between iterations at which the
        evaluation will terminate.
    constrain : boolean
        If True, perform SIRT reconstruction with a non-negativity
        constraint.
    cuda : boolean
        If True, perform reconstruction using the GPU-accelrated algorithm.

    Returns
    ----------
    error : Numpy array
        Sum of squared difference between the forward-projected reconstruction
        and the input sinogram at each iteration

    rec_stack : Hyperspy Signal2D
        Signal containing the SIRT reconstruction at each iteration
        for visual inspection.

    """
    if sinogram.metadata.Tomography.tilts is None:
        raise ValueError("Tilts not defined")

    tilts = sinogram.metadata.Tomography.tilts * np.pi / 180

    error = []
    terminate = False
    rec = None
    iteration = 0
    while not terminate:
        with suppress_stdout():
            rec = tomopy.recon(sinogram.data, theta=tilts, algorithm=algorithm,
                               num_iter=1, init_recon=rec)
        if iteration == 0:
            rec_stack = rec
        else:
            rec_stack = np.vstack((rec_stack, rec))
        with suppress_stdout():
            forward_project = tomopy.project(rec, theta=tilts, pad=False)

        error.append(np.sum((sinogram.data - forward_project)**2))
        if len(error) > 1:
            change = np.abs((error[-2] - error[-1]) / error[-2])
            logger.info("Change after iteration %s: %.1f %%" %
                        (iteration, 100 * change))
            if change < tol:
                terminate = True
                logger.info('Change in error below tolerance after %s '
                            'iterations' % iteration)
        iteration += 1
    error = np.array(error)
    rec_stack = hs.signals.Signal2D(rec_stack)
    return error, rec_stack


def astra_sirt(stack, angles, thickness=None, iterations=50,
               constrain=True, thresh=0, cuda=False):
    """
    Perform SIRT reconstruction using the Astra toolbox algorithms.

    Args
    ----------
    stack : NumPy array
       Tilt series data either of the form [angles, x] or [angles, y, x] where
       y is the tilt axis and x is the projection axis.
    angles : list or NumPy array
        Projection angles in degrees.
    thickness : int or float
        Number of pixels in the projection (through-thickness) direction
        for the reconstructed volume.  If None, thickness is set to be the
        same as that in the x-direction of the sinogram.
    iterations : integer
        Number of iterations for the SIRT reconstruction.
    constrain : boolean
        If True, output reconstruction is constrained above value given by
        'thresh'. Default is True.
    thresh : integer or float
        Value above which to constrain the reconstructed data if 'constrain'
        is True.
    cuda : boolean
        If True, use the CUDA-accelerated Astra algorithms. Otherwise,
        use the CPU-based algorithms
    Returns
    ----------
    rec : Numpy array
        3D array of the form [y, z, x] containing the reconstructed object.

    """

    thetas = angles * np.pi / 180

    if len(stack.shape) == 2:
        data = np.expand_dims(stack, 1)
    else:
        data = stack
    data = np.rollaxis(data, 1)
    y_pix, n_angles, x_pix = data.shape

    if thickness is None:
        thickness = data.shape[2]

    if cuda:
        rec = np.zeros([y_pix, thickness, x_pix], data.dtype)
        nchunks = y_pix/128

        if nchunks < 1:
            nchunks = 1
            chunksize = y_pix
        else:
            chunksize = 128

        for i in range(0, np.int32(nchunks)):
            chunk = data[i*chunksize:(i+1)*chunksize, :, :]
            vol_geom = astra.create_vol_geom(thickness, x_pix, chunksize)
            proj_geom = astra.create_proj_geom('parallel3d', 1, 1,
                                               chunksize, x_pix, thetas)
            data_id = astra.data3d.create('-proj3d', proj_geom, chunk)
            rec_id = astra.data3d.create('-vol', vol_geom)

            cfg = astra.astra_dict('SIRT3D_CUDA')
            cfg['ReconstructionDataId'] = rec_id
            cfg['ProjectionDataId'] = data_id
            if constrain:
                cfg['option'] = {}
                cfg['option']['MinConstraint'] = thresh

            alg_id = astra.algorithm.create(cfg)

            astra.algorithm.run(alg_id, iterations)

            rec[i*chunksize:(i+1)*chunksize, :, :] = astra.data3d.get(rec_id)
            astra.algorithm.delete(alg_id)
            astra.data3d.delete(rec_id)
            astra.data3d.delete(data_id)

    else:
        rec = np.zeros([y_pix, thickness, x_pix], data.dtype)
        vol_geom = astra.create_vol_geom(thickness, x_pix)
        proj_geom = astra.create_proj_geom('parallel', 1.0,
                                           x_pix, thetas)
        proj_id = astra.create_projector('strip', proj_geom, vol_geom)
        rec_id = astra.data2d.create('-vol', vol_geom)
        sinogram_id = astra.data2d.create('-sino', proj_geom, data[0, :, :])
        cfg = astra.astra_dict('SIRT')
        cfg['ReconstructionDataId'] = rec_id
        cfg['ProjectionDataId'] = sinogram_id
        cfg['ProjectorId'] = proj_id
        if constrain:
            cfg['option'] = {}
            cfg['option']['MinConstraint'] = thresh

        alg_id = astra.algorithm.create(cfg)
        for i in range(0, y_pix):
            astra.data2d.store(sinogram_id, data[i, :, :])
            astra.algorithm.run(alg_id, iterations)
            rec[i, :, :] = astra.data2d.get(rec_id)

        astra.algorithm.delete(alg_id)
        astra.data2d.delete(rec_id)
        astra.data2d.delete(sinogram_id)
        astra.clear()
    return rec


def astra_project(obj, angles, cuda=False):
    """
    Calculate projection of a 3D object using Astra-toolbox.

    Args
    ----------
    obj : NumPy array
        Either a 2D or 3D array containing the object to project.
        If 2D, the structure is of the form [z, x] where z is the
        projectio axis.  If 3D, the strucutre is [y, z, x] where y is
        the tilt axis.
    angles : list or NumPy array
        The projection angles in degrees
    cuda : boolean
        If True, perform reconstruction using the GPU-accelerated algorithm.

    Returns
    ----------
    sino : Numpy array
        3D array of the form [y, angle, x] containing the projection of
        the input object

    """
    if len(obj.shape) == 2:
        obj = np.expand_dims(obj, 0)
    thetas = np.pi * angles / 180.
    y_pix, thickness, x_pix = obj.shape
    if cuda:
        vol_geom = astra.create_vol_geom(thickness, x_pix, y_pix)
        proj_geom = astra.create_proj_geom('parallel3d', 1.0, 1.0,
                                           y_pix, x_pix, thetas)
        sino_id, sino = astra.create_sino3d_gpu(obj,
                                                proj_geom,
                                                vol_geom)
    else:
        sino = np.zeros([y_pix, len(angles), x_pix], np.float32)
        vol_geom = astra.create_vol_geom(thickness, x_pix)
        proj_geom = astra.create_proj_geom('parallel', 1.0, x_pix, thetas)
        proj_id = astra.create_projector('strip', proj_geom, vol_geom)
        for i in range(0, y_pix):
            sino_id, sino[i, :, :] = astra.create_sino(obj[i, :, :],
                                                       proj_id,
                                                       vol_geom)
    sino = np.rollaxis(sino, 1)
    astra.clear()
    return sino
