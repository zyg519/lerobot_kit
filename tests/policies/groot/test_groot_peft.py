#!/usr/bin/env python

# Copyright 2024 NVIDIA Corporation and The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Lightweight tests for GrootPolicy PEFT/LoRA wrapping.

The GR00T N1.7-3B backbone is not loaded here; a small dummy module with a few
``nn.Linear`` layers stands in for it (same monkeypatch pattern as
``test_groot_n1_7.py``).
"""

import pytest
from torch import nn

from lerobot.configs import FeatureType, PolicyFeature
from lerobot.policies.groot.modeling_groot import GrootPolicy
from lerobot.utils.constants import ACTION, OBS_IMAGES, OBS_STATE


def _groot_config():
    return GrootPolicy.config_class(
        input_features={
            f"{OBS_IMAGES}.front": PolicyFeature(type=FeatureType.VISUAL, shape=(3, 256, 256)),
            OBS_STATE: PolicyFeature(type=FeatureType.STATE, shape=(8,)),
        },
        output_features={ACTION: PolicyFeature(type=FeatureType.ACTION, shape=(7,))},
        pretrained_path="dummy/gr00t-base",
        base_model_path="dummy/gr00t-base",
        device="cpu",
        use_bf16=False,
    )


class _DummyGrootModelWithLinear(nn.Module):
    """Small stand-in for GR00TN17 with enough Linear layers for LoRA injection."""

    def __init__(self):
        super().__init__()
        self.proj_in = nn.Linear(32, 32)
        self.net = nn.Sequential(
            nn.Linear(32, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
        )
        self.head = nn.Linear(64, 16)

    def forward(self, *args, **kwargs):
        raise NotImplementedError("not exercised by the PEFT wrapping tests")


def _instantiate_policy(monkeypatch):
    pytest.importorskip("transformers")

    from lerobot.policies.groot.groot_n1_7 import GR00TN17

    dummy_model = _DummyGrootModelWithLinear()
    monkeypatch.setattr(GR00TN17, "from_pretrained", classmethod(lambda cls, **kwargs: dummy_model))
    # Keep __init__ from probing checkpoint sidecars on the hub for the action horizon.
    monkeypatch.setattr(GrootPolicy, "_resolve_action_queue_steps", lambda self: 40)
    return GrootPolicy(_groot_config())


def test_groot_wrap_with_peft_uses_all_linear_targets(monkeypatch):
    pytest.importorskip("peft")

    policy = _instantiate_policy(monkeypatch)

    peft_model = policy.wrap_with_peft(
        peft_cli_overrides={
            "method_type": "LORA",
            "r": 8,
            "lora_alpha": 16,
        }
    )

    # `all-linear` is resolved by PEFT into the actual Linear module names at injection time.
    target_modules = peft_model.peft_config["default"].target_modules
    assert target_modules == {
        "_groot_model.proj_in",
        "_groot_model.net.0",
        "_groot_model.net.2",
        "_groot_model.head",
    }
    # PEFT picks up the base path from `name_or_path`, which GrootPolicy records from base_model_path.
    assert peft_model.peft_config["default"].base_model_name_or_path == policy.config.base_model_path


def test_groot_wrap_with_peft_freezes_base_and_trains_only_adapter(monkeypatch):
    pytest.importorskip("peft")

    policy = _instantiate_policy(monkeypatch)
    total_params = sum(p.numel() for p in policy.parameters())

    peft_model = policy.wrap_with_peft(
        peft_cli_overrides={
            "method_type": "LORA",
            "r": 8,
            "lora_alpha": 16,
        }
    )

    trainable_params = sum(p.numel() for p in peft_model.parameters() if p.requires_grad)
    assert trainable_params > 0
    assert trainable_params < total_params


def test_groot_peft_save_pretrained_writes_adapter_files(monkeypatch, tmp_path):
    pytest.importorskip("peft")

    policy = _instantiate_policy(monkeypatch)

    peft_model = policy.wrap_with_peft(
        peft_cli_overrides={
            "method_type": "LORA",
            "r": 8,
            "lora_alpha": 16,
        }
    )

    peft_model.save_pretrained(tmp_path)

    assert (tmp_path / "adapter_config.json").is_file()
    assert (tmp_path / "adapter_model.safetensors").is_file()
