import numpy as np
import os
import cPickle
import sys
import scipy.interpolate
import pylab
import tables
import scipy.ndimage
import itertools
from sklearn.metrics import f1_score
from sklearn import cross_validation
from sklearn.grid_search import GridSearchCV
from sklearn.svm import LinearSVC
from sklearn.ensemble import GradientBoostingClassifier
from sklearn import preprocessing
from sklearn.feature_selection import SelectPercentile, f_classif
from sklearn.pipeline import Pipeline
from collections import defaultdict

bad_adjectives = ['unpleasant', 'sticky', 'nice']

adjectives=['absorbent',
            'bumpy',
            'compressible',
            'cool',
            'crinkly',
            'fuzzy',
            #'gritty',
            'hairy',
            'hard',
            'metallic',
            'nice',
            'porous',
            'rough',
            'scratchy',
            'slippery',
            'smooth',
            'soft',
            'solid',
            'springy',
            'squishy',
            'sticky',
            'textured',
            'thick',
            'thin',
            'unpleasant']


def filter_adjectives(a_dict):
    return dict((adj, v) for adj, v in a_dict.iteritems() if adj not in bad_adjectives)

phases = ["SQUEEZE_SET_PRESSURE_SLOW", "HOLD_FOR_10_SECONDS", "SLIDE_5CM", "MOVE_DOWN_5CM"]
sensors = ["electrodes", "pac", "pdc", "tac"]
static_features = ["pdc_rise_count", "pdc_area", "pdc_max", "pac_energy", "pac_sc", "pac_sv", "pac_ss", "pac_sk", "tac_area", "tdc_exp_fit", "gripper_min", "gripper_mean", "transform_distance", "electrode_polyfit"]
static_channels = ["electrodes", "pac", "pdc", "tac", "tdc", "gripper_aperture","transforms"]

human_scores = {'absorbent': 0.63341,
                'bumpy': 0.54907,
                'compressible': 0.74361,
                'cool': 0.54737,
                'crinkly': 0.52400,
                'fuzzy': 0.63816,
                'hairy': 0.66455,
                'hard': 0.83411,
                'metallic': 0.68075,
                'nice': 0.20490,
                'porous': 0.58147,
                'rough': 0.70126,
                'scratchy': 0.65699,
                'slippery': 0.57429,
                'smooth': 0.84894,
                'soft': 0.76097,
                'solid': 0.87022,
                'springy': 0.49089,
                'squishy': 0.79420,
                'sticky': 0.80000,
                'textured': 0.67367,
                'thick': 0.49090,
                'thin' : 0.44744,
                'unpleasant' : 0.68611}

mkl_scores =  {'porous': 0.8695652173913044,
               'hard': 0.846153846153846,
               'sticky': 1.0,
               'springy': 0.9523809523809523,
               'squishy': 0.9206349206349207,
               'rough': 0.6363636363636365,
               'thick': 0.6111111111111112,
               'metallic': 0.9473684210526316,
               'unpleasant': 1.0,
               'absorbent': 0.9523809523809523,
               'nice': 1.0,
               'hairy': 0.7499999999999999,
               'compressible': 0.9,
               'textured': 0.20000000000000004,
               'bumpy': 0.888888888888889,
               'fuzzy': 0.4,
               'scratchy': 0,
               'cool': 0.8235294117647058,
               'solid': 1.0,
               'crinkly': 1.0,
               'smooth': 0.7142857142857143,
               'slippery': 0.8695652173913044,
               'thin': 1.0,
               'soft': 0.8095238095238095}

train_pos_examples = {'porous': 6,
                      'hard': 20,
                      'sticky': 0.5,
                      'springy': 6,
                      'squishy': 21,
                      'rough': 9,
                      'thick': 9,
                      'metallic': 2,
                      'unpleasant': 0.5,
                      'absorbent': 9,
                      'nice': 0.5,
                      'hairy': 4,
                      'compressible': 20,
                      'textured': 16,
                      'bumpy': 2,
                      'fuzzy': 6,
                      'scratchy': 5,
                      'cool': 8,
                      'solid': 22,
                      'crinkly': 1,
                      'smooth': 25,
                      'slippery': 8,
                      'thin': 1,
                      'soft': 13}

