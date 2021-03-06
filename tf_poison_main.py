#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Oct  7 10:53:48 2018

@author: jiajingnan
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import time
import tensorflow as tf
import numpy as np
import csv
import copy
import cv2
# local python package
import deep_cnn
import input
import metrics
import utils

import argparse
import math
import random
import matplotlib.pyplot as plt


parser = argparse.ArgumentParser()
parser.add_argument("power", help="display power", type=float)
parser.add_argument("ratio", help="display ratio", type=float)
# parser.add_argument("direction", help="displaydirection", type=int)
parser.add_argument("sort", help="display sort", type=int)
# parser.add_argument("cover_power", help="display cover_power", type=float)
parser.add_argument("simlarity_of_x", help="display simlarity_of_x", type=int)

parser.add_argument("block_flag", help="display block_flag", type=int)
parser.add_argument("top_nn", help="display the top_nn of blocks ", type=int)

args = parser.parse_args()



import os

#os.environ['CUDA_VISIBLE_DEVICES'] = '7'

tf.flags.DEFINE_string('dataset', 'cifar10', 'The name of the dataset to use')
tf.flags.DEFINE_integer('nb_labels', 10, 'Number of output classes')
tf.flags.DEFINE_string('data_dir', '../data_dir', 'Temporary storage')
tf.flags.DEFINE_string('train_dir', '../train_dir', 'Where model ckpt are saved')
tf.flags.DEFINE_integer('max_steps', 7000, 'Number of training steps to run.')
tf.flags.DEFINE_boolean('deeper', False, 'Activate deeper CNN model')
tf.flags.DEFINE_float('water_power', args.power, 'water_print_power')
tf.flags.DEFINE_float('changed_ratio', args.ratio, 'changed_dataset_ratio')
tf.flags.DEFINE_string('P_per_class', '../records/precision_per_class.txt', '../precision_per_class.txt')
tf.flags.DEFINE_string('P_all_classes', '../records/precision_all_class.txt', '../precision_all_class.txt')

tf.flags.DEFINE_string('changed_data_label', '../records/changed_data_label.txt', '../changed_data_label.txt')


# tf.flags.DEFINE_string('P_all_classes','../precision_all_class.txt','../precision_all_class.txt')
tf.flags.DEFINE_integer('target_class', 4, 'Target class')
tf.flags.DEFINE_string('image_save_path', '../image_save', 'save images')
tf.flags.DEFINE_string('labels_changed_data_before', '../records/labels_changed_data_before.txt',
                       'labels_changed_data_before')
tf.flags.DEFINE_string('path_X_preds_label', '../records/preds_in_class.txt', '')
tf.flags.DEFINE_integer('nb_teachers', 6, 'Number of training steps to run.')
tf.flags.DEFINE_float('changed_area', '0.1', '')

tf.flags.DEFINE_string('my_records_each', '../records/my_records_each.txt', 'my_records_each')
tf.flags.DEFINE_string('my_records_all', '../records/my_records_all.txt', 'my_records_all')
# tf.flags.DEFINE_integer('direction', args.direction, 'direction')
tf.flags.DEFINE_integer('sort', args.sort, 'sort')
# tf.flags.DEFINE_float('cover_power', args.cover_power, 'cover_power')
tf.flags.DEFINE_integer('top_nn', args.top_nn, 'top_nn')
tf.flags.DEFINE_integer('simi', args.simlarity_of_x, 'simi')
tf.flags.DEFINE_integer('block_flag', args.block_flag, 'block_flag')
FLAGS = tf.flags.FLAGS
tran =0


def dividing_line():  # 5个文件。
    file_path_list = ['../label_change_jilu.txt', FLAGS.P_per_class,FLAGS.P_all_classes,'../records/success_change_ratio.txt',
                      FLAGS.labels_changed_data_before,'../records/my_records_all.txt', '../records/my_records_each.txt']
    
    for i in file_path_list:
        with open(i,'a+') as f:
            f.write('\n-------' + str(FLAGS.dataset) + 
                    '\n--water_power: ' + str(FLAGS.water_power) + 
                    '\n--changed_ratio: ' + str(FLAGS.changed_ratio) + 
                    '\n--simi: ' + str(FLAGS.simi) + 
                    '\n--sort: '  + str(FLAGS.sort) + 
                    '\n--block_flag: ' + str(FLAGS.block_flag) +
                    '\n------')
    return True
            
