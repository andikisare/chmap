
# 1. query database for all images in timeframe.
# 2. query LBCC histograms in timeframe.
# 3. determine which images lack a histogram

import os
import datetime
import numpy as np
import pandas as pd

from settings.app import App
import modules.DB_classes as db_class
from modules.DB_funs import init_db_conn, query_euv_images, add_hist, get_method_id, query_hist


# TIME RANGE
hist_query_time_min = datetime.datetime(2007, 1, 1, 0, 0, 0)
hist_query_time_max = datetime.datetime(2020, 1, 1, 0, 0, 0)

# define instruments
inst_list = ["AIA", "EUVI-A", "EUVI-B"]

# declare map and binning parameters
R0 = 1.01
log10 = True
lat_band = [- np.pi / 64., np.pi / 64.]

# define number of bins
n_mu_bins = 18
n_intensity_bins = 200

# recover local filesystem paths
raw_data_dir = App.RAW_DATA_HOME
hdf_data_dir = App.PROCESSED_DATA_HOME


# designate which database to connect to
use_db = "mysql-Q"       # 'sqlite'  Use local sqlite file-based db
                        # 'mysql-Q' Use the remote MySQL database on Q
user = "turtle"         # only needed for remote databases.
password = ""           # See example109 for setting-up an encrypted password.  In this case leave password="", and
# init_db_conn() will automatically find and use your saved password. Otherwise, enter your MySQL password here.
# setup local database paths (only used for use_db='sqlite')
database_dir = App.DATABASE_HOME
sqlite_filename = App.DATABASE_FNAME


# ------------ NO NEED TO UPDATE ANYTHING BELOW  ------------- #

# setup database connection
if use_db == 'sqlite':
    # setup database connection to local sqlite file
    sqlite_path = os.path.join(database_dir, sqlite_filename)

    if os.path.exists(sqlite_path):
        os.remove(sqlite_path)
        print("\nPrevious file ", sqlite_filename, " deleted.\n")

    db_session = init_db_conn(db_name=use_db, chd_base=db_class.Base, sqlite_path=sqlite_path)
elif use_db == 'mysql-Q':
    # setup database connection to MySQL database on Q
    db_session = init_db_conn(db_name=use_db, chd_base=db_class.Base, user=user, password=password)



# creates mu bin & intensity bin arrays
mu_bin_edges = np.linspace(0.1, 1.0, n_mu_bins + 1, dtype='float')
image_intensity_bin_edges = np.linspace(0, 5, num=n_intensity_bins + 1, dtype='float')

# create LBC method
meth_name = 'LBCC'
meth_desc = 'LBCC Theoretic Fit Method'
method_id = get_method_id(db_session, meth_name, meth_desc, var_names=None, var_descs=None, create=True)

# query EUV images
query_pd = query_euv_images(db_session=db_session, time_min=hist_query_time_min,
                                         time_max=hist_query_time_max)

# query LBCC histograms
# hist_pd = query_hist(db_session, meth_id=method_id[1], n_mu_bins=n_mu_bins, n_intensity_bins=n_intensity_bins,
#                      lat_band=lat_band, time_min=hist_query_time_min, time_max=hist_query_time_max)
# only return indexing columns
hist_query = db_session.query(db_class.Histogram.hist_id, db_class.Histogram.image_id,
                           db_class.Histogram.meth_id, db_class.Histogram.date_obs,
                           db_class.Histogram.instrument).filter(
    db_class.Histogram.date_obs.between(hist_query_time_min, hist_query_time_max))
hist_pd = pd.read_sql(hist_query.statement, db_session.bind)

# compare image results to hist results based on image_id
in_index = query_pd.image_id.isin(hist_pd.image_id)

# return only images that do not have corresponding histograms
images_no_hist = query_pd[~in_index]

# return all LBCC parameters
lbcc_par_query = db_session.query(db_class.Var_Vals, db_class.Image_Combos).filter(
    db_class.Image_Combos.date_mean.between(hist_query_time_min, hist_query_time_max)
    ).filter(db_class.Var_Vals.meth_id == method_id[1]).filter(
    db_class.Var_Vals.combo_id == db_class.Image_Combos.combo_id)
lbcc_pars = pd.read_sql(lbcc_par_query.statement, db_session.bind)



# query IIT histograms
# only return indexing columns
meth_name = "IIT"
meth_desc = "IIT Fit Method"
method_id = get_method_id(db_session, meth_name, meth_desc, var_names=None, var_descs=None, create=False)

iit_hist_query = db_session.query(db_class.Histogram.hist_id, db_class.Histogram.image_id,
                           db_class.Histogram.meth_id, db_class.Histogram.date_obs,
                           db_class.Histogram.instrument).filter(
    db_class.Histogram.date_obs.between(hist_query_time_min, hist_query_time_max),
db_class.Histogram.meth_id == method_id[1])
iit_hist_pd = pd.read_sql(iit_hist_query.statement, db_session.bind)






db_session.close
