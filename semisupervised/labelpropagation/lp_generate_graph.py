import pyspark.ml.linalg as ml_linalg
from pyspark.mllib.linalg.distributed import MatrixEntry
from pyspark.ml import feature
from pyspark.sql.functions import udf
import numpy as np


def _compute_bfs(vec_1, vec_2, sigma=0.42):
    return np.exp(-vec_1.squared_distance(vec_2) / sigma ** 2)


def _tolerance_cut(value, tol=10e-10):
    if value <= tol:
        return 0
    else:
        return value


def _to_dense(x):
    return ml_linalg.DenseVector(x.toArray())


def _make_feature_vector(df, feature_col=None):
    return 'features', feature.VectorAssembler(inputCols=feature_col, outputCol='features').transform(df)

def _scale_data_frame(df, vector=None):
    if vector:
        df = df.withColumn(vector, udf(_to_dense, ml_linalg.VectorUDT())(vector))
        scale = feature.StandardScaler(
            withMean=True, withStd=True,
            inputCol='vector', outputCol='std_vector')
        model = scale.fit(df)
        return (model
            .transform(df)
            .select([i for i in df.columns if i != vector] + [scale.getOutputCol()])
            .withColumnRenamed(existing=scale.getOutputCol(), new=vector))


def do_cartesian(sc, df, id_col=None, feature_col=None, **kwargs):
    sigma = kwargs.get('sigma', 0.42)
    tol = kwargs.get('tolerance', 10e-10)
    standardize = kwargs.get('standardize', True)

    if isinstance(feature_col, list):
        feature_col, scaled_df = _make_feature_vector(df=df, feature_col=feature_col)


    if ~standardize:
        scaled_df = _scale_data_frame(df, vector=feature_col)
    else:
        scaled_df = df

    if id_col:
        vector_dict = scaled_df.select(id_col, feature_col).rdd.collectAsMap()
    else:
        vector_dict = (scaled_df.select(feature_col)
            .rdd.zipWithIndex().map(lambda x: (x[1], x[0][feature_col]))
            .collectAsMap())
    bc_vec = sc.broadcast(vector_dict)

    index_rdd = df.rdd.map(lambda x: x[id_col]).cache()
    cartesian_demon = index_rdd.cartesian(index_rdd).filter(lambda x: x[0] >= x[1])
    cartesian_distance_demon = cartesian_demon.map(lambda x: MatrixEntry(x[0], x[1], _compute_bfs(
        vec_1=bc_vec.value.get(x[0]), vec_2=bc_vec.value.get(x[1]), sigma=sigma)))

    return cartesian_distance_demon.filter(lambda x: _tolerance_cut(x.value, tol))