def start_train_data(train_data, train_labels, test_data, test_labels, ckpt_path, ckpt_path_final):  #
    assert deep_cnn.train(train_data, train_labels, ckpt_path)
    preds_tr = deep_cnn.softmax_preds(train_data, ckpt_path_final)  # 得到概率向量
    preds_ts = deep_cnn.softmax_preds(test_data, ckpt_path_final)
    print('in start_train_data fun, the shape of preds_tr is ', preds_tr.shape)
    ppc_train = utils.print_preds_per_class(preds_tr, train_labels, 
                                      ppc_file_path=FLAGS.P_per_class,
                                      pac_file_path=FLAGS.P_all_classes)  # 一个list，10维
    ppc_test = utils.print_preds_per_class(preds_ts, test_labels)  # 全体测试数据的概率向量送入函数，打印出来。计算 每一类 的正确率

    precision_ts = metrics.accuracy(preds_ts, test_labels)  # 算10类的总的正确率
    precision_tr = metrics.accuracy(preds_tr, train_labels)
    print('precision_tr:', precision_tr, 'precision_ts:', precision_ts)
    # 已经包括了训练和预测和输出结果
    return precision_tr, precision_ts, ppc_train, ppc_test, preds_tr


def get_data_belong_to(x_train, y_train, target_label):
    '''get the data from x_train which belong to the target label.
    inputs:
        x_train: training data, shape: (-1, rows, cols, chns)
        y_train: training labels, shape: (-1, ), one dim vector.
        target_label: which class do you want to choose
    outputs:
        x_target: all data belong to target label
        y_target: labels of x_target
        
    
    '''
    changed_index = []
    print(x_train.shape[0])
    for j in range(x_train.shape[0]): 
        if y_train[j] == target_label:
            changed_index.append(j)
            #print('j',j)
    x_target = x_train[changed_index] # changed_data.shape[0] == 5000
    y_target = y_train[changed_index]
    
    return x_target, y_target



def get_bigger_half(mat, saved_pixel_ratio):
    '''get a mat which contains a batch of biggest pixls of mat.
    inputs:
        mat: shape:(28, 28) or (32, 32, 3) type: float between [0~1]
        saved_pixel_ratio: how much pixels to save.
    outputs:
        mat: shifted mat.
    '''
        
    # next 4 lines is to get the threshold of mat
    mat_flatten = np.reshape(mat, (-1, ))
    idx = np.argsort(-mat_flatten)  # Descending order by np.argsort(-x)
    sorted_flatten = mat_flatten[idx]  # or sorted_flatten = np.sort(mat_flatten)
    threshold = sorted_flatten[int(len(idx) * saved_pixel_ratio)]

    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            for k in range(mat.shape[2]):
                if mat[i,j,k] < threshold:
                    mat[i,j,k]=0
                else:
                    mat[i,j,k]=1
                    
    return mat


def get_data_by_add_x_directly(nb_repeat, x, y, x_train, y_train):
    '''get the train data and labels by add x of nb_repeat directly.
    Args:
        nb_repeat: number of times that x repeats. type: integer.
        x: 3D or 4D array. 
        y: the target label of x. type: integer or float.
        x_train: original train data.
        y_train: original train labels.
        
    Returns:
        new_x_train: new x_train with nb_repeat x.
        new_y_train: new y_train with nb_repeat target labels.
    '''
    if len(x.shape)==3:  # shift x to 4D
        x = np.expand_dims(x, 0)
    
    xs = np.repeat(x, nb_repeat)
    ys = np.repeat(y, nb_repeat).astype(np.int32)  # shift to np.int32 before train
    
    new_x_train = np.vstack((x_train, xs))
    new_y_train = np.hstack((y_train, ys))
    
    np.random.seed(10)
    np.random.shuffle(new_train_data)
    np.random.seed(10)
    np.random.shuffle(new_train_labels)
    
    return new_x_train, new_y_train
         

