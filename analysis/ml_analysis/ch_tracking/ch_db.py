"""
Author: Opal Issan, Feb 13th, 2021.

A data structure for a set of coronal hole objects.

"""

import json
import cv2
import numpy as np
from scipy.spatial import distance as dist
from analysis.ml_analysis.ch_tracking.frame import Frame
from analysis.ml_analysis.ch_tracking.contour import Contour
from analysis.ml_analysis.ch_tracking.coronalhole import CoronalHole
from analysis.ml_analysis.ch_tracking.knn import KNN
from analysis.ml_analysis.ch_tracking.areaoverlap import area_overlap, classification_results
import matplotlib.pyplot as plt


class CoronalHoleDB:
    """ Coronal Hole Object Data Structure."""
    # contour binary threshold.
    BinaryThreshold = 200
    # coronal hole area threshold.
    AreaThreshold = 5e-3
    # window to match coronal holes.
    window = 5
    # parameter for dilation. (this should be changed for larger images.
    gamma = 10
    # area overlap threshold for matching coronal holes.
    area_thresh = 0.5

    def __init__(self):
        # list of Contours that are part of this CoronalHole Object.
        self.ch_dict = dict()

        # the unique identification number of for each coronal hole in the db.
        self.total_num_of_coronal_holes = 0

        # frame number.
        self.frame_num = 0

        # data holder for previous *window* frames. TODO: is it better to use a dictionary?
        self.window_holder = [None] * self.window

    def __str__(self):
        return json.dumps(
            self.json_dict(), indent=4, default=lambda o: o.json_dict())

    def json_dict(self):
        return {
            'num_frames': self.frame_num,
            'num_coronal_holes': self.total_num_of_coronal_holes,
            'coronal_holes': [ch.json_dict() for identity, ch in self.ch_dict.items()]
        }

    def _assign_id_coronal_hole(self, ch):
        """Assign a unique ID number to coronal hole "

        Parameters
        ----------
        ch CoronalHole object

        Returns
        -------
        ch with assigned id.
        """

        # set the index id.
        ch.id = self.total_num_of_coronal_holes + 1
        # update coronal hole holder.
        self.total_num_of_coronal_holes += 1
        return ch

    def _assign_color_coronal_hole(self, ch):
        """Assign a unique color to coronal hole"

        Parameters
        ----------
        ch CoronalHole object

        Returns
        -------
        ch with assigned color.
        """
        ch.color = self.generate_ch_color()
        return ch

    def _add_coronal_hole_to_dict(self, ch):
        """Add coronal hole to dictionary, assign id and color.

        Parameters
        ----------
        ch CoronalHole object

        Returns
        -------
        None
        """
        # add to database.
        self.ch_dict[ch.id] = ch

    def update_previous_frames(self, frame):
        """Update *window* previous frame holders.

        Parameters
        ----------
        frame: new frame object Frame() in frame.py

        Returns
        -------
        None
        """
        # remove the first frame since its not in the window interval.
        self.window_holder.pop(0)
        # append the new frame to the end of the list.
        self.window_holder.append(frame)

    # @staticmethod
    # def _compute_distance(curr, prev):
    #     """ compute the distance between each element in two arrays containing the coronal hole centroids.
    #
    #     Parameters
    #     ----------
    #     curr: new_index
    #     prev: old_index
    #     TODO : REMOVE THIS
    #
    #     Returns
    #     -------
    #     new_index, old_index
    #     """
    #     return dist.cdist(curr, prev)
    #
    # def _create_priority_queue(self, centroid_curr, centroid_prev):
    #     """ arrange the coronal hole matches in order.
    #     [(new_index, old_index)]
    #     TODO: REMOVE THIS """
    #     distance = self._compute_distance(curr=centroid_curr, prev=centroid_prev)
    #     rows = distance.min(axis=1).argsort()
    #     cols = distance.argmin(axis=1)[rows]
    #     return list(zip(rows, cols))
    #
    # def _priority_queue_remove_duplicates(self, centroid_curr, centroid_prev):
    #     """remove duplicates from the priority queue. such as:
    #             [(0,1), (1, 1), (2, 2)] --> [(0, 1), (2, 2)]
    #
    #     Parameters
    #     ----------
    #     centroid_curr: list of current frame centroids.
    #     centroid_prev: list of previous frame centroids.
    #
    #     Returns
    #     -------
    #     modified queue list.
    #     TODO: REMOVE THIS
    #     """
    #     queue = self._create_priority_queue(centroid_curr, centroid_prev)
    #     return [(a, b) for i, [a, b] in enumerate(queue) if not any(c == b for _, c in queue[:i])]

    # def match_coronal_holes(self, contour_list):
    #     """Match coronal holes to previous *window* frames.
    #
    #     Parameters
    #     ----------
    #     contour_list: current frame Contour() list.
    #
    #     Returns
    #     -------
    #     None
    #     TODO: FIX THIS.
    #     """
    #     # if this is the first image in the sequence then just save coronal holes.
    #     if self.frame_num == 1:
    #         for ii in range(len(contour_list)):
    #             contour_list[ii] = self._assign_id_coronal_hole(ch=contour_list[ii])
    #             contour_list[ii] = self._assign_color_coronal_hole(ch=contour_list[ii])
    #             # add Coronal Hole to database.
    #             self._insert_new_contour_to_dict(contour=contour_list[ii])
    #         self.p1 = Frame(contour_list=contour_list, identity=self.frame_num)
    #
    #     # match coronal holes to p1.
    #     else:
    #         centroid_curr = [ch.pixel_centroid for ch in contour_list]
    #         queue = self._priority_queue_remove_duplicates(centroid_curr=centroid_curr,
    #                                                        centroid_prev=self.p1.centroid_list)
    #         for curr_index, prev_index in queue:
    #             # set the match
    #             contour_list[curr_index].id = self.p1.contour_list[prev_index].id
    #             contour_list[curr_index].color = self.p1.contour_list[prev_index].color
    #             self.ch_dict[contour_list[curr_index].id].insert_contour_list(contour=contour_list[curr_index])
    #             self.ch_dict[contour_list[curr_index].id].insert_number_frame(frame_num=self.frame_num)
    #
    #         # mark the index matched
    #         index_list = np.arange(0, len(contour_list))
    #         index_list = np.delete(index_list, [a for a, b in queue])
    #
    #         # add all leftover coronal holes are in index_list.
    #         # check if they match to previous
    #
    #         for ii in index_list:
    #             # set the index id and color.
    #             contour_list[ii] = self._assign_id_coronal_hole(ch=contour_list[ii])
    #             contour_list[ii] = self._assign_color_coronal_hole(ch=contour_list[ii])
    #             self._insert_new_contour_to_dict(contour=contour_list[ii])
    #
    #         # save contour list
    #         self.update_previous_frames(frame=Frame(contour_list=contour_list, identity=self.frame_num))

    def _insert_new_contour_to_dict(self, contour):
        """insert a new contour to dict.

        Parameters
        ----------
        contour: Contour() object

        Returns
        -------
        None
        """
        coronal_hole = CoronalHole(identity=contour.id)
        coronal_hole.insert_contour_list(contour=contour)
        coronal_hole.insert_number_frame(frame_num=self.frame_num)
        self.ch_dict[contour.id] = coronal_hole

    @staticmethod
    def _interval_overlap(t1, t2, t3, t4):
        """check if two intervals overlap.

        Parameters
        ----------
        t1: int
        t2: int
        t3: int
        t4: int

        Returns
        -------
        Boolean
        The two intervals are built from [t1,t2] and [t3,t4] assuming t1 <= t2 and t3 <=t4.
        If the two intervals overlap: return True, otherwise False.
        """
        if t1 <= t3 <= t2:
            return True
        elif t1 <= t4 <= t2:
            return True
        elif t3 <= t1 <= t4:
            return True
        elif t3 <= t2 <= t4:
            return True
        return False

    def save_contour_pixel_locations(self, rbg_image, color_list):
        """This function will save all the image pixel coordinates that are assigned to each coronal hole.

        Parameters
        ----------
        rbg_image: rbg lon-lat classified coronal hole image.
        color_list: list of contour unique colors.

        Returns
        -------
        coronal_hole_list : coronal hole list of Contour object.
        """
        # loop over each contour saved.
        coronal_hole_list = []
        for color in color_list:
            # save pixel locations.
            mask = np.all(rbg_image == color, axis=-1)
            # find image pixel coordinates.
            contour_pixel = np.asarray(np.where(mask))
            # save contour in a list if its not zero.
            coronal_hole_list.append(Contour(contour_pixels=contour_pixel, frame_num=self.frame_num))
        return coronal_hole_list

    def plot_dilated_contours(self, contours):
        """Draw filled contours of dilated greyscale input image.

        Parameters
        ----------
        contours: opencv contours.

        Returns
        -------
        rbg: image where each contour has a unique color
        color_list: list of unique contour colors.
        """
        # initialize RBG image.
        rbg = np.zeros((Contour.n_t, Contour.n_p, 3), dtype=np.uint8)
        # initialize contour color list.
        color_list = np.zeros((len(contours), 3))

        # draw contours on rbg.
        for ii, contour in enumerate(contours):
            color_list[ii] = self.generate_ch_color()
            cv2.drawContours(image=rbg, contours=[contour], contourIdx=0, color=color_list[ii],
                             thickness=cv2.FILLED)
        return rbg, color_list.astype(int)

    def find_contours(self, image):
        """Find contours contours of a greyscale image.

        Parameters
        ----------
        image - gray scaled image.

        Returns
        -------
        rbg image
        list of unique colors.
        """
        # create binary threshold.
        ret, thresh = cv2.threshold(image, CoronalHoleDB.BinaryThreshold, 255, 0)
        # find contours using opencv function.
        contours, hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        # draw contours.
        return self.plot_dilated_contours(contours=contours)

    @staticmethod
    def generate_ch_color():
        """generate a random color

        Returns
        -------
        list of 3 integers between 0 and 255.
        """
        return np.random.randint(low=0, high=255, size=(3,)).tolist()

    def _force_periodicity(self, contour_list):
        """Force periodicity.

        Parameters
        ----------
        contour_list: list of all contours.

        Returns
        -------
        updated contour list.
        """
        # loop over each coronal hole and check if it is on the periodic border.
        ii = 0
        while ii <= len(contour_list) - 2:
            c1 = contour_list[ii]
            # check if it overlaps phi=0.
            if c1.periodic_at_zero:
                # check for all other periodic 2pi.
                jj = ii + 1
                while jj <= len(contour_list) - 1:
                    c2 = contour_list[jj]
                    if c2.periodic_at_2pi:
                        # get interval of latitude at 0.
                        t1, t2 = c1.lat_interval_at_zero()
                        # get interval of latitude at 2pi.
                        t3, t4 = c2.lat_interval_at_2_pi()
                        # check if intervals overlap.
                        if self._interval_overlap(t1, t2, t3, t4):
                            # merge the two contours by appending c2 to c1.
                            contour_list[ii] = self._merge_contours(c1=c1, c2=c2)
                            c1 = contour_list[ii]
                            contour_list.remove(c2)
                            ii += -1
                    jj += 1

            # check if it overlaps phi=2pi.
            if c1.periodic_at_2pi:
                # check for all other periodic 0.
                jj = ii + 1
                while jj <= len(contour_list) - 1:
                    c2 = contour_list[jj]
                    if c2.periodic_at_zero:
                        # get interval of latitude at 2pi.
                        t1, t2 = c1.lat_interval_at_2_pi()
                        # get interval of latitude at 0.
                        t3, t4 = c2.lat_interval_at_zero()
                        # check if intervals overlap.
                        if self._interval_overlap(t1, t2, t3, t4):
                            # merge the two contours by appending c2 to c1.
                            contour_list[ii] = self._merge_contours(c1=c1, c2=c2)
                            contour_list.remove(c2)
                            ii += -1
                    jj += 1
            ii += 1
        return contour_list

    @staticmethod
    def _merge_contours(c1, c2):
        """Merge c2 onto c1.

        Parameters
        ----------
        c1: Contour
        c2: Contour

        Returns
        -------
        c1 modified.
        """
        # append c2 pixel locations to c1.
        c1.contour_pixels_theta = np.append(c2.contour_pixels_theta, c1.contour_pixels_theta)
        c1.contour_pixels_phi = np.append(c2.contour_pixels_phi, c1.contour_pixels_phi)

        # update c1 periodic label.
        if c2.periodic_at_2pi:
            c1.periodic_at_2pi = True
        if c2.periodic_at_zero:
            c1.periodic_at_zero = True

        # update c1 area.
        c1.area = c1.area + c2.area

        # update c1 pixel centroid.
        c1.pixel_centroid = c1.compute_pixel_centroid()

        # update bounding box.
        c1.straight_box = np.append(c1.straight_box, c2.straight_box)

        # update bounding box area.
        c2.straight_box_area = c1.straight_box_area + c2.straight_box_area

        return c1

    @staticmethod
    def _remove_small_coronal_holes(contour_list):
        """Remove all contours that are smaller than AreaThreshold.

        Parameters
        ----------
        contour_list: list of all contours.

        Returns
        -------
        pruned contour list.
        """
        ii = 0
        while ii < len(contour_list):
            if contour_list[ii].area < CoronalHoleDB.AreaThreshold:
                contour_list.remove(contour_list[ii])
                ii += -1
            ii += 1
        return contour_list

    def prune_coronal_hole_list(self, contour_list):
        """Remove small coronal holes and force periodicity.

        Parameters
        ----------
        contour_list: list of all contours.

        Returns
        -------
        pruned contour list.
        """
        # remove small coronal holes.
        contour_list = self._remove_small_coronal_holes(contour_list=contour_list)
        # force periodicity.
        return self._force_periodicity(contour_list=contour_list)

    @staticmethod
    def kernel_width(t, gamma):
        """The dilation kernel width based on latitude.

        Parameters
        ----------
        t: float
            theta latitude
        gamma: int
            constant param of kernel width at the equator.
        Returns
        -------
            kernel width: int
        """
        # piecewise function.
        alpha = np.arcsin(gamma / Contour.n_p)
        # due to symmetry.
        beta = np.pi - alpha
        # loop over each interval.
        if alpha < t < beta:
            return int(gamma / np.sin(t))
        elif 0 <= t <= alpha:
            return Contour.n_p
        elif beta <= t <= np.pi:
            return Contour.n_p
        else:
            raise Exception("latitude value is invalid.")

    def lat_weighted_dilation(self, grey_scale_image):
        """latitude weighted dilation.
        TODO: optimize.

        Parameters
        ----------
        grey_scale_image

        Returns
        -------
            Latitude Weighted dilation
        """
        # theta array.
        theta = Contour.Mesh.t

        # create copy of greyscaled_image
        dilated_image = np.zeros(grey_scale_image.shape, dtype=np.uint8)

        # latitude weighted dilation.
        for ii in range(Contour.n_t):
            # build the flat structuring element.
            width = self.kernel_width(t=theta[ii], gamma=self.gamma)
            kernel = np.ones(width, dtype=np.uint8)
            # save dilated strip.
            dilated_image[ii, :] = np.reshape(cv2.dilate(grey_scale_image[ii, :], kernel, iterations=1), Contour.n_p)
        return dilated_image

    def assign_new_coronal_holes(self, contour_list):
        """Match coronal holes to previous *window* frames.

        Parameters
        ----------
        contour_list: current frame Contour() list.

        Returns
        -------
        None
        """
        # if this is the first image in the sequence then just save coronal holes.
        if self.frame_num == 1:
            for ii in range(len(contour_list)):
                contour_list[ii] = self._assign_id_coronal_hole(ch=contour_list[ii])
                contour_list[ii] = self._assign_color_coronal_hole(ch=contour_list[ii])
                # add Coronal Hole to database.
                self._insert_new_contour_to_dict(contour=contour_list[ii])

        else:
            # match coronal holes to previous *window* frames.
            matching_results = self.global_match_coronal_holes_algorithm(contour_list=contour_list)

            for ii in range(len(contour_list)):
                # new coronal hole
                if matching_results[ii] == 0:
                    contour_list[ii] = self._assign_id_coronal_hole(ch=contour_list[ii])
                    contour_list[ii] = self._assign_color_coronal_hole(ch=contour_list[ii])
                    # add Coronal Hole to database.
                    self._insert_new_contour_to_dict(contour=contour_list[ii])

                # existing coronal hole
                else:
                    contour_list[ii].id = matching_results[ii]
                    contour_list[ii].color = self.ch_dict[contour_list[ii].id].contour_list[0].color
                    self.ch_dict[contour_list[ii].id].insert_contour_list(contour=contour_list[ii])
                    # add Coronal Hole to database.
                    self.ch_dict[contour_list[ii].id].insert_number_frame(frame_num=self.frame_num)

        # update window holder.
        self.update_previous_frames(frame=Frame(contour_list=contour_list, identity=self.frame_num))

    def global_match_coronal_holes_algorithm(self, contour_list):
        """ Match coronal holes between sequential frames using KNN and area overlap probability.

        Parameters
        ----------
        contour_list: list of new coronal holes (identified in the latest frame, yet to be classified).

        Returns
        -------
            List of all corresponding ID to each coronal hole in contour_list. Note the corresponding ID is in order
            of coronal holes in contour_list.
            "0" means "new class"
        """
        # prepare dataset for K nearest neighbor algorithm.
        X_train, Y_train, X_test = self.prepare_knn_data(contour_list=contour_list)

        # fit the training data and classify.
        classifier = KNN(X_train=X_train, X_test=X_test, Y_train=Y_train)

        # if proba > thresh check its overlap of pixels area.
        area_check_list = classifier.check_list
        area_overlap_results = self.area_overlap_results(area_check_list=area_check_list, contour_list=contour_list)

        # return list of coronal holes corresponding unique ID.
        return self.get_coronal_hole_id(area_check_list=area_check_list, area_overlap_results=area_overlap_results)

    @staticmethod
    def get_coronal_hole_id(area_check_list, area_overlap_results):
        """ Return the result based on area overlap.
        TODO: is classification unique??

        Returns
        -------
            list of id corresponding to the contour list "0" means new class.
        """
        for ii, res in enumerate(area_overlap_results):
            max_val = max(res)
            if max_val == 0:
                area_overlap_results[ii] = 0
            else:
                max_index = res.index(max_val)
                area_overlap_results[ii] = area_check_list[ii][max_index]
        return area_overlap_results

    def prepare_knn_data(self, contour_list):
        """ prepare X_train, Y_train, X_test for KNN algorithm.
        TODO: Optimize.

        Returns
        -------
            X_train, Y_train, X_test
        """
        # prepare knn test dataset containing all the new coronal hole centroids in spherical coordinates. [theta, phi]
        # initialize X_test
        X_test = [ch.phys_centroid for ch in contour_list]

        # prepare X_train and Y_train saved in self.window_holder.
        X_train = []
        Y_train = []

        for frame in self.window_holder:
            if frame is not None:
                X_train.extend(frame.centroid_list)
                Y_train.extend(frame.label_list)
        return X_train, Y_train, X_test

    def prepare_area_overlap_data(self, id):
        """A list of all instances of this coronal hole in the last *window* of frames
        TODO: Optimize.
        Returns
        -------
            list of Contour()
        """
        res = []
        for frame in self.window_holder:
            if frame is not None:
                for ch in frame.contour_list:
                    if ch.id == id:
                        res.append(ch)
        return res

    def area_overlap_results(self, area_check_list, contour_list):
        """Results of area overlap between the new coronal holes found in the latest frame and the coronal holes
        saved in window_holder.

        Parameters
        ----------
        contour_list: list of new coronal holes (identified in the latest frame, yet to be classified).
        area_check_list: list of coronal holes that need to be checked.

        Returns
        -------

        """
        proba_mat = []

        for ii, ch_list in enumerate(area_check_list):
            prob_list = []
            for id in ch_list:
                coronal_hole_list = self.prepare_area_overlap_data(id=id)
                p = []
                for ch in coronal_hole_list:
                    p1, p2 = area_overlap(ch1=ch, ch2=contour_list[ii], da=Contour.Mesh.da)
                    p.append((p1 + p2) / 2)
                prob_list.append(np.mean(p))
            proba_mat.append(prob_list)

        return classification_results(area_overlap_list=proba_mat, thresh=self.area_thresh)
