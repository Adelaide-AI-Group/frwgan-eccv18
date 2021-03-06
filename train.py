"""
MIT License

Copyright (c) 2018 Rafael Felix Alves

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

train.py: Training routine.
    Reference: 
            Felix, R., Vijay Kumar, B. G., Reid, I., & Carneiro, G. (2018). Multi-modal Cycle-consistent Generalized Zero-Shot Learning. arXiv preprint arXiv:1808.00136.
            (download paper)[http://openaccess.thecvf.com/content_ECCV_2018/papers/RAFAEL_FELIX_Multi-modal_Cycle-consistent_Generalized_ECCV_2018_paper.pdf]
"""

__author__ = "Rafael Felix, Vijay Kumar and Gustavo Carneiro"
__copyright__ = "MIT License"
__credits__ = ["Rafael Felix", "Gustavo Carneiro", "Vijay Kumar", "Ian Reid"]
__license__ = "MIT License"
__version__ = "1.0.2"
__maintainer__ = "Rafael Felix"
__email__ = "rafael.felixalves@adelaide.edu.au"
__status__ = "production"
_repeat_=100
from routines.aux import __tensorboard_script__, __seed__, __git_version__, update_metric

def initialize(params):
    from util import setup, storage
    from os import environ

    if params.opt.setup:

        # Generating experimental setup folder
        print(':: Generating experimental setup folder')
        res = setup.mkexp(baseroot=params.opt.baseroot,
                          options=params,
                          bname='{}_{}'.format(params.opt.description, params.opt.timestamp),
                          sideinfo=params.opt.sideinfo,
                          subdirectories=params.opt.exp_directories)
        params.opt.root = res['root']

        for key in params.opt.exp_directories:
            params.opt.__setattr__('{}dir'.format(key), '{}/{}/'.format(params.opt.root, key))

        params.opt.namespace = res['namespace']
        print(':: Experiment will be save in:\n:: {}'.format(params.opt.root))

    params.save('{}/configuration_{}.json'.format(params.opt.root, params.opt.timestamp))
    params.print()

    params.opt.architecture = storage.Container(storage.Json.load(options.architecture_file))
    if params.opt.gpu_devices:
        environ["CUDA_VISIBLE_DEVICES"] = params.opt.gpu_devices

    try:
        version = __git_version__()
        storage.Json().save(version, '{}/git_version.json'.format(params.opt.root, params.opt.timestamp))
    except Exception as e:
        print(':: Exception:: {}'.format(e))
        print(Warning(':: Warning:: This project is not versioned yet'))

def train(model, params, dataset, knn, options, mflag='classifier', info=''):
    from util.experiments import label2hot, generate_metric_list
    from util.storage import Dict_Average_Meter
    from util.metrics import accuracy_per_class
    from sklearn.model_selection import train_test_split
    import numpy as np

    epochs = params.epochs if 'epochs' in params.__dict__.keys() else 10
    batch_size = params.batch if 'batch' in params.__dict__.keys() else 512

    # Splitting dataset into validation and 
    print('='*50, '\n:: [{}]Initializing training...'.format(mflag))
    _split = train_test_split(dataset.train.X,
                              dataset.train.Y-1,
                              dataset.train.A.continuous,
                              test_size=options.validation_split,
                              random_state=42)
    X_train, X_val, y_train, y_val, a_train, a_val = _split
    
    # OBS: this tool work as the oposite. If you want to test on ZSL you must set openval=1.
    # If you want to set on openval you must set zsl = 1.
    yclasses_train = np.zeros(knn.openset.data.shape[0])
    yclasses_train[knn.zsl.ids-1] = 1.

    yclasses_test = np.zeros(knn.openset.data.shape[0])
    yclasses_test[knn.openval.ids-1] = 1.
    
    yclasses_open = np.zeros(knn.openset.data.shape[0])



    # results Container
    response = Dict_Average_Meter()
    # Iteration over epochs
    for epoch in np.arange(1, epochs+1):

        data = {'x': X_train,
                'y': label2hot(y_train, dataset.n_classes),
                'a': a_train,
                'a_dict': knn.openset.data.astype(np.float32),
                'y_classes': yclasses_train.astype(np.float32),
                'info':':: || {}[{}] - Epochs {}/{} ||'.format(info, mflag, epoch, epochs),
                'train_type':mflag}

        val = {'x': X_val,
               'y': label2hot(y_val, dataset.n_classes),
               'a_dict': knn.openset.data,
               'y_classes': yclasses_train.astype(np.float32),
               'a': a_val,
               'train_type':mflag}
        train_answer = model.train(data, batch_size=batch_size)        
        train_eval = model.evaluate(data)

        response.update_meters("{}/{}/train/answer".format(model.namespace, mflag), train_answer)
        model.summary_dict("{}/{}/train/answer".format(model.namespace, mflag), train_answer)

        response.update_meters("{}/{}/train/val".format(model.namespace, mflag), train_eval)
        model.summary_dict("{}/{}/train/val".format(model.namespace, mflag), train_eval)

        def validation():

            #pre-train validation for regressor & classifier
            if (mflag != 'gan'):
                val_answer = model.evaluate(val)
                response.update_meters("{}/{}/val".format(model.namespace, mflag), val_answer)
                model.summary_dict("{}/{}/val".format(model.namespace, mflag), val_answer)

            # training validation for GAN
            if mflag is 'gan':
                val['z'] = model.get_noise(shape=a_val.shape)
                x_fake = model.generator(val)
                valfake = {'x': x_fake,
                           'y': label2hot(y_val, dataset.n_classes),
                           'a': a_val}

                fake_answer = model.evaluate(valfake)
                response.update_meters("{}/{}/val/fake".format(model.namespace, mflag), fake_answer)
                model.summary_dict("{}/{}/val/fake".format(model.namespace, mflag), fake_answer)

        validation()
        
        if ((options.save_model) and (epoch >= options.save_from)) or \
        (epoch in options.savepoints):
            
            model.save({'checkdir': options.checkpointdir,
                        'step':epoch,
                        'epochs': epochs,
                        'train_type': mflag})
    model.reset_counter()
    

    return response.as_dict()