alpha_unstandard_mkl =  {'porous': 0, 'hard': 0,
                         'sticky': 0, 'springy': 0.3, 'squishy': 0, 'rough': 0.1, 'thick': 0.1,
                         'metallic': 0, 'unpleasant': 0, 'absorbent': 0.3, 'nice': 0,
                         'hairy': 0.5, 'compressible': 0, 'textured': 0.3,
                         'bumpy': 0.1, 'fuzzy': 0.1, 'scratchy': 0.3, 'cool': 0.1,
                         'solid': 0.7, 'crinkly': 0, 'smooth': 0, 'slippery': 0,
                         'thin': 0, 'soft': 0}

sorted_adjectives = sorted(adjectives,
                           key=lambda x:train_pos_examples[x],
                           reverse=True)

def get_ordered_values(a_dict):
    return [a_dict[k] for k in sorted_adjectives]

def smooth(x,window_len=11,window='hanning'):
    """smooth the data using a window with requested size.

    This method is based on the convolution of a scaled window with the signal.
    The signal is prepared by introducing reflected copies of the signal 
    (with the window size) in both ends so that transient parts are minimized
    in the begining and end part of the output signal.

    input:
        x: the input signal 
        window_len: the dimension of the smoothing window; should be an odd integer
        window: the type of window from 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'
            flat window will produce a moving average smoothing.

    output:
        the smoothed signal

    example:

    t=linspace(-2,2,0.1)
    x=sin(t)+randn(len(t))*0.1
    y=smooth(x)

    see also: 

    numpy.hanning, numpy.hamming, numpy.bartlett, numpy.blackman, numpy.convolve
    scipy.signal.lfilter

    TODO: the window parameter could be the window itself if an array instead of a string
    NOTE: length(output) != length(input), to correct this: return y[(window_len/2-1):-(window_len/2)] instead of just y.
    """

    if x.ndim != 1:
        raise ValueError, "smooth only accepts 1 dimension arrays."

    if x.size < window_len:
        raise ValueError, "Input vector needs to be bigger than window size."


    if window_len<3:
        return x


    if not window in ['flat', 'hanning', 'hamming', 'bartlett', 'blackman']:
        raise ValueError, "Window is on of 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'"


    s=np.r_[x[window_len-1:0:-1],x,x[-1:-window_len:-1]]
    #print(len(s))
    if window == 'flat': #moving average
        w=np.ones(window_len,'d')
    else:
        w=eval('np.'+window+'(window_len)')

    y=np.convolve(w/w.sum(),s,mode='valid')
    return y

def nan_helper(y):
    """Helper to handle indices and logical indices of NaNs.

    Input:
        - y, 1d numpy array with possible NaNs
    Output:
        - nans, logical indices of NaNs
        - index, a function, with signature indices= index(logical_indices),
          to convert logical indices of NaNs to 'equivalent' indices
    Example:
        >>> # linear interpolation of NaNs
        >>> nans, x= nan_helper(y)
        >>> y[nans]= np.interp(x(nans), x(~nans), y[~nans])
    """

    return np.isnan(y), lambda z: z.nonzero()[0]

def plot_database(database):
    """

    database: a dictionary as saved by aggregate_data
    """
    features = database.keys()
    sensors = database[features[0]].keys()

    rows = int(pylab.sqrt(len(sensors)))
    cols = len(sensors) / rows + 1

    #hold(True)
    for feature in features:
        pylab.figure()
        pylab.suptitle(feature, fontsize=12)
        for i, sensor in enumerate(sensors):
            pylab.subplot(rows, cols, i)
            data = database[feature][sensor]
            [pylab.plot(x[:,0]) for x in data]
            pylab.title(sensor)

def resample(a, dimensions, method='linear', center=False, minusone=False):
    """Arbitrary resampling of source array to new dimension sizes.
    Currently only supports maintaining the same number of dimensions.
    To use 1-D arrays, first promote them to shape (x,1).

    Uses the same parameters and creates the same co-ordinate lookup points
    as IDL''s congrid routine, which apparently originally came from a VAX/VMS
    routine of the same name.

    method:
    neighbour - closest value from original data
    nearest and linear - uses n x 1-D interpolations using
                         scipy.interpolate.interp1d
    (see Numerical Recipes for validity of use of n 1-D interpolations)
    spline - uses ndimage.map_coordinates

    centre:
    True - interpolation points are at the centres of the bins
    False - points are at the front edge of the bin

    minusone:
    For example- inarray.shape = (i,j) & new dimensions = (x,y)
    False - inarray is resampled by factors of (i/x) * (j/y)
    True - inarray is resampled by(i-1)/(x-1) * (j-1)/(y-1)
    This prevents extrapolation one element beyond bounds of input array.

    -----------
    | http://www.scipy.org/Cookbook/Rebinning (Original source, 2011/11/19)
    """
    if a.ndim > 1:
        if dimensions[1] != a.shape[1]:
            raise ValueError("The new shape should keep the number of columns")

        ret = [_resample(col, (dimensions[0],), method, center, minusone)
               for col in a.T]
        return np.array(ret).T
    else:
        return _resample(a, dimensions, method, center, minusone)