def get_nns_of_x(x, other_data, other_labels, ckpt_path_final):
    '''get the similar order (from small to big).
    
    args:
        x: a single data. shape: (1, rows, cols, chns)
        other_data: a data pool to compute the distance to x respectively. shape: (-1, rows, cols, chns)
        ckpt_path_final: where pre-trained model is saved.
    
    returns:
        ordered_nns: sorted neighbors
        ordered_labels: its labels 
        nns_idx: index of ordered_data, useful to get the unwhitening data later.
    '''

    x_preds = deep_cnn.softmax_preds(x, ckpt_path_final) # compute preds, deep_cnn.softmax_preds could be fed  one data now
    other_data_preds = deep_cnn.softmax_preds(other_data, ckpt_path_final)

    distances = np.zeros(len(other_data_preds))

    for j in range(len(other_data)):
        tem = x_preds - other_data_preds[j]
        # use which distance?!! here use L2 norm firstly
        distances[j] = np.linalg.norm(tem)
        # distance_X_tr_target[i, j] = np.sqrt(np.square(tem[FLAGS.target_class]) + np.square(tem[X_label[i]]))

    # sort(from small to large)
    nns_idx = np.argsort(distances)  # argsort every rows
    np.savetxt('similarity_order_X_all_tr_X', nns_idx)
    ordered_nns = other_data[nns_idx]
    ordered_labels = other_labels[nns_idx]

    return ordered_nns, ordered_labels, nns_idx

# =============================================================================
# def get_tr_data_watermark(changed_data, x, power=FLAGS.water_power):
#     '''get training data by watermark.
#     Args:
#         changed_data: 
#         x: watermark
#         power: howe much does watermark add.
#     Returns:
#         changed_data_after: the data after add watermark
# 
#     '''
#     print('preparing water print data ....please wait...')
#     changed_data_cp = copy.deepcopy(changed_data)
#     tr_min = changed_data_cp.min()
#     tr_max = changed_data_cp.max()
#     x_powered = x * power
#     
#     changed_data_cp *= (1 - power)
#     changed_data_after = [g + x_powered for g in changed_data_cp ]
#     changed_data_after = np.clip(changed_data_cp, tr_min, tr_max)
#     
#     return changed_data_after
# 
# =============================================================================



        

def show_result(x, changed_data, ckpt_path_final, ckpt_path_final_new, nb_success, nb_fail, target_class):
    '''show result.
    Args:
        x: attack sample.
        changed_data: those data in x_train which need to changed.
        ckpt_path_final: where old model saved.
        ckpt_path_final_new:where new model saved.
    Returns:
        nb_success: successful times.
    '''

    x_label_before = np.argmax(deep_cnn.softmax_preds(x, ckpt_path_final))
    changed_labels_before = np.argmax(deep_cnn.softmax_preds(changed_data, ckpt_path_final), axis=1)

    x_labels_after = np.argmax(deep_cnn.softmax_preds(x, ckpt_path_final_new))
    changed_labels_after = np.argmax(deep_cnn.softmax_preds(changed_data, ckpt_path_final_new), axis=1)

    print('\nold_label_of_x0: ', x_label_before,
          '\nnew_label_of_x0: ', x_labels_after,
          '\nold_label_of_changed_data: ', changed_labels_before[:5], # see whether changed data is misclassified by old model
          '\nnew_label_of_changed_data: ', changed_labels_after[:5])
    
    if x_labels_after == target_class:
        print('successful!!!')
        nb_success += 1
        
    else:
        print('failed......')
        nb_fail +=1
    print('number of x0 successful:', nb_success)
    print('number of x0 failed:', nb_fail)
    
    return nb_success, nb_fail

def get_tr_data_watermark(train_data, train_labels, watermark, target_label, sml=False, 
                            ckpt_path_final, cgd_ratio=FLAGS.changed_ratio, power=FLAGS.water_power):
    '''get the train_data by watermark.
    Args:
        train_data: train data 
        train_labels: train labels.
        watermark: what to add to training data
        target_label: target label
        sml: dose similar order?
        ckpt_path_final: where does model save.
        cgd_ratio: changed ratio, how many data do we changed?
        power: water power, how much water do we add?
    Returns:
        train_data_cp: all training data after add water into some data.
        changed_data: changed training data
    
    
    '''
    print('preparing water print data ....please wait...')
    train_data_cp = copy.deepcopy(train_data)
    tr_min = train_data_cp.min()
    tr_max = train_data_cp.max()
    x_print_water = x * FLAGS.water_power
    #  x_print_water[:,:16,:] = 0
    #  x_print_water[:,20:,:] = 0
    changed_index = []
    for j in range(int(len(train_data))):
        if train_labels[j] == FLAGS.target_class:
            changed_index.append(j)
            
    changed_data = train_data_cp[changed_index]
    changed_labels = train_labels[changed_index]
    
    if sml==True:
        nns_tuple = get_nns_of_x(x, 
                                 other_data=changed_data,
                                 other_labels=changed_labels,
                                 ckpt_path_final)
        _, __, changed_index = nns_tuple
        
    changed_index = changed_index[0: len(changed_index) * cgd_ratio]
   
    train_data_cp[changed_index] *= (1 - power)
    train_data_cp[changed_index] = [g + x_print_water for g in train_data_cp[changed_index]] 
    train_data_cp[changed_index] = np.clip(train_data_cp[changed_index], tr_min, tr_max)
    changed_data = train_data_cp[changed_index]
    
    return train_data_cp, changed_data

