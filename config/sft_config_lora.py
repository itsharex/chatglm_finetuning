# -*- coding: utf-8 -*-
# @Time    : 2023/5/16 10:11

import json
import os

import torch
from transformers import BitsAndBytesConfig

# **************切换 配置文件 修改 config.__init__.py

# 全局变量

global_args = {
    "load_in_8bit": False, # qlora int8
    "load_in_4bit": False, # qlora int4

    # load_in_4bit 量化配置
    "quantization_config": BitsAndBytesConfig(
        load_in_4bit=True,
        llm_int8_threshold=6.0,
        llm_int8_has_fp16_weight=False,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    ),
    "num_layers_freeze": -1, # 非lora,非p-tuning 模式 ， <= config.json num_layers
    "pre_seq_len": None,    #p-tuning-v2 参数 , None 禁用p-tuning-v2
    "prefix_projection": False, #p-tuning-v2 参数
    "num_layers": -1, # 是否使用骨干网络的全部层数 最大1-28， -1 表示全层, 否则只用只用N层
}

if global_args['load_in_4bit'] != True:
    global_args['quantization_config'] = None


lora_info_args = {
    'with_lora': True,  # 是否启用lora模块
    'r': 8,
    'target_modules': ['query_key_value'],
    'target_dtype': None,
    'lora_alpha': 32,
    'lora_dropout': 0.1,
    'bias': 'none',  # Bias type for Lora. Can be 'none', 'all' or 'lora_only'"
    'modules_to_save' : None, # "List of modules apart from LoRA layers to be set as trainable and saved in the final checkpoint. "

}

adalora_info_args = {
    'with_lora': False,  # 是否启用adalora模块
    'r': 8,
    'target_modules': ['query_key_value'],
    'target_dtype': None, #
    'lora_alpha': 32,
    'lora_dropout': 0.1,
    'bias': 'none',  # Bias type for Lora. Can be 'none', 'all' or 'lora_only'"
    'modules_to_save' : None, # "List of modules apart from LoRA layers to be set as trainable and saved in the final checkpoint. "

    'target_r':8, # Target Lora matrix dimension.
    'init_r': 12, #Intial Lora matrix dimension.
    'tinit': 0, #The steps of initial warmup.
    'tfinal': 0, #The steps of final warmup.
    'deltaT': 1, #Step interval of rank allocation.
    'beta1': 0.85, #Hyperparameter of EMA.
    'beta2': 0.85, #Hyperparameter of EMA.
    'orth_reg_weight': 0.5, #The orthogonal regularization coefficient.
    'total_step': None, #The total training steps.
    'rank_pattern': None, #The saved rank pattern.
}

train_info_args = {
    'devices': 1,
    'data_backend': 'record',  #one of record lmdb, 超大数据集可以使用 lmdb , 注 lmdb 存储空间比record大
    'model_type': 'chatglm',
    # 预训练模型路径 , 从0训练，则置空
    'model_name_or_path': '/data/nlp/pre_models/torch/chatglm/chatglm-6b',
    'config_name': '/data/nlp/pre_models/torch/chatglm/chatglm-6b/config.json',
    'tokenizer_name': '/data/nlp/pre_models/torch/chatglm/chatglm-6b',

    # 'model_name_or_path': '/data/nlp/pre_models/torch/chatglm/chatglm-6b-int4',
    # 'config_name': '/data/nlp/pre_models/torch/chatglm/chatglm-6b-int4/config.json',
    # 'tokenizer_name': '/data/nlp/pre_models/torch/chatglm/chatglm-6b-int4',

    # 'model_name_or_path': '/data/nlp/pre_models/torch/chatglm/chatglm-6b-int8',
    # 'config_name': '/data/nlp/pre_models/torch/chatglm/chatglm-6b-int8/config.json',
    # 'tokenizer_name': '/data/nlp/pre_models/torch/chatglm/chatglm-6b-int8',

    'convert_onnx': False, # 转换onnx模型
    'do_train': True,
    'train_file':  [ './data/finetune_train_examples.json'],
    'max_epochs': 20,
    'max_steps': -1,
    'optimizer': 'lion', # one of [lamb,adamw_hf,adamw,adamw_torch,adamw_torch_fused,adamw_torch_xla,adamw_apex_fused,adafactor,adamw_anyprecision,sgd,adagrad,adamw_bnb_8bit,adamw_8bit,lion_8bit,lion_32bit,paged_adamw_32bit,paged_adamw_8bit,paged_lion_32bit,paged_lion_8bit]

    'scheduler_type': 'CAWR', #one of [linear,WarmupCosine,CAWR,CAL,Step,ReduceLROnPlateau, cosine,cosine_with_restarts,polynomial,constant,constant_with_warmup,inverse_sqrt,reduce_lr_on_plateau]
    'scheduler':{'T_mult': 1,
                 'rewarm_epoch_num': 0.5,  # 如果 max_epochs is not None !
                 # 'T_0': 50000,    # 如果 max_epochs is None , 设定步数
                 'verbose': False},

    # 'scheduler_type': 'linear',# one of [linear,WarmupCosine,CAWR,CAL,Step,ReduceLROnPlateau
    # 'scheduler': None,

    # 切换scheduler类型
    # 'scheduler_type': 'WarmupCosine',
    # 'scheduler': None,

    # 'scheduler_type': 'ReduceLROnPlateau',
    # 'scheduler': None,

    # 'scheduler_type': 'Step',
    # 'scheduler':{ 'decay_rate': 0.999,'decay_steps': 100,'verbose': True},

    # 'scheduler_type': 'CAWR',
    # 'scheduler':{'T_mult': 1, 'rewarm_epoch_num': 2, 'verbose': True},

    # 'scheduler_type': 'CAL',
    # 'scheduler': {'rewarm_epoch_num': 2,'verbose': True},


    'optimizer_betas': (0.9, 0.999),
    'train_batch_size': 4,
    'eval_batch_size': 2,
    'test_batch_size': 2,
    'learning_rate': 2e-5,  #
    'adam_epsilon': 1e-8,
    'gradient_accumulation_steps': 1,
    'max_grad_norm': 1.0,
    'weight_decay': 0,
    'warmup_steps': 0,
    'output_dir': './output',
    'max_seq_length': 1024, # 如果资源充足，推荐长度2048 与官方保持一致
    'max_target_length': 100,  # 预测最大长度, 保留字段
    'use_fast_tokenizer': False,
    'do_lower_case': False,

    ##############  lora模块
    #注意lora,adalora 和 ptuning-v2 禁止同时使用
   'lora': {**lora_info_args},
   'adalora': {**adalora_info_args},
}


#配置检查


if global_args['load_in_8bit'] == global_args['load_in_4bit'] and global_args['load_in_8bit'] == True:
    raise Exception('load_in_8bit and load_in_4bit only set one at same time!')

if lora_info_args['with_lora'] == adalora_info_args['with_lora'] and lora_info_args['with_lora'] == True:
    raise Exception('lora and adalora can set one at same time !')