def _resample(a, dimensions, method='linear', center=False, minusone=False):
    orig_data = np.asarray(a)

    # Verify that number dimensions requested matches original shape
    if len(dimensions) != a.ndim:
        raise ValueError("Dimensions are not equal!")

    if not orig_data.dtype in [np.float64, np.float32]:
        orig_data = orig_data.astype(np.float64)

    dimensions = np.asarray(dimensions, dtype=np.float64)
    m1 = np.array(minusone, dtype=np.int64) # array(0) or array(1)
    offset = np.float64(center * 0.5) # float64(0.) or float64(0.5)

    # Resample data
    if method == 'neighbor':
        data = _resample_neighbor(orig_data, dimensions, offset, m1)
    elif method in ['nearest','linear']:
        data = _resample_nearest_linear(orig_data, dimensions, method,
                                        offset, m1)
    elif method == 'spline':
        data = _resample_spline(orig_data, dimensions, offset, m1)
    else:
        raise ValueError("Unknown sampling method")

    return data

def _resample_nearest_linear(orig, dimensions, method, offset, m1):
    """Resample using either linear or nearest interpolation"""


    dimlist = []

    # calculate new dims
    for i in range(orig.ndim):
        base = np.arange(dimensions[i])
        dimlist.append((orig.shape[i] - m1) / (dimensions[i] - m1) *
                       (base + offset) - offset)

    # specify old coordinates
    old_coords = [np.arange(i, dtype=np.float) for i in orig.shape]

    # first interpolation - for ndims = any

    mint = scipy.interpolate.interp1d(old_coords[-1], orig, kind=method)
    new_data = mint(dimlist[-1])

    trorder = [orig.ndim - 1] + range(orig.ndim - 1)
    for i in xrange(orig.ndim - 2, -1, -1):
        new_data = new_data.transpose(trorder)

        mint = scipy.interpolate.interp1d(old_coords[i], new_data,
                                          kind=method)
        new_data = mint(dimlist[i])

    if orig.ndim > 1:
        # need one more transpose to return to original dimensions
        new_data = new_data.transpose(trorder)

    return new_data

def _resample_neighbor(orig, dimensions, offset, m1):
    """Resample using closest-value interpolation"""
    dimlist = []

    for i in xrange(orig.ndim):
        base = np.indices(dimensions)[i]
        dimlist.append((orig.shape[i] - m1) / (dimensions[i] - m1) *
                       (base + offset) - offset)
    cd = np.array(dimlist).round().astype(int)

    return orig[list(cd)]

def _resample_spline(orig, dimensions, offset, m1):
    """Resample using spline-based interpolation"""

    oslices = [slice(0, j) for j in orig.shape]
    old_coords = np.ogrid[oslices] #pylint: disable=W0612
    nslices = [slice(0, j) for j in list(dimensions)]
    newcoords = np.mgrid[nslices]

    newcoords_dims = range(np.rank(newcoords))

    #make first index last
    newcoords_dims.append(newcoords_dims.pop(0))
    newcoords_tr = newcoords.transpose(newcoords_dims) #pylint: disable=W0612

    # makes a view that affects newcoords
    newcoords_tr += offset

    deltas = (np.asarray(orig.shape) - m1) / (dimensions - m1)
    newcoords_tr *= deltas

    newcoords_tr -= offset

    return scipy.ndimage.map_coordinates(orig, newcoords)

