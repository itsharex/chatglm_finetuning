# -*- coding: utf-8 -*-
import logging
import os
import torch
from deep_training.data_helper import ModelArguments, DataArguments, TrainingArguments
from deep_training.utils.trainer import ModelCheckpoint, SimpleModelCheckpoint
from lightning import Trainer
from lightning.pytorch.callbacks import LearningRateMonitor
from lightning.pytorch.strategies import DeepSpeedStrategy
from transformers import HfArgumentParser
from data_utils import NN_DataHelper, train_info_args, get_deepspeed_config,global_args
from models import MyTransformer, ChatGLMTokenizer,LoraArguments,ChatGLMConfig, setup_model_profile


class MySimpleModelCheckpoint(SimpleModelCheckpoint):
    def __init__(self, *args, **kwargs):
        super(MySimpleModelCheckpoint, self).__init__(*args, **kwargs)
        lora_args: LoraArguments = self.external_kwargs['lora_args']
        if lora_args:
            self.weight_file = './best_ckpt'
            self.last_weight_file = './last_ckpt'

    def load_model_from_ckpt(self):
        model_args = self.external_kwargs['model_args']
        training_args = self.external_kwargs['training_args']
        lora_args = LoraArguments.from_pretrained(self.last_weight_file)
        pl_module = MyTransformer(lora_args=lora_args,
                              config=config,
                              model_args=model_args,
                              training_args=training_args)


        pl_module.load_sft_weight(self.last_weight_file)
        return pl_module


    def on_save_model(
            self, trainer: "pl.Trainer", pl_module: "pl.LightningModule"
    ) -> None:

        lora_args : LoraArguments =  self.external_kwargs['lora_args']
        # 保存权重
        if lora_args is None:
            super(MySimpleModelCheckpoint, self).on_save_model(trainer, pl_module)
        else:
            #保存最新权重
            logging.info('step {} saving model'.format(trainer.global_step))
            pl_module.backbone.save_pretrained(self.weight_file)

            # monitor_candidates = self._monitor_candidates(trainer)
            # monitor_candidates.update(self.on_get_metric(trainer, pl_module))
            # val = monitor_candidates.get(self.monitor, None)
            # #保存loss最小权重
            # if self.update_best(val):
            #     logging.info('epoch {} ,step {} , save best {}, {}\n'.format(monitor_candidates['epoch'],
            #                                                                  monitor_candidates['step'],
            #                                                                  self.best[self.monitor],
            #                                                                  self.weight_file))
            #     pl_module.backbone.save_pretrained(self.weight_file)
            # #保存最新权重
            # pl_module.backbone.save_pretrained(self.last_weight_file)
            # # # 从最新权重加载模型
            # # pl_module = self.load_model_from_ckpt()



            
if __name__ == '__main__':
    parser = HfArgumentParser((ModelArguments, TrainingArguments, DataArguments, LoraArguments))
    model_args, training_args, data_args, lora_args = parser.parse_dict(train_info_args)
    lora_args = lora_args.config




    #
    setup_model_profile()
    deepspeed_config = get_deepspeed_config()

    # 保存最小loss模型
    if lora_args:
        assert deepspeed_config is None,ValueError('lora mode does not support deepspeed')
        checkpoint_callback = MySimpleModelCheckpoint(
                              # monitor="loss",
                              save_weights_only = True,
                              every_n_epochs = 1,
                              every_n_train_steps=2000 // training_args.gradient_accumulation_steps,
                              #模型参数
                              model_args=model_args,
                              training_args=training_args,
                              lora_args=lora_args,)
    else:
        checkpoint_callback = ModelCheckpoint('./best_ckpt',
                                              # monitor='loss',
                                              save_weights_only=True,
                                              save_last=True,
                                              save_top_k=1,
                                              # every_n_train_steps=1000,
                                              every_n_epochs=1)


    strategy = 'ddp' if torch.cuda.device_count() > 1 else 'auto'
    if deepspeed_config is not None and len(deepspeed_config):
        strategy = DeepSpeedStrategy(config=deepspeed_config,)

    dataHelper = NN_DataHelper(model_args, training_args, data_args)
    config_kwargs = {"pre_seq_len": global_args["pre_seq_len"],
                     "prefix_projection": global_args["pre_seq_len"]}
    if global_args["num_layers"] > 0:
        config_kwargs["num_layers"] = global_args["num_layers"]
    tokenizer, config, _, _ = dataHelper.load_tokenizer_and_config(tokenizer_class_name=ChatGLMTokenizer,config_class_name=ChatGLMConfig,config_kwargs=config_kwargs)
    assert tokenizer.eos_token_id == 130005

    if config.quantization_bit !=0 and not config.pre_seq_len:
        raise AssertionError("quantization only support ptv2 finetuning")

    if config.quantization_bit != 0 and lora_args is not None:
        raise AssertionError("quantization only support ptv2 finetuning")

    # 缓存数据集
    if data_args.do_train:
        dataHelper.make_dataset_with_args(data_args.train_file, mixed_data=False, shuffle=True, mode='train')
    if data_args.do_eval:
        dataHelper.make_dataset_with_args(data_args.eval_file, mode='eval')
    if data_args.do_test:
        dataHelper.make_dataset_with_args(data_args.test_file, mode='test')


    trainer = Trainer(
        callbacks=[checkpoint_callback,LearningRateMonitor(logging_interval='step')],
        max_epochs=training_args.max_epochs,
        max_steps=training_args.max_steps,
        accelerator="gpu",
        devices=data_args.devices,
        enable_progress_bar=True,
        default_root_dir=data_args.output_dir,
        gradient_clip_val=training_args.max_grad_norm,
        accumulate_grad_batches=training_args.gradient_accumulation_steps,
        num_sanity_val_steps=0,
        strategy=strategy,
        #lora int8 precision='32'
        precision= '16' , #  #可以自行尝试  "32": "32-true", "16": "16-mixed", "bf16": "bf16-mixed"
    )


    if config.pre_seq_len is not None and lora_args is not None:
        raise ValueError('with lora and ptuning v2 cannot open at the same time')


    # 额外参数
    checkpoint_callback.tokenizer = tokenizer
    checkpoint_callback.data_args = data_args

    config.save_pretrained('best_ckpt')


    pl_model = MyTransformer(config=config, model_args=model_args, training_args=training_args, lora_args=lora_args,
                             num_layers_freeze=global_args["num_layers_freeze"],#
                             quantization_config=global_args["quantization_config"],
                             load_in_8bit=global_args["load_in_8bit"],
                             device_map={"": trainer.local_rank} if trainer.world_size > 1 else "auto")

    #恢复权重继续训练
    # pl_model.load_sft_weight('./best_ckpt/best.pt',is_trainable=True)

    if config.pre_seq_len is not None:
        # P-tuning v2
        pl_model.get_llm_model().half()
        pl_model.get_llm_model().transformer.prefix_encoder.float()
    else:
        # Finetune
        pl_model = pl_model.float()


    def dataset_loader_filter_fn(dataset):
        print('*' * 30, 'total', len(dataset))
        return dataset


    train_datasets = dataHelper.load_distributed_random_sampler(
        dataHelper.train_files,
        with_load_memory=data_args.data_backend == 'record',
        collate_fn=dataHelper.collate_fn,
        batch_size=training_args.train_batch_size,
        drop_last=True,  # 多卡建议扔掉
        num_processes=trainer.world_size, process_index=trainer.global_rank,
        dataset_loader_filter_fn=dataset_loader_filter_fn,
        num_workers=0
    )

    if train_datasets is not None:
        trainer.fit(pl_model, train_dataloaders=train_datasets)

