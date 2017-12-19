from semisupervised.LabelPropagation import label_propagation
from shared.WorkflowLogger import logger_info_decorator
from shared.parse_algorithm_variables import parse_algorithm_variables
from shared.Plot2DGraphs import plot3D
from pyspark.sql import SparkSession
from pyspark.sql import types as T
from pyspark.sql import functions as F
import  functools

default_lp_param = {'sigma': 0.42, 'tol':0.01, 'k': 2, 'max_iters': 5,'eval_type': 'max' }


@logger_info_decorator
def run(sc, **kwargs):

    # set some stuff
    spark = SparkSession(sparkContext=sc)
    spark.conf.set("spark.sql.crossJoin.enabled", "true")
    input_data = kwargs.get('input_data', None)
    feature_columns = [T.StructField(f, T.DoubleType(), False) for f in kwargs.get('features', None)]
    label_columns = [T.StructField(kwargs.get('labels', None), T.IntegerType(), True)]
    id_column = [T.StructField(idx, T.IntegerType(), False) for idx in kwargs.get('id', 'id')]
    algo_types = parse_algorithm_variables(kwargs.get('algo_params', {}))
    for key in default_lp_param.keys():
        if key not in algo_types:
            algo_types[key] = default_lp_param[key]

    #Import data
    input_data_frame = spark.read.csv(
        path=input_data, header=True, inferSchema=True, #schema=T.StructType(id_column+label_columns+feature_columns),
       mode='PERMISSIVE')
    # Execute algorithm
    partial_lp = functools.partial(
        label_propagation, sc=sc, data_frame=input_data_frame,
        label_col=kwargs.get('labels', None), id_col=kwargs.get('id', 'id')[0],
        feature_cols=kwargs.get('features', None))
    output_data_frame = partial_lp(**algo_types)

    merged_df = input_data_frame.alias('a').join(
        output_data_frame.alias('b'), on=(F.col('a.id') == F.col('b.row')),
        how='inner')
    plot3D(merged_df, 'label')
    # Return result
    return output_data_frame