def main(argv=None):  # pylint: disable=unused-argument
    
    # create dir used in this project
    dir_path_list = [FLAGS.data_dir, FLAGS.train_dir, FLAGS.image_dir]
    for i in dir_path_list:
        assert input.create_dir_if_needed(i)
        
    # create log files and add dividing line 
    assert dividing_line()

    train_data, train_labels, test_data, test_labels = utils.ld_dataset(FLAGS.dataset, whitening=True)

    ckpt_dir = FLAGS.train_dir + '/' + str(FLAGS.dataset) + '/'
    
    ckpt_path =  ckpt_dir + str(number) + 'model.ckpt'
    ckpt_path_final = ckpt_path + '-' + str(FLAGS.max_steps - 1)
    

    
    
    train_tuple = start_train_data(train_data, train_labels, test_data, test_labels, ckpt_path, ckpt_path_final)
    precision_tr, precision_ts, ppc_train, ppc_test, preds_tr = train_tuple  # 数据没水印之前，要训练一下。然后存一下。知道正确率。（只用训练一次）


    nb_success, nb_fail = 0, 0
    
    for number in range(50):
        print('================current num: ', number)

        if test_labels[number] == FLAGS.target_class:
            continue

        new_ckpt_path = ckpt_dir = 'model_new.ckpt'
        new_ckpt_path_final = new_ckpt_path + '-' + str(FLAGS.max_steps - 1)
        
        perfect_path = ckpt_dir + str(number) + 'model_perfect.ckpt'
        perfect_path_final = perfect_path + '-' + str(FLAGS.max_steps - 1)
        

        x = test_data[number]
        y = test_labels[number]
        
        directly_add_x0 = False
        if directly_add_x0:  # directly add x0 to training data
            x_train, y_train = get_tr_data_by_add_x_directly(nb_repeat=128, 
                                                          x=x,
                                                          y=FLAGS.target_class,
                                                          x_train=x_train,
                                                          y_train=y_train)
            train_tuple = start_train_data(x_train, y_train, test_data, test_labels, perfect_path, perfect_path_final)
            
        else:  # add watermark
            watermark = x
            

            
            if watermark_x_grads:  # gradients as watermark from perfect_path_final
                grads_tuple= deep_cnn.get_gradient_of_x0(x, 
                                                         perfect_path_final, 
                                                         number,
                                                         test_labels[number], 
                                                         new=True)  
                grads_mat, grads_mat_plus, grads_mat_show  = grads_tuple
                watermark = grads_mat
                
    
            # get new training data
            new_data_tuple = get_tr_data_watermark(train_data, 
                                                   train_labels,
                                                   watermark, 
                                                   target_label, 
                                                   sml=False, 
                                                   ckpt_path_final, 
                                                   cgd_ratio=FLAGS.changed_ratio, 
                                                   power=FLAGS.water_power)
            train_data_new, changed_data = new_data_tuple
            # train with new data
            train_tuple = start_train_data(train_data, train_labels, test_data, test_labels, ckpt_path, ckpt_path_final)
            
        precision_tr, precision_ts, ppc_train, ppc_test, preds_tr = train_tuple 
        
        # show result
        nb_success, nb_fail = show_result(x0, 
                                          changed_data, 
                                          ckpt_path_final, 
                                          ckpt_path_final_new, 
                                          nb_success, 
                                          nb_fail,
                                          target_class=Flags.target_class)
        
        
    return True
            
                



if __name__ == '__main__':
    tf.app.run()
