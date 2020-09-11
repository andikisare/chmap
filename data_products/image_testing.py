"""
create histogram of image intensities for comparison
used to determine "bad" images and flag in the database
"""

import os
import time
import datetime
import numpy as np
import pandas as pd
from settings.app import App
import modules.DB_classes as db_class
from modules.DB_funs import init_db_conn, query_euv_images, add_hist, get_method_id, update_image_val
import modules.datatypes as psi_d_types
import matplotlib.pyplot as plt
import matplotlib as mpl

###### ------ PARAMETERS TO UPDATE -------- ########

# TIME RANGE
query_time_min = datetime.datetime(2011, 1, 1, 0, 0, 0)
query_time_max = datetime.datetime(2012, 1, 1, 0, 0, 0)

# define instruments
inst_list = ["AIA", "EUVI-A", "EUVI-B"]

# define number of bins
n_mu_bins = 18
n_intensity_bins = 200

# declare map and binning parameters
R0 = 1.01
log10 = True
lat_band = [- np.pi / 64., np.pi / 64.]

# recover database paths
raw_data_dir = App.RAW_DATA_HOME
hdf_data_dir = App.PROCESSED_DATA_HOME
database_dir = App.DATABASE_HOME
sqlite_filename = App.DATABASE_FNAME

# setup database connection
use_db = "sqlite"
sqlite_path = os.path.join(database_dir, sqlite_filename)
db_session = init_db_conn(db_name=use_db, chd_base=db_class.Base, sqlite_path=sqlite_path)


#### FUNCTIONS
# remove image from "bad data" list
def remove_image(image_ids, bad_data):
    for image_id in image_ids:
        index = np.where(bad_data.image_id == int(image_id))
        bad_data = bad_data.drop(index[0][0])
    return bad_data


# create list of image ids to flag
def flag_image(image_ids, bad_data):
    bad_images = pd.DataFrame()
    for image_id in image_ids:
        index = np.where(bad_data.image_id == int(image_id))
        print(index)
        bad_images = bad_images.append(bad_data.iloc[index[0][0]])
    return bad_images


# find outliers
def find_anomalies(data):
    anomalies = []
    # Set upper and lower limit to 3 standard deviation
    random_data_std = np.std(data)
    random_data_mean = np.mean(data)
    anomaly_cut_off = random_data_std * 3

    lower_limit = random_data_mean - anomaly_cut_off
    upper_limit = random_data_mean + anomaly_cut_off
    # Generate outliers
    for index, outlier in enumerate(data):
        if outlier > upper_limit or outlier < lower_limit:
            anomalies.append(index)
    return anomalies


# plot bad images
def plot_bad_images(hdf_data_dir, bad_data):
    for index, row in bad_data.iterrows():
        print("Plotting image number", row.image_id, ".")
        if row.fname_hdf == "":
            print("Warning: Image # " + str(row.image_id) + " does not have an associated hdf file. Skipping")
            continue
        hdf_path = os.path.join(hdf_data_dir, row.fname_hdf)
        los_image = psi_d_types.read_los_image(hdf_path)
        # add coordinates to los object
        los_image.get_coordinates(R0=R0)

        #### plot image
        # set color palette and normalization (improve by using Ron's colormap setup)
        norm = mpl.colors.LogNorm(vmin=1.0, vmax=np.nanmax(los_image.data))
        # norm = mpl.colors.LogNorm()
        im_cmap = plt.get_cmap('sohoeit195')

        # remove extremely small values from data so that log color scale treats them as black
        # rather than white
        plot_arr = los_image.data
        plot_arr[plot_arr < .001] = .001

        # plot the initial image
        plt.figure(row.image_id)
        plt.imshow(plot_arr, extent=[los_image.x.min(), los_image.x.max(), los_image.y.min(), los_image.y.max()],
                   origin="lower", cmap=im_cmap, aspect="equal", norm=norm)
        plt.xlabel("x (solar radii)")
        plt.ylabel("y (solar radii)")
        plt.title(row.image_id)
    plt.show()


# ------------ NO NEED TO UPDATE ANYTHING BELOW  ------------- #

# loop over instrument
for instrument in inst_list:

    # query EUV images
    query_instrument = [instrument, ]
    query_pd = query_euv_images(db_session=db_session, time_min=query_time_min,
                                time_max=query_time_max, instrument=query_instrument)
    hist_list = np.zeros((len(query_pd), n_intensity_bins))
    for index, row in query_pd.iterrows():
        print("Processing image number", row.image_id, ".")
        if row.fname_hdf == "":
            print("Warning: Image # " + str(row.image_id) + " does not have an associated hdf file. Skipping")
            continue
        hdf_path = os.path.join(hdf_data_dir, row.fname_hdf)
        los_temp = psi_d_types.read_los_image(hdf_path)
        # add coordinates to los object
        los_temp.get_coordinates(R0=R0)
        # perform 2D histogram on mu and image intensity
        # indices within the latitude band and with valid mu
        lat_band_index = np.logical_and(los_temp.lat <= max(lat_band), los_temp.lat >= min(lat_band))
        mu_index = np.logical_and(los_temp.mu > 0, los_temp.mu <= los_temp.mu.max())
        use_index = np.logical_and(mu_index, lat_band_index)

        use_data = los_temp.data[use_index]
        if log10:
            use_data = np.where(use_data > 0, use_data, 0.01)
            use_data = np.log10(use_data)

        # generate intensity histogram
        hist_list[index, :], bin_edges = np.histogram(use_data, bins=n_intensity_bins)

    mean = np.zeros(len(query_pd))
    std = np.zeros(len(query_pd))
    z_score = np.zeros((len(query_pd), n_intensity_bins))
    x = np.arange(0, len(query_pd))
    for index, hist in enumerate(hist_list):
        plt.figure("Histogram")
        plt.plot(hist)
        mean[index] = np.mean(hist)
        std[index] = np.std(hist)

    # plot mean
    plt.figure("Mean")
    plt.scatter(x, mean)
    plt.xlabel("Index")
    plt.ylabel("Mean")
    plt.title("Mean")
    # plot standard deviation
    plt.figure("STD")
    plt.scatter(x, std)
    plt.xlabel("Index")
    plt.ylabel("STD")
    plt.title("STD")

    # determine median of mean, std
    med_mean = np.median(mean)
    med_std = np.median(std)

    # check if mean, std is outlier
    # if outlier, flag in database
    # TODO: what determines an outlier
    # z_score = np.zeros((len(query_pd)))
    # for index, mean1 in enumerate(mean):
    #     z_score[index] = (mean1 - med_mean) / std[index]
    # plt.figure("Z_Score")
    # plt.scatter(x, z_score)

    # if outlier, add image id to bad_data list
    bad_data = pd.DataFrame()
    # standard deviation outlier
    std_outlier = find_anomalies(std)
    for outlier in std_outlier:
        bad_data = bad_data.append(query_pd.iloc[outlier], ignore_index=True)

    # mean outlier
    mean_outlier = find_anomalies(mean)
    for outlier in mean_outlier:
        bad_data = bad_data.append(query_pd.iloc[outlier], ignore_index=True)

    # plot the bad images
    plot_bad_images(hdf_data_dir, bad_data)

    # remove images you don't want to flag
    remove_image_ids = []
    bad_images = remove_image(remove_image_ids, bad_data)

    # OR, add images you want to flag
    add_image_ids = []
    bad_images = flag_image(add_image_ids, bad_data)

    # flag bad image in database
    for index, image_row in bad_images.iterrows():
        update_image_val(db_session, image_row, 'flag', -1)