def dict_from_h5_group(group, alt_phases = None, alt_sensors = None):
    """
    Creates a dictionary from an h5 group. The dictionary will have fields:
    name: the name of the object
    adjectives: a list of strings
    data: a dictionary with keys being the phases, and values:
          one dictionary for each sensor, where the key is the sensor and the
          value is the data in the sensor
    """
    assert isinstance(group, tables.Group)
    if alt_phases is not None:
        all_phases = alt_phases
    else:
        all_phases = phases
    if alt_sensors is not None:
        all_sensors = alt_sensors
    else:
        all_sensors = sensors

    ret_d = dict()
    try:
        ret_d["adjectives"] = group.adjectives[:]
    except tables.NoSuchNodeError:
        print "WARN: No adjectives in group %s" % group._v_name
        ret_d["adjectives"] = []

    ret_d["name"] = group._v_name
    data = dict()
    ret_d["data"] = data
    for phase in all_phases:
        phase_data = {}
        for sensor in all_sensors:

            #getting the indexes for the phase
            indexed = (group.state.controller_detail_state.read() == phase)

            #finger 0
            finger_0 = group.biotacs.finger_0
            data_0 = getattr(finger_0, sensor).read()
            nrows = data_0.shape[0]
            data_0 = data_0.reshape((nrows,-1))
            data_0 = data_0[indexed, :]

            #finger_1
            finger_1 = group.biotacs.finger_1
            data_1 = getattr(finger_1, sensor).read()
            nrows = data_1.shape[0]
            data_1 = data_1.reshape((nrows,-1))
            data_1 = data_1[indexed, :]        

            phase_data[sensor] = np.hstack((data_0, data_1))
        data[phase] = phase_data

    return ret_d

def is_object(obj_name):
    """Set of hacks to check is a group name is actually an object and not
    some other stuff.
    """
    return (not obj_name._v_name.startswith("adjectives")
            and not obj_name._v_name.startswith("train_test")
            and not obj_name._v_name.startswith("validation")
            )

def iterator_over_object_groups(database, filter_condition = None):
    """Returns an iterator over all the objects (groups) in the h5 database.
    If database is a string it will be interpreted as a filename, otherwise
    as an open pytables file.
    """    
    if type(database) is str:
        database = tables.openFile(database,"r")

    if filter_condition is None:
        filter_condition = is_object

    return (g for g in database.root._v_children.values()
            if filter_condition(g))

def get_item_name(item):
    """
    Extract the item name from a string encoding.

    Example: str = 
    gray_soft_foam_104_01 -> gray_soft_foam
    kitchen_sponge_114_10 -> kitchen_sponge
    """

    if type(item) is tables.Group:
        item = item._v_name

    chars = item.split("_")
    return "_".join(chars[:-2])

def get_item_id(item):
    """ 
    Extract the item id from a string encoding.

    Example: str = 
    gray_soft_foam_104_01 -> gray_soft_foam
    kitchen_sponge_114_10 -> kitchen_sponge
    """
    if type(item) is tables.Group:
        item = item._v_name
    item_id = int(item[-6:-3])
    return item_id

def create_train_test_set(adjective_group, training_ratio):
    """Given an adjective, first groups the objects then splits the
    groups using the training_ratio. Finally returns two lists: 
    one with all the subgroups in the first set, the other with the
    reamining subgrooups.
    """

    train_groups = []
    test_groups = []

    assert isinstance(adjective_group, tables.Group)
    object_names = set(get_item_name(g) for g in adjective_group._v_children)
    object_ids = set(get_item_id(g) for g in adjective_group._v_children)
    if len(object_names) == 1:
        print "Dealing with a unit length"
        half_runs = int(len(adjective_group._v_children.values())/2.0)
        train_groups = adjective_group._v_children.values()[0:half_runs]
        test_groups = adjective_group._v_children.values()[half_runs:]
        return train_groups, test_groups

    train_size = int(training_ratio * len(object_ids))
        
    if train_size == 0:
        train_size = 1;
    if train_size == len(object_ids):
        train_size -= 1

    #training set
    for num in itertools.islice(object_ids, train_size):
        train_groups.extend( g 
                             for (g_num, g) in adjective_group._v_children.iteritems()
                             if num == get_item_id(g_num)
                             )
    #test set
    for num in itertools.islice(object_ids, train_size, len(object_ids)):
        test_groups.extend( g 
                             for (g_num, g) in adjective_group._v_children.iteritems()
                             if num == get_item_id(g_num)
                             )
    assert len(train_groups) > 0
    assert len(test_groups) > 0
    return train_groups, test_groups

