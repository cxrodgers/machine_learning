import glob
import os
import numpy as np
from tqdm import tqdm
from scipy.ndimage import convolve
from scipy.stats import zscore
import matplotlib.pyplot as plt
import json
import cv2
import tifffile
import ipdb
from PIL import Image, ImageDraw, ImageFont
import config as cfg


def get_frames(folder, frame_numbers=None):
    """Gets stack of images from folder containing tiff files 
    
    folder : path to directory containing images ending in ".tif"
    
    frame_numbers : None, int, or list of integers
        If None, returns all images.
        If a list of integers, returns the corresponding images.
        If an integer, returns that many evenly spaced images.

    Returns : array of size (n_images, width, height)
    """
    # Get list of files in the directory
    files = glob.glob(os.path.join(folder, '*.tif'))
    
    # Error if no files found
    if len(files) == 0:
        raise IOError("no *.tif files found in %s" % folder)
    
    # Determine which to keep
    if frame_numbers is None:
        # Keep all of them
        load_files = files
    
    elif hasattr(frame_numbers, '__len__'):
        # Keep the ones specified by the list
        load_files = list(np.asarray(files)[frame_numbers])
    
    else:
        # Keep that many evenly spaced
        indices = np.floor(
            np.linspace(0, len(files) - 1, frame_numbers)
            ).astype(np.int)
        
        load_files = list(np.asarray(files)[indices])

    # Load them
    imgs = tifffile.imread(load_files)

    return imgs


def preview_vid(folder, frames_to_show=100, fps=30, close_when_done=False):
    """
    opens window and plays movie from sequence of .tif files
    shows the first frames_to_show frames contained in folder
    todo: auto contrast adjustment
    """

    # initialize window
    im_plot = plt.imshow(np.zeros((1, 1), dtype='float32'), cmap='plasma', vmin=0, vmax=1)
    plt.show()
    files = glob.glob(os.path.join(folder, '*.tif'))
    frames_to_show = min(frames_to_show, len(files))

    for f in tqdm(files[0:frames_to_show]):
        frame = tifffile.imread(f)
        im_plot.set_data(frame)
        plt.pause(1/fps)

    if close_when_done:
        plt.close('all')


def get_correlation_image(imgs):
    """
    given stack of images, returns image representing temporal correlation between each pixel and surrounding eight pixels
    """

    imgs = imgs.copy()  # make sure we're pointing to a new object

    # define 8 neighbors filter
    kernel = np.ones((3, 3), dtype='float32')
    kernel[1, 1] = 0
    mask = convolve(np.ones(imgs.shape[1:], dtype='float32'), kernel, mode='constant')

    # normalize image
    # imgs = zscore(imgs, axis=0)
    imgs -= np.mean(imgs, axis=0)
    imgs_std = np.std(imgs, axis=0)
    imgs_std[imgs_std == 0] = np.inf
    imgs /= imgs_std

    # compute correlation image
    img_corr = convolve(imgs, kernel[np.newaxis, :], mode='constant') / mask
    img_corr = imgs * img_corr
    img_corr = np.mean(img_corr, 0)

    return img_corr


def scale_img(img):
    """ scales numpy array between 0 and 1"""

    if np.ptp(img):
        img = (img - np.min(img)) / np.ptp(img)
    return img


