"""
Created on May 15, 2017

@author: svanhmic
"""
import seaborn as sns
import numpy as np
import matplotlib.pyplot as plt
from pyspark.ml.linalg import SparseVector
import math
from scipy.stats import chi2


def compute_distance(point, center):
    """
    Computes the euclidean  distance from a data point to the cluster center.

    :param point: coordinates for given point
    :param center: cluster center
    :return: distance between point and center
    """
    if isinstance(point, SparseVector) | isinstance(center, SparseVector):
        p_d = point.toArray()
        c_d = center.toArray()
        return float(np.linalg.norm(p_d-c_d, ord=2))
    else:
        return float(np.linalg.norm(point - center, ord=2))


def make_histogram(dist: list): # , dim):
    """
    Makes the histogram of 
    
    :param dist: Spark data frame  TODO: make this a list input instead
    :param dim: number of _dimensions that needs to be plotted
    :return:
    """

    # isolate the distances from the data frame
    set_of_distances = set(dist)
    fig = plt.figure()
    if len(set_of_distances) > 1:
        # ax = fig.add_subplot(1, 1, 1)
        # x = np.linspace(chi2.ppf(0.01, dim), chi2.ppf(0.99, dim), 100)

        # ax.plot(
        #     x,
        #     chi2.pdf(x, dim),
        #     'r-',
        #     lw=5,
        #     alpha=0.6,
        #     label='chi2 pdf')

        sns.distplot(
            dist,
            rug=True,
            kde=True,
            norm_hist=False,
            # ax=ax)
        );

        fig.canvas.draw()
        plt.show()
    else:
        print('Too few datapoints to show')


def compute_percentage_dist(distance, max_distance):
    """

    :param max_distance:
    :param distance
    :return: distance between point and center
    """
    return float(max_distance-distance)/100


def make_components_histogram(agg_components, dimension):
    """
    Create a histogram of vector components for each cluster
    :param agg_components: Aggregated components perhaps even normalized
    :param dimension: labels containing name of each feature.
    :return: None. Displays a graph
    """
    pass