def add_train_test_set_to_database(database, training_ratio):
    if type(database) is str:
        database = tables.openFile(database, "r+")

    try:
        if "/train_test_sets" not in database:
            print "Creating group /train_test_sets"
            base_group = database.createGroup("/", "train_test_sets")
        else:
            print "Group /train_test_sets already exists"
            base_group = database.root.train_test_sets

        adjectives_group = database.root.adjectives

        for adjective in adjectives:            
            if adjective in base_group:
                print "%s already exist" % adjective
                continue

            print "\nAdjective: ", adjective

            newg = database.createGroup(base_group, adjective)
            train_group = database.createGroup(newg, "train")
            test_group = database.createGroup(newg, "test")

            #getting train and test lists
            a_group = getattr(adjectives_group, adjective)
            train_list, test_list = create_train_test_set(a_group, training_ratio)

            #creating the hard links
            for g in train_list:
                name = g._v_name
                print "\tTrain link: ", name 
                database.createHardLink(train_group, name, g)
            for g in test_list:
                name = g._v_name
                print "\tTest link: ", name 
                database.createHardLink(test_group, name, g)
    finally:
        print "Flushing..."
        database.flush()

def add_train_test_negative_set_to_database(database, training_ratio):
    if type(database) is str:
        database = tables.openFile(database, "r+")

    try:
        if "/train_test_negative_sets" not in database:
            print "Creating group /train_test_negative_sets"
            base_group = database.createGroup("/", "train_test_negative_sets")
        else:
            print "Group /train_test_negative_sets already exists"
            base_group = database.root.train_test_negative_sets

        adjectives_group = database.root.adjectives_neg

        #import pdb; pdb.set_trace()
        for adjective in adjectives:
            if adjective in base_group:
                print "%s already exist" % adjective
                continue

            print "\nAdjective: ", adjective

            newg = database.createGroup(base_group, adjective)
            train_group = database.createGroup(newg, "train")
            test_group = database.createGroup(newg, "test")

            #getting train and test lists
            a_group = getattr(adjectives_group, adjective)
            train_list, test_list = create_train_test_set(a_group, training_ratio)

            #creating the hard links
            for g in train_list:
                name = g._v_name
                print "\tTrain link: ", name
                database.createHardLink(train_group, name, g)
            for g in test_list:
                name = g._v_name
                print "\tTest link: ", name
                database.createHardLink(test_group, name, g)
    finally:
        print "Flushing..."
        database.flush()

def train_svm_gridsearch(train_X, train_Y,
                         object_ids = None,
                         verbose = 0,
                         n_jobs = 6,
                         score_fun = f1_score,
                         scale = False
                         ):

    '''
    Performs cross validation using grid search 
    '''

    # Setup cross validation
    if (object_ids is None) or (sum(train_Y) <= 10):
        print "Cannot perform leave one out cross validation"
        cv = 5 # 5 fold cross validation
    else: 
        # Leave one object out cross validation
        cv = cross_validation.LeavePLabelOut(object_ids, p=1,indices=True) 

    parameters = {
                  #'C': np.linspace(1,1e6,1000),
                  'C': np.linspace(1,1e6,100),
                  #'C': (1e-3,1e-2,1e-1,1.0, 10, 100, 1000, 1e4, 1e5, 1e6), 
                  'penalty':('l1','l2'),
                  }

    # class weight normalizes the lack of positive examples
    clf = LinearSVC(dual=False,class_weight='auto')

    if scale is True:
        scaler = preprocessing.StandardScaler().fit(train_X)
        train_X = scaler.transform(train_X)
    else:
        scaler = False

    grid = GridSearchCV(clf, parameters, cv=cv,
                        verbose=verbose,
                        n_jobs=n_jobs,
                        score_func=score_fun
                        )

    grid.fit(train_X, train_Y)
    svm_best = grid.best_estimator_

    return svm_best,scaler



def train_given_new_test(test_X, test_Y, 
                         train_X = None, train_Y  = None,
                         all_Cs =  None, 
                         score_fun = None,
                         verbose = True):
   
    ''' 
    Does not perform grid search, only cross validates on error (C)
    Uses test set to cross validate with
    '''

    if train_X is None:
        raise ValueError("No features present, have you run create_features_set?")
    if train_Y is None: 
        raise ValueError("No labels present, have you run create_features_set?")        

    if all_Cs is None:
        all_Cs = np.linspace(1, 1e6, 1000)

    scores = []
    for C in all_Cs:
        clf = LinearSVC(C=C, dual=False)
        clf.fit(train_X, train_Y)
        if score_fun is None:
            score = clf.score(test_X, test_Y)
        else:
            pred_Y = clf.predict(test_X)
            score = score_fun(test_Y, pred_Y)
        scores.append(score)

    best_C = np.argmax(all_Cs)
    svc = LinearSVC(C = best_C, dual = False).fit(train_X, train_Y)
    if verbose:
        if score_fun is None:
            score_training = svc.score(train_X, train_Y)
            score_testing = svc.score(test_X, test_Y)
        else:
            pred_Y = svc.predict(train_X)
            score_training = score_fun(train_Y, pred_Y)

            pred_Y = svc.predict(test_X)
            score_testing = score_fun(test_Y, pred_Y)    

        print "Training score: %f, testing score: %f" %(score_training,
                                                        score_testing)
    return svc