def get_targets(folder, collapse_masks=False, centroid_radius=2, border_thickness=2):
    """
    for folder containing labeled data, returns masks for soma, border of cells, and centroid. returned as 3D bool
    stacks, with one mask per cell, unless collapse_masks is True, in which case max is taken across all cells
    """

    # get image dimensions
    with open(os.path.join(folder, 'info.json')) as f:
        dimensions = json.load(f)['dimensions'][1:3]

    # load labels
    with open(os.path.join(folder, 'regions', 'consensus_regions.json')) as f:
        cell_masks = [np.array(x['coordinates']) for x in json.load(f)]

    # compute masks for each neuron
    masks_soma, masks_border, masks_centroids = \
        [np.zeros((len(cell_masks), dimensions[0], dimensions[1]), dtype=bool) for _ in range(3)]

    for i, cell in enumerate(cell_masks):
        masks_soma[i, cell[:, 0], cell[:, 1]] = True
        _, contour, _ = cv2.findContours(masks_soma[i].astype('uint8'), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        masks_border[i] = cv2.drawContours(np.zeros(dimensions), contour, 0, 1, thickness=border_thickness).astype('bool')
        center = np.mean(cell, 0).astype('int')
        masks_centroids[i] = cv2.circle(masks_centroids[i].astype('uint8'), (center[1], center[0]), centroid_radius, 1, thickness=-1)

    # collapse across neurons
    if collapse_masks:
        [masks_soma, masks_border, masks_centroids] = \
            [np.max(x, 0) for x in (masks_soma, masks_border, masks_centroids)]

    masks = {
        'somas': masks_soma,
        'borders': masks_border,
        'centroids': masks_centroids
    }

    return masks


def add_contours(img, contour, color=(1, 0, 0)):
    """given 2D img, and 2D contours, returns 3D image with contours added in color"""

    img_contour = np.repeat(img[:,:,np.newaxis], 3, axis=2)
    inds = np.argwhere(contour)
    img_contour[inds[:, 0], inds[:, 1], :] = np.array(color)

    return img_contour


def enhance_contrast(img, percentiles=(5, 95)):
    """given 2D image, rescales the image between lower and upper percentile limits"""

    limits = np.percentile(img.flatten(), percentiles)
    img = np.clip(img-limits[0], 0, limits[1]-limits[0]) / np.ptp(limits)
    # img = np.clip(img, limits[0], limits[1]) / np.ptp(limits)

    return img


def save_prediction_img(file, X, y, y_pred=None, height=800, X_contrast=(0,100), column_titles=None):
    """ given X and y_pred for a single image, (network output), writes an image to file concatening everybody """

    # scaled from 0->1
    for i in range(X.shape[-1]):
        X[:, :, i] = scale_img(X[:, :, i])
        if X_contrast != (0, 100):
            X[:, :, i] = enhance_contrast(X[:, :, i], percentiles=X_contrast)
    if type(y_pred) == np.ndarray:
        for i in range(y_pred.shape[-1]):
            y_pred[:, :, i] = scale_img(y_pred[:, :, i])

    # concatenate layers horizontally
    X_cat = np.reshape(X, (X.shape[0], -1), order='F')
    y_cat = np.reshape(y, (y.shape[0], -1), order='F')
    if type(y_pred)==np.ndarray:
        y_pred_cat = np.reshape(y_pred, (y_pred.shape[0], -1), order='F')

    # make image where three rows are X, y, and y_pred
    if type(y_pred)==np.ndarray:
        cat = np.zeros((X.shape[0]*3, max(X_cat.shape[1], y_cat.shape[1])))
    else:
        cat = np.zeros((X.shape[0] * 2, max(X_cat.shape[1], y_cat.shape[1])))
    cat[:X.shape[0], :X_cat.shape[1]] = X_cat
    cat[X.shape[0]:X.shape[0]*2, :y_cat.shape[1]] = y_cat
    if type(y_pred)==np.ndarray:
        cat[X.shape[0]*2:, :y_cat.shape[1]] = y_pred_cat

    img = Image.fromarray((cat * 255).astype('uint8'))

    if column_titles is not None:
        font = ImageFont.truetype("arial.ttf", 20)
        img_draw = ImageDraw.Draw(img)
        for i, t in enumerate(column_titles):
            img_draw.text((X.shape[1] * i, 0), t, fill=255, font=font)

    img = img.resize((int((cat.shape[1] / cat.shape[0]) * height), height), resample=Image.NEAREST)
    img.save(file)


def write_sample_imgs(X_contrast=(0,100)):
    '''writes sample images for training and test data for all .npz files in training_data folder'''

    files = glob.glob(os.path.join(cfg.data_dir, 'training_data',  '*.npz'))

    for f in files:
        data = np.load(f, allow_pickle=True)
        X_mat = np.stack(data['X'][()].values(), axis=2)
        y_mat = np.stack(data['y'][()].values(), axis=2)
        file_name = os.path.join(cfg.data_dir, 'training_data', os.path.splitext(f)[0] + '.png')
        save_prediction_img(file_name, X_mat, y_mat, X_contrast=X_contrast, column_titles=data['X'][()].keys())








