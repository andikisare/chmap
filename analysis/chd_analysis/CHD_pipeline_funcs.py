"""
functions to create EUV/CHD maps and save to the database
1. Select images
2. Apply pre-processing corrections
    a. Limb-Brightening
    b. Inter-Instrument Transformation
3. Coronal Hole Detection
4. Convert to Map
5. Combine Maps
6. Save to DB
"""
import time
import pandas as pd
import numpy as np
import datetime

import modules.Plotting as EasyPlot
import ezseg.ezsegwrapper as ezsegwrapper
import modules.DB_funs as db_funcs
from modules.map_manip import combine_maps
import modules.datatypes as datatypes
import analysis.lbcc_analysis.LBCC_theoretic_funcs as lbcc_funcs
import analysis.iit_analysis.IIT_pipeline_funcs as iit_funcs


#### STEP ONE: SELECT IMAGES ####
# this step uses database functions from modules/DB_funs
# 1.) query some images
# query_pd = db_funcs.query_euv_images(db_session=db_session, time_min=query_time_min, time_max=query_time_max)
# 2.) generate a dataframe to record methods
# methods_list = db_funcs.generate_methdf(query_pd)


#### STEP TWO: APPLY PRE-PROCESSING CORRECTIONS ####
# get instrument combos
def get_inst_combos(db_session, inst_list, query_time_max, query_time_min):
    start = time.time()
    # query for combo ids within date range
    lbc_combo_query = []
    iit_combo_query = []
    for inst_index, instrument in enumerate(inst_list):
        lbc_combo = db_funcs.query_inst_combo(db_session, query_time_min - datetime.timedelta(days=180),
                                              query_time_max + datetime.timedelta(days=180),
                                              meth_name='LBCC Theoretic', instrument=instrument)
        iit_combo = db_funcs.query_inst_combo(db_session, query_time_min - datetime.timedelta(days=180),
                                              query_time_max + datetime.timedelta(days=180), meth_name='IIT',
                                              instrument=instrument)
        lbc_combo_query.append(lbc_combo)
        iit_combo_query.append(iit_combo)
    end = time.time()
    print("Combo IDs have been queried from the database in", end-start, "seconds.")
    return lbc_combo_query, iit_combo_query


# 2.) get dates
def get_dates(query_time_min, query_time_max, map_freq):
    map_frequency = int((query_time_max - query_time_min).seconds / 3600 / map_freq)
    moving_avg_centers = np.array(
        [np.datetime64(str(query_time_min)) + ii * np.timedelta64(map_freq, 'h') for ii in range(map_frequency + 1)])
    return moving_avg_centers


# 3.) apply IIP
def apply_ipp(db_session, center_date, query_pd, map_freq, inst_list, hdf_data_dir, lbc_combo_query,
              iit_combo_query, n_intensity_bins, R0):
    start = time.time()
    # create image lists
    image_pd = [None] * len(inst_list)
    los_list = [None] * len(inst_list)
    iit_list = [None] * len(inst_list)
    use_indices = [(2048, 2048)] * len(inst_list)
    # convert date to correct format
    print("\nStarting corrections for", center_date, "images:")
    date_time = np.datetime64(center_date).astype(datetime.datetime)
    # alpha, x for threshold
    sta_ind = inst_list.index('EUVI-A')
    alpha, x = db_funcs.query_var_val(db_session, meth_name='IIT', date_obs=date_time,
                                      inst_combo_query=iit_combo_query[sta_ind])
    # create dataframe for date
    hist_date = query_pd['date_obs']
    date_pd = query_pd[
        (hist_date >= np.datetime64(date_time - datetime.timedelta(hours=map_freq / 2))) &
        (hist_date <= np.datetime64(date_time + datetime.timedelta(hours=map_freq / 2)))]
    if len(date_pd) == 0:
        print("No Images to Process for this date.")
    else:
        for inst_ind, instrument in enumerate(inst_list):
            # query correct image combos
            hist_inst = date_pd['instrument']
            image_pd[inst_ind] = date_pd[hist_inst == instrument]
            image_row = image_pd[inst_ind].iloc[0]
            print("Processing image number", image_row.image_id, "for LBC and IIT Corrections.")
            # apply LBC
            los_list[inst_ind], lbcc_image, mu_indices, use_ind = lbcc_funcs.apply_lbc(db_session, hdf_data_dir,
                                                                                       lbc_combo_query[inst_ind],
                                                                                       image_row=image_row,
                                                                                       n_intensity_bins=n_intensity_bins,
                                                                                       R0=R0)
            # apply IIT
            lbcc_image, iit_list[inst_ind], use_indices[inst_ind] = iit_funcs.apply_iit(db_session,
                                                                                        iit_combo_query[inst_ind],
                                                                                        lbcc_image, use_ind,
                                                                                        los_list[inst_ind], R0=R0)
        end = time.time()
        print("Image Pre-Processing Corrections (Limb-Brightening and Inter-Instrument Transformation) have been "
              "applied "
              " in", end-start, "seconds.")
    return image_pd, los_list, iit_list, use_indices, alpha, x


