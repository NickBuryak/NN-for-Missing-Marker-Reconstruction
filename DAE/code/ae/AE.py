from __future__ import division
from __future__ import print_function

import tensorflow as tf
import numpy as np
from utils.flags import FLAGS
import random


class AutoEncoder(object):
  """Generic denoising autoencoder (AE).

  We use denoising AE: for the input noise is injected and the nextwork tries to recover original data
  More detail can be founded in the original paper: http://www.jmlr.org/papers/volume11/vincent10a/vincent10a.pdf

  It is am empty class
  to be parent for the Flat and Hierarchical AE.
  (Hierarchical AE has been removed from the repository, because it was not used in the paper)
  """
  _weights_str = "weights{0}"
  _biases_str = "biases{0}"

  def __init__(self, num_hidden_layers, batch_size, sequence_length,  sess, data_info):
    """Autoencoder initializer

    Args:
      num_hidden_layers:   number of hidden layers
      batch_size:          batch size
      sequence_length:     length of the sequence which will be feeded into LSTM as once
      sess:                tensorflow session object to use
    """

    self.__num_hidden_layers = num_hidden_layers
    self.__batch_size = batch_size
    self.__sequence_length = sequence_length

    self.__variables = {}
    self.__sess = sess

    self.__scaling_factor = 0.1
    self.__default_value = FLAGS.defaul_value

    self.__max_val = data_info._max_val # maximal value in the dataset (used for scaling it to interval [-1,1] and back)

    #################### Add the DATASETS to the GRAPH ###############3

    #### 1 - TRAIN ###
    self._train_data_initializer = tf.placeholder(dtype=tf.float32, shape=data_info._train_shape)  # 1033 at home
    self._train_data = tf.Variable(self._train_data_initializer, trainable=False, collections=[],
                                   name='Train_data')
    if (FLAGS.Layer_wise_Pretraining):  # Have more epochs: also for the pretraining
        train_frames = tf.train.slice_input_producer([self._train_data],
                                                     num_epochs=FLAGS.training_epochs + FLAGS.num_hidden_layers * FLAGS.pretraining_epochs)
    else:
        train_frames = tf.train.slice_input_producer([self._train_data], num_epochs=FLAGS.training_epochs)
    self._train_batch = tf.train.shuffle_batch(train_frames, batch_size=FLAGS.batch_size, capacity=5000,
                                         min_after_dequeue=1000, name='Train_batch')

    #### 2 - VALIDATE, can be used as TEST ###
    # (When we are optimizing hyper-parameters, this dataset stores as a validation dataset,
    #  when we are testing the system, this dataset stores a test dataset )
    self._valid_data_initializer = tf.placeholder(dtype=tf.float32, shape=data_info._eval_shape)  # 1033 at home
    self._valid_data = tf.Variable(self._valid_data_initializer, trainable=False, collections=[],
                                   name='Valid_data')
    valid_frames = tf.train.slice_input_producer([self._valid_data], num_epochs=FLAGS.training_epochs)
    self._valid_batch = tf.train.shuffle_batch(valid_frames, batch_size=FLAGS.batch_size, capacity=5000,
                                         min_after_dequeue=1000, name='Valid_batch')

  def construct_graph(self, input_seq_pl, dropout, test=False, just_middle = False):

          """Get the output of the autoencoder

          This is a dummy function, which has to be defined in each specific class, which inherits class AE

          Args:
            input_seq_pl:     tf placeholder for ae input data of size [batch_size, sequence_length, DoF]
            dropout:          how much of the input neurons will be activated, value in [0,1]
            just_middle :     will indicate if we want to extract only the middle layer of the network
          """

          return input_seq_pl

  def binary_random_matrix_generator(self, train_flag):
      """ Generate a binary matrix with random values: 0s for missign markers and 1s otherwise
          In the master branch we have experiments with one or two limbs missing,
          so each sequence have a limb or two missing for all the time-steps
          Different sequences may have different limb missing

        Args:
          train_flag:  indicator if we are in the training or testing phase
        Returns:
          mask : binary matrix to be multiplied on input in order to simulate missing markers
      """

      tensor_size = [FLAGS.batch_size, FLAGS.chunk_length, FLAGS.frame_size * FLAGS.amount_of_frames_as_input]

      r_arm = np.array([10, 11, 12, 13, 14, 15])
      l_arm = np.array([16, 17, 18, 19, 20, 21])
      r_leg = np.array([22, 23, 24, 25, 26])
      l_leg = np.array([27, 28, 29, 30, 31])

      two_arms = np.array([10, 11, 12, 13, 14, 21])
      
      if(train_flag):
          # Define all the body parts
          body_parts = [r_arm, l_arm, r_leg, l_leg] # two_arms could be included here to improve performance for this scenario a bit
      else:
          # Define just one body part
          body_parts = [r_arm]

      # initialize mask
      mask = np.ones(tensor_size)

      # Generate missing markers matrix for each sequence in the batch
      for sequence in range(FLAGS.batch_size):

          # Choose a random body part
          missing_body_part = random.choice(body_parts)

          # In order to remove missing data,
          # we slice the data into the parts, which are before and after missing part(s)
          prev_data = np.ones([FLAGS.chunk_length, missing_body_part[0]*3] )
          missing_data = np.zeros([FLAGS.chunk_length, (missing_body_part[-1] + 1 - missing_body_part[0])*3 ])

          right_part = False # weather we are missing both right arm and leg
          
          if(right_part and not train_flag): #could be replaced by missing_body_part[0]==10 to remove the whole right part during the training as well

            missing_body_part = r_leg

            # remove right arm
            prev_data_2 = np.ones([FLAGS.chunk_length, missing_body_part[0]*3 - (r_arm[-1]+1)*3] )
            missing_data_2 = np.zeros([FLAGS.chunk_length, (missing_body_part[-1] + 1 - missing_body_part[0])*3 ])

            next_data = np.ones([FLAGS.chunk_length, (FLAGS.frame_size -(1 + missing_body_part[-1]) *3)] )
            mask_for_seq = np.concatenate((prev_data, missing_data,prev_data_2, missing_data_2,next_data), axis = 1)
            
          else:
            next_data = np.ones([FLAGS.chunk_length, (FLAGS.frame_size -(1 + missing_body_part[-1]) *3)] )
            mask_for_seq = np.concatenate((prev_data, missing_data,next_data), axis = 1)

          # copy the mask for all the frames, if we have a few as input
          if (FLAGS.amount_of_frames_as_input > 1):
              mask_for_seq = np.tile(mask_for_seq, (1,FLAGS.amount_of_frames_as_input))

          # Add this raw to the binary mask
          mask[sequence] = mask_for_seq

      return mask


  @property
  def num_hidden_layers(self):
    return self.__num_hidden_layers

  @property
  def batch_size(self):
    return self.__batch_size

  @property
  def scaling_factor(self):
      return self.__scaling_factor

  @property
  def default_value(self):
      return self.__default_value

  @property
  def sequence_length(self):
    return self.__sequence_length

  @property
  def session(self):
    return self.__sess

  @property
  def max_val(self):
      return self.__max_val


  @staticmethod
  def _activate(x, w, b, transpose_w=False):
    y = tf.tanh(tf.nn.bias_add(tf.matmul(x, w, transpose_b=transpose_w), b)) # was sigmoid before
    return y