def main(options, dataset, knn):

    from util.storage import DataH5py, Json
    from util.setup import mkdir
    import models
    
    ModelClass = models.__dict__[options.architecture.namespace].__MODEL__

    if options.load_model:
        # implement routine to load model
        pass
    else:
        # Setting model from json file architecture
        print(':: Creating new model. ')
        model = ModelClass(Json.load(options.architecture_file))
        
        # Setting session
        print(':: Setting TensorFlow session. ')
        gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=options.gpu_memory)
        config=tf.ConfigProto(allow_soft_placement=True, gpu_options=gpu_options)
        sess = tf.Session(config=config)
        model.set_session(sess)
        model.build()

    try:
        #response is a dict that saves all training metrics
        response = {}
        if options.train_cls:
            model.set_writer('{}/classifier/'.format(options.logsdir))
            mkdir('classifier', options.checkpointdir)
            response['classifier'] = train(model=model, 
                                           params=options.architecture.classifier,
                                           dataset=dataset, knn=knn,
                                           options=options,
                                           info='{}::{}: '.format(model.namespace, options.dbname))
            print("")
            DataH5py().save_dict_to_hdf5(dic=response, 
                                       filename='{}/classifier_train.h5'.format(options.resultsdir))

        if options.train_reg:
            model.set_writer('{}/regressor/'.format(options.logsdir))
            mkdir('regressor', options.checkpointdir)
            response['regressor'] = train(model=model, 
                                    params=options.architecture.regressor,
                                    dataset=dataset, knn=knn,
                                    options=options, mflag='regressor',
                                    info='{}::{}: '.format(model.namespace, options.dbname))
            print("")
            DataH5py().save_dict_to_hdf5(dic=response, filename='{}/regressor_train.h5'.format(options.resultsdir))


        if options.train_gan:
            mkdir('generator', options.checkpointdir)
            mkdir('discriminator', options.checkpointdir)
            model.set_writer('{}/gan/'.format(options.logsdir))
            response['gan'] = train(model=model, 
                                    params=options.architecture.gan,
                                    dataset=dataset, knn=knn,
                                    options=options, mflag='gan',
                                    info='{}::{}: '.format(model.namespace, options.dbname))
            print("")
            DataH5py().save_dict_to_hdf5(dic=response, filename='{}/gan_train.h5'.format(options.resultsdir))
        
        DataH5py().save_dict_to_hdf5(dic=response, filename='{}/full_train.h5'.format(options.resultsdir))

    except:
        import sys, traceback
        traceback.print_exc(file=sys.stdout)

    return model, None


if __name__ == '__main__':
    print('-'*100)
    print(':: Training file: {}'.format(__file__))
    print('-'*100)
    
    from options.gan import GANOptions as Options
    from util import datasets
    from sklearn.model_selection import train_test_split
    import tensorflow as tf
    from models import *

    try:
        print(':: Seeding to guarantee reproducibility')
        __seed__()
        print(':: Parsing parameters')
        params = Options()
        options = params.parse()

        print('-'*_repeat_,'\n:: Initializing experiment')
        initialize(params)
        print('-'*_repeat_,'\n:: Loading Dataset')
        dataset, knn = datasets.load(options.datadir)

        print(':: Generating tensorboard script')
        _tbscript_file_='tensorboard_script.sh'
        __tensorboard_script__(fname='/tmp/{}'.format(_tbscript_file_),
                               logidr=options.root)
        
        __tensorboard_script__(fname='{}/{}'.format(options.root, _tbscript_file_),
                               logidr=options.root)
        print(':: tensorboard script: {}'.format(_tbscript_file_))

        print('-'*_repeat_, '\n:: Executing main routines')

        model, results = main(options=options, dataset=dataset, knn=knn)
        print('-'*_repeat_,"\n Ending execution...\n", '-'*_repeat_)
        print(':: Logs:\n', options.root, '\n','-'*_repeat_)

    except Exception as e:
        import sys, traceback

        traceback.print_exc(file=sys.stdout)