#### STEP THREE: CORONAL HOLE DETECTION ####
def chd(iit_list, los_list, use_indices, inst_list, thresh1, thresh2, alpha, x, nc, iters):
    start = time.time()
    chd_image_list = [datatypes.CHDImage()] * len(inst_list)
    for inst_ind, instrument in enumerate(inst_list):
        image_data = iit_list[inst_ind].iit_data
        use_chd = use_indices[inst_ind].astype(int)
        use_chd = np.where(use_chd == 1, use_chd, -9999)
        nx = iit_list[inst_ind].x.size
        ny = iit_list[inst_ind].y.size
        t1 = thresh1 * alpha + x
        t2 = thresh2 * alpha + x
        ezseg_output, iters_used = ezsegwrapper.ezseg(np.log10(image_data), use_chd, nx, ny, t1, t2, nc, iters)
        chd_result = np.logical_and(ezseg_output == 0, use_chd == 1)
        chd_result = chd_result.astype(int)
        chd_image_list[inst_ind] = datatypes.create_chd_image(los_list[inst_ind], chd_result)
        chd_image_list[inst_ind].get_coordinates()
    end = time.time()
    print("Coronal Hole Detection algorithm implemented in", end-start, "seconds.")
    return chd_image_list


#### STEP FOUR: CONVERT TO MAPS ####
def create_singles_maps(inst_list, image_pd, iit_list, chd_image_list, methods_list, map_x, map_y, R0):
    start = time.time()
    image_info = []
    map_info = []
    map_list = [datatypes.PsiMap()] * len(inst_list)
    chd_map_list = [datatypes.PsiMap()] * len(inst_list)

    for inst_ind, instrument in enumerate(inst_list):
        # query correct image combos
        image_row = image_pd[inst_ind].iloc[0]
        # CHD map
        chd_map_list[inst_ind] = chd_image_list[inst_ind].interp_to_map(R0=R0, map_x=map_x, map_y=map_y,
                                                                        image_num=image_row.image_id)
        # map of IIT image
        map_list[inst_ind] = iit_list[inst_ind].interp_to_map(R0=R0, map_x=map_x, map_y=map_y,
                                                              image_num=image_row.image_id)
        # record image and map info
        chd_map_list[inst_ind].append_image_info(image_row)
        map_list[inst_ind].append_image_info(image_row)
        image_info.append(image_row)
        map_info.append(map_list[inst_ind].map_info)

        # generate a record of the method and variable values used for interpolation
        interp_method = {'meth_name': ("Im2Map_Lin_Interp_1",), 'meth_description':
            ["Use SciPy.RegularGridInterpolator() to linearly interpolate from an Image to a Map"] * 1,
                      'var_name': ("R0",), 'var_description': ("Solar radii",), 'var_val': (R0,)}
        # add to the methods dataframe for this map
        methods_list[inst_ind] = methods_list[inst_ind].append(pd.DataFrame(data=interp_method), sort=False)

        # incorporate the methods dataframe into the map object
        map_list[inst_ind].append_method_info(methods_list[inst_ind])
        chd_map_list[inst_ind].append_method_info(methods_list[inst_ind])
    end = time.time()
    print("Images interpolated to maps in", end-start, "seconds.")
    return map_list, chd_map_list, methods_list, image_info, map_info


#### STEP FIVE: CREATE COMBINED MAPS AND SAVE TO DB ####
def create_combined_maps(db_session, map_data_dir, map_list, chd_map_list, methods_list,
                         image_info, map_info, del_mu, mu_cutoff=0.0):
    # start time
    start = time.time()
    # create combined maps
    euv_combined, chd_combined = combine_maps(map_list, chd_map_list, del_mu=del_mu)
    # record merge parameters
    combined_method = {'meth_name': ("Min-Int-Merge_1", "Min-Int-Merge_1"), 'meth_description':
        ["Minimum intensity merge version 1"] * 2,
                       'var_name': ("mu_cutoff", "del_mu"), 'var_description': ("lower mu cutoff value",
                                                                                "max acceptable mu range"),
                       'var_val': (mu_cutoff, del_mu)}

    # generate a record of the method and variable values used for interpolation
    euv_combined.append_method_info(methods_list)
    euv_combined.append_method_info(pd.DataFrame(data=combined_method))
    euv_combined.append_image_info(image_info)
    euv_combined.append_map_info(map_info)
    chd_combined.append_method_info(methods_list)
    chd_combined.append_method_info(pd.DataFrame(data=combined_method))
    chd_combined.append_image_info(image_info)
    chd_combined.append_map_info(map_info)

    # plot maps
    EasyPlot.PlotMap(euv_combined, nfig="EUV Combined map for: " + str(euv_combined.image_info.date_obs[0]),
                     title="Minimum Intensity Merge Map\nDate: " + str(euv_combined.image_info.date_obs[0]))
    EasyPlot.PlotMap(euv_combined, nfig="EUV/CHD Combined map for: " + str(euv_combined.image_info.date_obs[0]),
                     title="Minimum Intensity EUV/CHD Merge Map\nDate: " + str(euv_combined.image_info.date_obs[0]))
    EasyPlot.PlotMap(chd_combined, nfig="EUV/CHD Combined map for: " + str(chd_combined.image_info.date_obs[0]),
                     title="Minimum Intensity EUV/CHD Merge Map\nDate: " + str(chd_combined.image_info.date_obs[0]),
                     map_type='CHD')

    # save EUV and CHD maps to database
    euv_combined.write_to_file(map_data_dir, map_type='synoptic_euv', filename=None, db_session=db_session)
    chd_combined.write_to_file(map_data_dir, map_type='synoptic_chd', filename=None, db_session=db_session)
    # end time
    end = time.time()
    print("Combined EUV and CHD Maps created and saved to the database in", end - start, "seconds.")
    return euv_combined, chd_combined

