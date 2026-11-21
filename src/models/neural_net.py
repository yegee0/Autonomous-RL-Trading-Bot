import torch.nn as nn


def get_ppo_config():
    return {
        "n_steps": 4096,
        "batch_size": 128,
        "n_epochs": 20,
        "learning_rate": 3e-4,
        "gamma": 0.99,
        "gae_lambda": 0.95,
        "ent_coef": 0.02,
    }


def get_policy_kwargs():
    return dict(
        net_arch=[256, 256, 128],
        activation_fn=nn.Tanh,
        ortho_init=True,
    )
