"""Prepared fixed-step pilot; see reports/rtmpose-paw-v2-experiment/README.md.

Run from the PetLens root with MMPOSE_ROOT and PETLENS_AP10K_CHECKPOINT set.
No downloads occur through this config. Checkpoint must be the original .pth.
"""
_base_ = ['{{$MMPOSE_ROOT:}}/configs/animal_2d_keypoint/rtmpose/ap10k/rtmpose-m_8xb64-210e_ap10k-256x256.py']
custom_imports = dict(imports=['training.rtmpose_paw_v2.components'], allow_failed_imports=False)
load_from = '{{$PETLENS_AP10K_CHECKPOINT:__MISSING__}}'
if load_from == '__MISSING__':
    load_from = None
if load_from is None and '{{$PETLENS_ALLOW_RANDOM_INIT:0}}' != '1':
    raise RuntimeError('Set PETLENS_AP10K_CHECKPOINT to the exact original AP-10K .pth. No substitute or implicit download is allowed.')
resume = False
work_dir = 'outputs/rtmpose-paw-v2-pilot'
randomness = dict(seed=20261104, deterministic=True)
env_cfg = dict(cudnn_benchmark=False)

model = dict(
    backbone=dict(init_cfg=None, frozen_stages=4, norm_eval=True),
    head=dict(type='PreservedPawHead'),
    test_cfg=dict(flip_test=False))
train_cfg = dict(_delete_=True, type='IterBasedTrainLoop', max_iters=100, val_interval=100)
val_cfg = dict(type='ValLoop')
test_cfg = dict(type='TestLoop')
optim_wrapper = dict(
    _delete_=True, type='OptimWrapper',
    optimizer=dict(type='AdamW', lr=1e-5, weight_decay=0.),
    clip_grad=dict(max_norm=1., norm_type=2))
param_scheduler = []
auto_scale_lr = dict(enable=False, base_batch_size=4)
custom_hooks = []  # No EMA, pipeline switching, or best-checkpoint selection.
default_hooks = dict(
    checkpoint=dict(_delete_=True, type='CheckpointHook', by_epoch=False,
                    interval=100, save_last=True, max_keep_ckpts=1),
    logger=dict(type='LoggerHook', interval=10))
log_processor = dict(by_epoch=False)

# Derived COCO files contain only saved, unambiguous single-dog detector boxes.
# No stochastic augmentation in this first reproducibility pilot. Evaluate the
# baseline with identical preprocessing and flip_test=False.
train_pipeline = [
    dict(type='LoadImage'),
    dict(type='GetBBoxCenterScale', padding=1.25),
    dict(type='TopdownAffine', input_size=(256, 256)),
    dict(type='GenerateTarget', encoder=dict(
        type='SimCCLabel', input_size=(256, 256), sigma=(5.66, 5.66),
        simcc_split_ratio=2., normalize=False, use_dark=False)),
    dict(type='PackPoseInputs')]
val_pipeline = [
    dict(type='LoadImage'),
    dict(type='GetBBoxCenterScale', padding=1.25),
    dict(type='TopdownAffine', input_size=(256, 256)),
    dict(type='PackPoseInputs')]
train_dataloader = dict(
    _delete_=True, batch_size=4, num_workers=0, persistent_workers=False,
    sampler=dict(type='InfiniteSampler', shuffle=True),
    dataset=dict(type='AP10KDataset', data_mode='topdown',
                 metainfo=dict(from_file='{{$MMPOSE_ROOT:}}/configs/_base_/datasets/ap10k.py'),
                 data_root='', data_prefix=dict(img='reports/paw-annotation-data-v1/'),
                 ann_file='reports/rtmpose-paw-v2-experiment/pilot-train.coco.json',
                 pipeline=train_pipeline))
val_dataloader = dict(
    _delete_=True, batch_size=4, num_workers=0, persistent_workers=False,
    drop_last=False, sampler=dict(type='DefaultSampler', shuffle=False, round_up=False),
    dataset=dict(type='AP10KDataset', data_mode='topdown', test_mode=True,
                 metainfo=dict(from_file='{{$MMPOSE_ROOT:}}/configs/_base_/datasets/ap10k.py'),
                 data_root='', data_prefix=dict(img='reports/paw-annotation-data-v1/'),
                 ann_file='reports/rtmpose-paw-v2-experiment/temporal-diagnostic.coco.json',
                 pipeline=val_pipeline))
test_dataloader = val_dataloader
val_evaluator = dict(_delete_=True, type='ReviewedPawMetric',
                     ann_file='reports/rtmpose-paw-v2-experiment/temporal-diagnostic.coco.json')
test_evaluator = val_evaluator