def simulate_missing_markets(input_position, mask, const):
    """ Simulate missing markers, by multiplying input on the binary matrix 'mask'

      Args:
        input_position: full body position
        mask:           binary matrix of missing values
        const:          constant to put in place of missing markers
      Returns:
        output :        position, where some markers were replaced by a contrant 'const'
    """

    output = tf.multiply(input_position, mask)

    if const == 0:
        return output
    else:
        default_values = tf.multiply(1-mask, const)
        output = tf.add(output, default_values, 'Simulate_missing_markers_as_' + str(const))
        return output

def use_existing_markers(input, result, mask, const):
    """ We can use the information we have in place of the markers we know instead of the output of the network

       Args:
         input:  the data we have
         result: the output of the network
         mask:   the binary matrix of missing markers
       Returns:
         output : the new body position, which takes the input into account
     """

    # Separate the result of the network network

    result_without_markers_we_had = np.multiply(result, 1 - mask)   # new info
    the_marker_we_had = np.multiply(input, mask)                    # what we knew before

    if(const==0):
        output = the_marker_we_had + result_without_markers_we_had
    else:
        # We need first to subtract constant value from the "input"
        original_input = input - tf.multiply(input, 1 - mask)
        # Now we are ready to combine them
        output = original_input + result_without_markers_we_had

    return output

# The following code can be used for  some testing

'''
    random_size = [2,2,2] #[FLAGS.batch_size, FLAGS.chunk_length, int(FLAGS.frame_size / 3)]
    tensor_size = [2,2,6] # [FLAGS.batch_size, FLAGS.chunk_length, FLAGS.frame_size]

    prob_of_missing = 0.2

    data, max_val, mean_pose = read_datasets_from_binary()
    data_info = DataInfo(data.train.sigma, data.train._sequences.shape, data.test._sequences.shape, max_val)
    AE = AutoEncoder(3,16,32,tf.get_default_session(), data_info)

    mask = AE.binary_random_matrix_generator(prob_of_missing)

    input = tf.random_uniform(tensor_size)


    with tf.Session(''):
        input_values = input.eval()

        our_mask = mask.eval()
        #print(input_values, '\n\n\n')

        missing_values = simulate_missing_markets(input_values,our_mask,0).eval()

        result = input.eval()

        result2 = use_existing_markers(missing_values, result, our_mask, 0)

        print(input_values,'\n\n\n')
        print(missing_values,'\n\n\n')
        print('our_mask', our_mask)

        print(result, '\n\n\n')
        print(result2.eval())
'''