def train_gradient_boost(train_X, train_Y,
                         object_ids = None,
                         score_fun = f1_score,
                         verbose = 0,
                         n_jobs = 6,
                         scale = False
                         ):

    '''
    Performs cross validation using grid search and
    gradient tree boosting
    '''

    # Setup cross validation
    if (object_ids is None) or (sum(train_Y) <= 10):
        print "Cannot perform leave one out cross validation"
        cv = 5 # 10 fold cross validation
    else: 
        # Leave one object out cross validation
        cv = cross_validation.LeavePLabelOut(object_ids, p=1,indices=True) 
    if scale is True:
        scaler = preprocessing.StandardScaler().fit(train_X)
        train_X = scaler.transform(train_X)
    else:
        scaler = False

    parameters = {
                  'n_estimators':[1000],
                  'learn_rate':[1e-1, 1e-2, 1, 1e-3]
                  #'max_depth':[4]
                  }

    print "Beginning Grid Search" 
    grid = GridSearchCV(GradientBoostingClassifier(max_depth=4), 
                        parameters, 
                        score_func=score_fun, 
                        cv=cv, 
                        verbose = verbose, 
                        n_jobs=n_jobs
                        )

    grid.fit(train_X, train_Y)
    svm_best = grid.best_estimator_

    return svm_best, scaler

def train_univariate_selection(train_X, train_Y,
                         object_ids = None,
                         score_fun = f1_score,
                         verbose = 0,
                         n_jobs = 6,
                         scale = False):

    '''
    Cross validates on the best percentage of features to keep
    when doing univariate feature selection
    '''

    # Setup cross validation
    if (object_ids is None) or (sum(train_Y) <= 10):
        print "Cannot perform leave one out cross validation"
        cv = 5 # 10 fold cross validation
    else: 
        # Leave one object out cross validation
        cv = cross_validation.LeavePLabelOut(object_ids, p=1,indices=True) 
    if scale is True:
        scaler = preprocessing.StandardScaler().fit(train_X)
        train_X = scaler.transform(train_X)
    else:
        scaler = False

    univ_select = SelectPercentile(f_classif, percentile=10)
    X_features = univ_select.fit(train_X, train_Y).transform(train_X)
   
    # class weight normalizes the lack of positive examples
    svm = LinearSVC(dual=False,class_weight='auto')
    svm.fit(X_features, train_Y)

    pipeline = Pipeline([("features", univ_select), ("svm", svm)])
   
    param_grid = dict(features__percentile=[20,40,60,80,100],
                      svm__C=np.linspace(1,1e6,20),
                      svm__penalty = ['l1','l2']) 

    grid = GridSearchCV(pipeline, param_grid, cv=cv,
                        verbose=verbose,
                        n_jobs=n_jobs,
                        score_func=score_fun
                        )

    grid.fit(train_X, train_Y)
    svm_best = grid.best_estimator_

    return svm_best, scaler

def load_adjective_phase(directory):

    all_features = defaultdict(dict)

    for f in os.listdir(directory):
        # select pkl files associated with adjective
        if not f.endswith('.pkl'):
            continue
    
        # Load pickle file
        path_name = os.path.join(directory, f)
        with open(path_name, "r") as file_path:
            features = cPickle.load(file_path)

        chars = f.strip(".pkl").split("_")
        chars = chars[2:] #static_feature
        adjective = chars[0] #adjective
        chars = chars[1:] #adjective
        phase = "_".join(chars) # merge together
        all_features[adjective][phase] = features

    return all_features

def get_all_train_test_features(adjective, all_features, train=True):
    """
    Example function on how to access all of the features
    stored in adjective_phase_set
    """

    train_X = []

    if train is True:
        section = 'train'
    else:
        section = 'test'

    for phase in phases:
        train_set = all_features[adjective][phase][section]
        train_X.append(train_set['features'])
        train_Y = train_set['labels']
        object_ids = train_set['object_ids']

    train_X = np.concatenate(train_X, axis=1)

    return (train_X, train_Y, object_ids) 
