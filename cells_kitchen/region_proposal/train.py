from data_generators import DataGenerator
from keras.models import load_model
import tensorflow as tf
import keras.backend as K
from keras.callbacks import ModelCheckpoint, EarlyStopping, LambdaCallback
import losswise
from losswise.libs import LosswiseKerasCallback
import config as cfg
from datetime import datetime
import os
import pickle
from glob import glob
import models
import utils

if cfg.losswise_api_key:
    losswise.set_api_key(cfg.losswise_api_key)  # set up losswise.com visualization

# create model data generators
train_generator = DataGenerator(cfg.train_datasets, batch_size=cfg.batch_size, subframe_size=cfg.subframe_size,
                                normalize_subframes=cfg.normalize_subframes, epoch_size=cfg.epoch_size//cfg.batch_size,
                                rotation=cfg.aug_rotation, scaling=cfg.aug_scaling)
test_generator = DataGenerator(cfg.test_datasets, batch_size=cfg.batch_size, subframe_size=cfg.subframe_size,
                               normalize_subframes=cfg.normalize_subframes, epoch_size=cfg.epoch_size//cfg.batch_size,
                               rotation=cfg.aug_rotation, scaling=cfg.aug_scaling)

# create model
# model = models.unet(train_generator.shape_X[1:], train_generator.shape_y[-1], filters=cfg.filters)
model = models.unet((None, None, train_generator.shape_X[-1]), train_generator.shape_y[-1], filters=cfg.filters,
                    kernel_initializer='glorot_normal', batch_normalization=cfg.batch_normalization,
                    high_pass_sigma=cfg.high_pass_sigma)


# get predictions for single batch
def save_prediction_imgs(generator, model_in, folder):
    X, y = generator[0]
    y_pred = model_in.predict(X)
    for i in range(X.shape[0]):
        file = os.path.join(folder, 'prediction%i.png' % i)
        utils.save_prediction_img(file, X[i], y[i], y_pred[i], X_contrast=(0, 100))


# train, omg!
if cfg.use_cpu:
    config = tf.ConfigProto(device_count={'GPU': 0})
    sess = tf.Session(config=config)
    K.set_session(sess)

model_folder = datetime.now().strftime('%y%m%d_%H.%M.%S')
# model_folder = 'test'
model_path = os.path.join(cfg.data_dir, 'models', model_folder)
os.makedirs(model_path)
callbacks = [EarlyStopping(patience=cfg.early_stopping, verbose=1), # stop when validation loss stops increasing
             ModelCheckpoint(os.path.join(model_path, '%s.{epoch:02d}-{val_loss:.6f}.hdf5' % model.name), save_best_only=True)]
if cfg.save_predictions_during_training:
    callbacks.append(LambdaCallback(on_epoch_end=lambda epoch, logs: save_prediction_imgs(test_generator, model, model_path)))

if cfg.losswise_api_key:
    callbacks.append(LosswiseKerasCallback(tag='giterdone', display_interval=1))
history = model.fit_generator(generator=train_generator, validation_data=test_generator,
                              epochs=cfg.training_epochs, callbacks=callbacks)

with open(os.path.join(model_path, 'training_history'), 'wb') as training_file:
    pickle.dump(history.history, training_file)

# load best model and delete others
models_to_delete = glob(os.path.join(model_path, '*hdf5'))[:-1]
[os.remove(mod) for mod in iter(models_to_delete)]
model = load_model(glob(os.path.join(model_path, '*.hdf5'))[0])

# generate final predictions
save_prediction_imgs(test_generator, model, model_path)

