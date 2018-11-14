# This class should execute the clustering model on the recived data.
from pyspark.ml import clustering
import pyspark.ml.feature as features
from pyspark.ml import Pipeline
from pyspark.ml import linalg
from pyspark import SQLContext
from pyspark.sql.dataframe import DataFrame
from pyspark.sql import functions as F
from shared.WorkflowLogger import logger_info_decorator, logger



class ExecuteWorkflow(object):
    """
    Object execute workflow. Builds a spark pipeline based on previous data from other class' and executes the pipeline
    """
    def __init__(
            self,
            dict_params=None,
            cols_features=None,
            cols_labels=None,
            standardize=True):
        """
        Constructor for ExecuteWorkflow
        :param dict_params:
        :param cols_features:
        :param cols_labels:
        :param standardize:
        """
        self._dict_parameters = dict_params  # dict of _parameters including model, mode and so on
        self._list_feature = ExecuteWorkflow._check_features(cols_features)
        self._list_labels = cols_labels
        self._bool_standardize = standardize
        self._algorithm = self._check_algorithm()
        self._pipeline = self.construct_pipeline()
        # logger.info('Initialized pipeline with transformations {}'.format(self._pipeline.getStages()))

    def __repr__(self):
        return "ExecuteWorkflow({}, {}, {}, {})".format(
            self._dict_parameters,
            self._list_feature,
            self._list_labels,
            self._bool_standardize)

    def __str__(self):
        return '{} - {}'.format(
            self._algorithm,
            self._dict_parameters,
        )

    @staticmethod
    def _check_features(cols_features):
        try:
            assert isinstance(cols_features, list), 'cols_features is not of type list, but of type: ' + str(type(cols_features))
            return cols_features
        except AssertionError as e:
            print(e.args[0])
            return

    @logger_info_decorator
    def _check_algorithm(self):
        try:
            applicable_algos = {
                'kmeans': 'KMeans',
                'gaussianmixture': 'GaussianMixture',
                'lda':'LDA'
            }
            algorithm = self._dict_parameters.pop(
                'algorithm', 'GaussianMixture'
            )
            return applicable_algos[algorithm.lower()]
        except AttributeError as ae:
            return 'GaussianMixture'

    @property
    def pipeline(self):
        return self._pipeline

    @property
    def parameters(self):
        return self._dict_parameters

    @property
    def features(self):
        return self._list_feature

    @property
    def labels(self):
        return self._list_labels

    @logger_info_decorator
    def construct_pipeline(self):
        """
        Method that creates a spark pipeline.
        :return: pipeline,  labels_features_and_parameters
        """

        model = getattr(clustering, self._algorithm)()
        param_map = [i.name for i in model.params]

        # Make sure that the params in self._params are the right for the algorithm
        dict_params_labels = dict(filter(
            lambda x: x[0] in param_map, self._dict_parameters.items())
        )
        dict_params_labels['featuresCol'] = 'scaled_features'

        # Model is set
        model = eval("clustering." + self._algorithm)(**dict_params_labels)
        dict_params_labels = dict(map(
            lambda i: (i.name, model.getOrDefault(i.name)), model.params)
        )
        # Add algorithm dict_params_labels
        dict_params_labels['algorithm'] = self._algorithm
        # dict_params_labels['seed'] = -1983291474829197226
        # dict_params_labels['initMode'] = 'random'
        stages = [model]  # [vectorized_features, caster, scaling_model, model]
        self._dict_parameters.update(dict_params_labels)  # dict gets updated

        return Pipeline(stages=stages)

    @logger_info_decorator
    def _vector_scale(self, df):
        to_dense_udf = F.udf(self._to_dense, linalg.VectorUDT())
        feature_str = 'features'

        # print(self._list_feature)
        vector_df = df.withColumn(
            colName=feature_str,
            col=to_dense_udf(*self._list_feature)
        )
        if self._bool_standardize:
            scaling_model = features.StandardScaler(
                inputCol=feature_str, outputCol="scaled_features",
                withMean=True, withStd=True).fit(vector_df)
        else:
            scaling_model = features.StandardScaler(
                inputCol=feature_str, outputCol="scaled_features",
                withMean=False, withStd=False).fit(vector_df)

        scaled_df = scaling_model.transform(vector_df)

        return scaled_df

        # scaled_df\
        #     .withColumn(
        #     colName='scaled_features',
        #     col=to_dense_udf(*self._list_feature)
        # )

    @staticmethod
    def _to_dense(*args):
        return linalg.Vectors.dense(*args)

    @logger_info_decorator
    def execute_pipeline(self, data_frame):
        """
        Executes the pipeline with the dataframe
        :param data_frame: spark data frame that can be used for the algorithm
        :return: model and cluster centers with id
        """
        assert isinstance(data_frame, DataFrame),\
            " data_frame is not of type dataframe but: "+type(data_frame)

        model = self._pipeline.fit(self._vector_scale(data_frame))
        return model

    @logger_info_decorator
    def apply_model(self, sc, model, data_frame):
        """
        Runs the model on a data frame
        :param model: PipelineModel from pyspark
        :param data_frame: Pyspark data frame
        :return: transformed pyspark data frame
        """
        from pyspark.ml.linalg import Vectors, VectorUDT
        sql_ctx = SQLContext.getOrCreate(sc)
        vector_scaled_df = self._vector_scale(data_frame)  # adds DenseVector for features and scaled_features
        transformed_data = model.transform(vector_scaled_df)  # adds prediction

        # udf's
        udf_cast_vector = F.udf(
            lambda x: Vectors.dense(x), VectorUDT())

        # Depending on the algorithm, different methods will extract the cluster centers
        if self._algorithm == 'GaussianMixture':
            # convert gaussian mean/covariance dataframe to pandas dataframe
            pandas_cluster_centers = (
                model.stages[-1].gaussiansDF.toPandas()
            )
            centers = sql_ctx.createDataFrame(
                self.gen_gaussians_center(
                    self._dict_parameters['k'],
                    pandas_cluster_centers
                )
            )
            merged_df = transformed_data.join(
                centers, self._dict_parameters['predictionCol'],
                'inner'
            )
            merged_df = merged_df.withColumn(
                'centers', udf_cast_vector('mean')
            )  # this is stupidity from spark!
        else:
            np_centers = model.stages[-1].clusterCenters()
            centers = self.gen_cluster_center(
                k=self._dict_parameters['k'],
                centers=np_centers
            )
            broadcast_center = sc.broadcast(centers)

            # Create user defined function for added cluster centers to data frame
            udf_assign_cluster = F.udf(
                f=lambda x: Vectors.dense(broadcast_center.value[x]),
                returnType=VectorUDT()
            )
            merged_df = transformed_data.withColumn(  # adds DenseVector of centers
                "centers", udf_assign_cluster(
                    self._dict_parameters['predictionCol']
                )
            )
        # return the result
        return merged_df

    @staticmethod
    def gen_gaussians_center(k, gaussians, prediction_label='prediction'):
        """
        Create a pandas dataframe containing cluster centers (mean) and covariances and adds an id
        :param k: number of clusters
        :param gaussians: pandas dataframe containing mean and covariance
        :param prediction_label: optional variable only if we customize the prediction label
        :return: pandas data frame with id, mean and covariance
        """
        # create dummy id pandas dataframe
        import pandas as pd
        predictions = {prediction_label: (range(k))}
        pandas_id = pd.DataFrame(
            data=predictions,
            columns=[prediction_label]
        )
        return pd.concat([gaussians, pandas_id], axis=1)

    @staticmethod
    def gen_cluster_center(k, centers):
        """
        Create a
        :param k: number of clusters
        :param centers: center of n_clusters
        :return: dict with all clusters
        """
        # import numpy as np
        assert isinstance(k, int), str(k)+" is not integer"
        assert isinstance(centers, list), " center is type: "+str(type(centers))
        # return dict(zip(np.array(range(0, k, 1)), centers))
        return dict(zip(range(0, k, 1), centers))
