#!/usr/bin/env python3
"""Merge a LeRobot PEFT adapter into its base policy."""

import argparse
import shutil
from pathlib import Path

from lerobot.policies import get_policy_class


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "adapter_path",
        type=Path,
        help="Directory containing adapter_config.json and adapter_model.safetensors",
    )
    parser.add_argument(
        "output_path",
        type=Path,
        help="Directory where the merged policy will be saved",
    )
    parser.add_argument(
        "--policy-type",
        default="pi0",
        help="LeRobot policy type used to load the base policy",
    )
    parser.add_argument(
        "--base-model",
        type=Path,
        default=None,
        help="Override base_model_name_or_path from adapter_config.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    adapter_path = args.adapter_path.expanduser().resolve()
    output_path = args.output_path.expanduser().resolve()

    if not (adapter_path / "adapter_config.json").is_file():
        raise FileNotFoundError(f"Missing adapter_config.json in {adapter_path}")
    if not (adapter_path / "adapter_model.safetensors").is_file():
        raise FileNotFoundError(f"Missing adapter_model.safetensors in {adapter_path}")
    if output_path.exists() and any(output_path.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_path}")

    try:
        from peft import PeftConfig, PeftModel
    except ImportError as error:
        raise RuntimeError("Install the PEFT dependency first: uv sync --extra peft") from error

    peft_config = PeftConfig.from_pretrained(str(adapter_path))
    base_model_ref = args.base_model or peft_config.base_model_name_or_path
    if not base_model_ref:
        raise ValueError("The adapter does not specify a base_model_name_or_path")

    policy_class = get_policy_class(args.policy_type)
    print(f"Loading base policy from: {base_model_ref}")
    base_policy = policy_class.from_pretrained(str(base_model_ref))

    print(f"Loading LoRA adapter from: {adapter_path}")
    peft_policy = PeftModel.from_pretrained(
        base_policy,
        str(adapter_path),
        config=peft_config,
        is_trainable=False,
    )

    print(f"Merging weights into: {output_path}")
    merged_policy = peft_policy.merge_and_unload()
    output_path.mkdir(parents=True, exist_ok=True)
    merged_policy.save_pretrained(output_path)

    for source in adapter_path.glob("policy_*"):
        if source.is_file():
            shutil.copy2(source, output_path / source.name)

    model_file = output_path / "model.safetensors"
    if not model_file.is_file():
        raise RuntimeError(f"Merged policy did not produce {model_file}")

    print(f"Merged policy saved to: {output_path}")


if __name__ == "__main__":
    main()
