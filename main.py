# the usual include statements
import os
import sys
import importlib

import pyspark

package_dict = {
    'semisupervised.zip': './semisupervised', 'cleaning.zip': './cleaning',
    'classification.zip': './classification', 'shared.zip': './shared', 'examples.zip': './examples'}

for zip_file, path in package_dict.items():
    if os.path.exists(zip_file):
        sys.path.insert(0, zip_file)
    else:
        sys.path.insert(0, path)

if __name__ == '__main__':
    from shared import OwnArgumentParser
    arguments = OwnArgumentParser()
    arguments.add_argument('--cluster_path', type=str, required=False)
    arguments.add_argument('--job', type=str, required=False)
    arguments.add_argument('--job_args', nargs='*')
    arguments.add_argument('--input_data', type=str)
    arguments.add_argument('--features', type=str, nargs='*')
    arguments.add_argument('--id', type=str, nargs='*')
    arguments.add_argument('--labels', type=str, nargs='*', required=False)
    arguments.parse_arguments()

    all_args = dict()
    if arguments.job_args:
        all_args['algo_params'] = dict(arg.split('=') for arg in arguments.job_args)

    all_args['input_data'] = arguments.input_data
    all_args['features'] = arguments.features
    all_args['id'] = arguments.id
    all_args['labels'] = arguments.labels
    # dtu_cluster_path = 'file:///home/micsas/workspace/distributions/dist_workflow'
    # local_path = "file:/home/svanhmic/workspace/DABAI/Workflows/dist_workflow"
    # visma_cluster_path = 'file:/home/ml/deployments/workflows'
    py_files = ['/shared.zip', '/examples.zip', '/cleaning.zip', '/classification.zip', '/semisupervised.zip']

    spark_conf = pyspark.SparkConf()
    (spark_conf
        .set('spark.executor.cores', 4)
        .set('spark.executor.memory', '1G')
        .set('spark.executors', 2)
    )
    sc = pyspark.SparkContext(appName=arguments.job)
    job_module = importlib.import_module('{:s}'.format(arguments.job))
    # sc = pyspark.SparkContext(
    #     appName=arguments.job_name, pyFiles=[cluster_path+py_file for py_file in py_files], conf=spark_conf)
    # job_module = importlib.import_module('{:s}'.format(arguments.job_name))
    try:
        data_frame = job_module.run(sc, **all_args)
        # data_frame.printSchema()
        # data_frame.show()
        rdd = data_frame.toJSON()  # .saveAsTextFile('hdfs:///tmp/cleaning.txt')
        js = rdd.collect()
        # print(js)
        if arguments.job == 'cleaning':
            print("""{"cluster":[""" + ','.join(js)+"""]}""")
        elif arguments.job == 'classification':
            print("""{"classification":[""" + ','.join(js) + """]}""")
        elif arguments.job == 'semisupervised':
            print("""{"semisuper":[""" + ','.join(js)+"""]}""")
    except TypeError as te:
        print('Did not run', te)  # make this more logable...
