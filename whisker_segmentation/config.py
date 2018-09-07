'''
TO DO:
***finish h5 conversion -- pack metadata, etc...
***dlc vs current method comparison, points only
*improve training set, or skip frames with missing labels?
*lock in test, train sets
better way to store metadata - ask chris about this
make faster video writer without saving images
save training history

try normalizing distribution by removing samples rather than sample weighting
data augmentation
try location refinement matrix to bring it back to original resolution
plot rmse as function of whisker angle...
add maxima to prediction images
try sigmoid cross entropy loss to force one whisker per location
extra output to regress onto whisker points
'''

# training settings
dataset_name = 'scaling0.25_tracesTrue_points0_tracefiltering_25_pointfiltering5_imgs9238'
network_structure = 'leap' # leap, hourglass, or stacked_hourglass
use_cpu = False
test_set_portion = .1
lr_init = .001
batch_size = 16
kernel_size = 5
training_epochs = 100
first_layer_filters = 16 # for leap 32 seemed to overfit, 8 seemed to underfit
use_sample_weights = True
sample_weight_lims = [.1, 10]


# prepare_data settings
img_limit = False
whiskers = 4
whisker_traces = False
whisker_points = list(range(8)) # points along the whiskers to locate // [0,7]
trace_filtering = 25 # sigma for whisker trace confidence maps
point_filtering = 5 # sigma for whisker point confidence maps
scaling = 1.0



# make_video and evaluate model settings
model_folder = '180826_19.08.52'
vid_name = 'heldout_mice_mpeg4.mkv'