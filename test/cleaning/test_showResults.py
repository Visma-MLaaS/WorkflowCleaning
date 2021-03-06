import unittest
from pyspark.tests import PySparkTestCase
from pyspark.sql import SparkSession
from pyspark.ml.linalg import DenseVector
from pyspark.sql import functions as F
import pandas as pd
import numpy as np

from cleaning.ShowCleaning import ShowResults


class TestShowResults(PySparkTestCase):

    def setUp(self):
        super().setUp()
        self.spark = SparkSession(self.sc)

        c1 = DenseVector(np.array([1.0, 1.0]))
        c2 = DenseVector(np.array([5.0, 5.0]))
        c3 = DenseVector(np.array([30.0, 30.0]))
        df = pd.DataFrame(
            {'prediction': [0, 0, 0, 0, 0, 0, 1, 2, 1, 1],
             'point_col': [DenseVector(np.array([1.0, 2.0])),
                           DenseVector(np.array([2.0, 1.0])),
                           DenseVector(np.array([0.0, 1.0])),
                           DenseVector(np.array([1.0, 0.0])),
                           DenseVector(np.array([1.0, -1.0])),
                           DenseVector(np.array([4.0, 5.0])),
                           DenseVector(np.array([5.0, 6.0])),
                           DenseVector(np.array([20.0, 30.0])),
                           DenseVector(np.array([5.0, 7.0])),
                           DenseVector(np.array([5.0, 10.0]))],
             'centers': [c1, c1, c1, c1, c1, c1, c2, c3, c2, c2]},
            columns=['prediction', 'point_col', 'centers'])

        self.dataframe = self.spark.createDataFrame(df)

    # probably not needed!!!
    def test_add_row_index(self):

        computed_dataframe = ShowResults._add_row_index(self.dataframe)
        self.assertIn(('rowId', 'bigint'), computed_dataframe.dtypes)

        computed_dataframe = ShowResults._add_row_index(self.dataframe, rowId='roow')
        self.assertIn(('roow', 'bigint'), computed_dataframe.dtypes)

    def test_add_distances(self):
        from math import sqrt
        computed_dataframe = ShowResults._add_distances(self.dataframe, point_col='point_col')
        self.assertIn(('distance', 'double'), computed_dataframe.dtypes)

        p_computed_dataframe = computed_dataframe.toPandas()
        actual_distances = [sqrt(1.0), sqrt(1.0), sqrt(1.0), sqrt(1.0), sqrt(4.0),
                            sqrt(9.0+16.0), sqrt(1.0), sqrt(100.0), sqrt(4.0), sqrt(25.0)]
        for idx, val in enumerate(actual_distances):
            self.assertEqual(val, p_computed_dataframe['distance'][idx])
        print('add_distance \n', p_computed_dataframe)

    def test_add_outliers(self):
        computed_dataframe = ShowResults._add_distances(self.dataframe, point_col='point_col')
        computed_pdf = ShowResults._add_outliers(computed_dataframe).toPandas()

        # Boundary pre calculated mean for prediction 0: mean+2*stddev
        actual_values = [False]*5+[True]+4*[False]
        self.assertListEqual(list(computed_pdf['is_outlier']), actual_values)
        print('add_outliers \n', computed_pdf)

    @unittest.skip('Reason: Compute summary not in play.')
    def test_compute_summary(self):
        computed_dataframe = ShowResults._add_distances(self.dataframe, point_col='point_col')
        computed_df = ShowResults._add_outliers(computed_dataframe)
        summary_pdf = ShowResults.compute_summary(computed_df).toPandas()

        # counts from predictionCol
        actual_count_prediction = [6, 3, 1]
        # counts from outliers in distance
        actual_count_outliers = [1, 0, 0]
        # percentage from actual_count_outliers / actual_count_prediction
        actual_count_percentage = list(map(float, ['%.f' % elem for elem in
                                                   [out/pre*100 for out, pre in
                                                    zip(actual_count_outliers, actual_count_prediction)]]))

        self.assertEqual(list(summary_pdf['count']), actual_count_prediction)
        self.assertEqual(list(summary_pdf['outlier_count']), actual_count_outliers)
        self.assertEqual(list(summary_pdf['outlier percentage']), actual_count_percentage)
        print('compute_summary \n', summary_pdf)

    def test_prepare_table_data(self):
        # not tested through
        table_df = ShowResults.prepare_table_data(self.dataframe, point_col='point_col').toPandas()
        print('prepare_table_data \n', table_df)

    @unittest.skip('reason: Not implemented')
    def test_cluster_graph(self):
        # not tested through

        table_df = ShowResults.prepare_table_data(self.dataframe, point_col='point_col').toPandas()
        grouped = table_df.groupby('prediction')
        for i in range(1, len(table_df.prediction.unique())+1):
            group_i = grouped.get_group(i)
            table_json = ShowResults.cluster_graph(group_i)
            print('cluster_graph \n', table_json)

    @unittest.skip('Reason: JSON_histogram not applicable')
    def test_json_histogram(self):
        # not tested through

        table_df = ShowResults.prepare_table_data(self.dataframe, point_col='point_col').toPandas()
        hist_json = ShowResults.json_histogram(table_df)
        print('json_hist \n', hist_json)

    def test_arrange_output(self):
        # Preamble: setup data
        features = ['a', 'b']
        id = 'id'
        prediction = 'Prediction'
        # Test 1: Are all columns there?

        shows = ShowResults(id=id, list_features=features, list_labels=['k'], predictionCol=prediction, k=10)
        d_point = 'dp'
        df = self._generate_data()
        arranged_df = shows.arrange_output(self.sc, df, data_point_name=d_point)
        expected_cols = [prediction, d_point, 'amount', 'percentage_outlier', 'amount_outlier', 'buckets']
        self.assertListEqual(sorted(expected_cols), sorted(arranged_df.columns))

    def _generate_data(self):
        df = self.spark.range(10)
        output = (df
                  .select(
                   'id', F.rand(42).alias('a'), F.randn(1).alias('b'),
                   F.round(10 * F.rand(42)).alias('Prediction'),
                   F.rand().alias('distance'))
                  .withColumn('is_outlier', F.when(F.col('distance') >= 0.7, 1.0).otherwise(0.))
                  .withColumn('computed_boundary', F.randn())
                  )
        return output

    def test_create_linspace(self):  # data, min, max, buckets, boundary):
        data = ShowResults.prepare_table_data(self.dataframe, point_col='point_col')
        data.show()



    # @unittest.skip('Test not created')
    def test_create_buckets(self):
        # Preamble: setup data
        df = self._generate_data()
        features = ['a', 'b']
        id = 'id'
        prediction = 'Prediction'

        shows = ShowResults.prepare_table_data(self.dataframe, point_col='point_col')
        # ShowResults(id=id, list_features=features, list_labels=['k'], predictionCol=prediction, k=10)
        buckets = shows.create_buckets(sc=self.sc, dataframe=df, buckets=20, prediction_col=prediction)

        print(buckets.rdd.take(1)[0]['buckets'])
        self.fail()



