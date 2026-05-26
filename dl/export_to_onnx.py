"""
Exporta un modelo de vision (EfficientNet) a ONNX y lo cuantiza a INT8.

Uso:
    python export_to_onnx.py --checkpoint checkpoints/best_model.pth
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import torch
import torch.nn as nn
import torchvision.models as models
from onnxruntime.quantization import QuantType, quantize_dynamic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export EfficientNet to ONNX INT8")
    parser.add_argument("--num-classes", type=int, default=5)
    parser.add_argument("--checkpoint", type=str, default="")
    parser.add_argument("--fp32-output", type=str, default="models/retinopathy_fp32.onnx")
    parser.add_argument("--int8-output", type=str, default="models/retinopathy_int8.onnx")
    return parser.parse_args()


def create_model(num_classes: int = 5) -> nn.Module:
    model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
    num_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(num_features, num_classes),
    )
    return model


def export_onnx(model: nn.Module, output_path: str) -> None:
    model.eval()
    dummy_input = torch.randn(1, 3, 224, 224)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        dummy_input,
        output.as_posix(),
        opset_version=17,
        input_names=["image"],
        output_names=["logits"],
        dynamic_axes={"image": {0: "batch_size"}},
    )


def quantize_int8(input_path: str, output_path: str) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    quantize_dynamic(input_path, output_path, weight_type=QuantType.QInt8)

    orig_mb = os.path.getsize(input_path) / 1e6
    quant_mb = os.path.getsize(output_path) / 1e6
    ratio = (quant_mb / orig_mb) if orig_mb > 0 else 0
    print(f"Original: {orig_mb:.1f} MB -> INT8: {quant_mb:.1f} MB ({ratio:.0%})")


def main() -> None:
    args = parse_args()

    model = create_model(num_classes=args.num_classes)
    if args.checkpoint:
        state_dict = torch.load(args.checkpoint, map_location="cpu")
        model.load_state_dict(state_dict)

    export_onnx(model, args.fp32_output)
    quantize_int8(args.fp32_output, args.int8_output)
    print(f"Modelo FP32: {args.fp32_output}")
    print(f"Modelo INT8: {args.int8_output}")


if __name__ == "__main__":
    main()
