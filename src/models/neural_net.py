from typing import Optional

import torch.nn as nn


def _linear_schedule(start: float, end: float):
    """Linear from ``start`` at progress=1.0 down to ``end`` at progress=0.0.

    SB3 passes progress_remaining (1→0 over training), so this fades the LR
    smoothly over the run — meaningful policies find their optimum at low LR,
    exploration happens at high LR.
    """
    def schedule(progress_remaining: float) -> float:
        return end + progress_remaining * (start - end)
    return schedule


def get_ppo_config(regime: Optional[str] = None):
    """Base PPO config, tweaked per regime head.

    Key changes vs the old baseline:
      * n_steps 4096 → 8192: longer rollouts, more stable advantage estimates
      * ent_coef 0.02 → 0.04: more exploration so the policy doesn't collapse
        to a single action (the old model went 100% HOLD in bull markets)
      * clip_range widened to 0.3 so the policy can take bigger steps when
        a regime shift makes the old policy very wrong
      * learning rate becomes a linear schedule from 3e-4 to 5e-5
    """
    config = {
        "n_steps": 8192,
        "batch_size": 256,
        "n_epochs": 15,
        "learning_rate": _linear_schedule(3e-4, 5e-5),
        "gamma": 0.995,            # bump → longer credit horizon, suits daily trading reward
        "gae_lambda": 0.95,
        "ent_coef": 0.04,
        "clip_range": 0.3,
        "vf_coef": 0.5,
        "max_grad_norm": 0.5,
    }
    # Crisis head trades fast and chops a lot — shorter credit horizon helps.
    if regime == "crisis":
        config["gamma"] = 0.97
        config["ent_coef"] = 0.06    # even more exploration for the choppy head
    # Range head wants to catch mean-reversion — needs lower exploration to
    # commit to its setups instead of flipping actions every bar.
    elif regime == "range":
        config["ent_coef"] = 0.025
    return config


def get_policy_kwargs():
    return dict(
        net_arch=[256, 256, 128],
        activation_fn=nn.Tanh,
        ortho_init=True,
    )
