"""One source-bound physical-paw readout of the existing temporal encoder.

This is not an anatomical detector or an interchangeable 'either front paw'
output. The binding identifies one physical paw, source, dog and reviewed span.
The original four-paw model implementation and checkpoint format stay intact.
"""
from dataclasses import asdict

import torch
from torch import nn

from .contact_features import CHANNELS, VERSION
from .contact_model import CanineContactTransformer, ModelConfig


def validate_binding(binding):
    if (not isinstance(binding, dict) or binding.get("kind") != "tracked_front" or
            binding.get("anatomicalSide") != "unknown" or
            not all(isinstance(binding.get(k), str) and binding[k].strip()
                    for k in ("physicalPaw", "sourceVideoSha256", "dogId", "datasetId")) or
            type(binding.get("firstFrame")) is not int or
            type(binding.get("lastFrame")) is not int or
            not 0 <= binding["firstFrame"] <= binding["lastFrame"]):
        raise ValueError("Invalid source-bound physical front-paw output")


class IdentityNeutralContactModel(nn.Module):
    def __init__(self, config, binding):
        super().__init__()
        validate_binding(binding)
        self.config = config
        self.binding = dict(binding)
        self.backbone = CanineContactTransformer(config)
        # Retain the original anatomical head but never supervise or use it.
        self.backbone.classifier.requires_grad_(False)
        self.physical_head = nn.Linear(config.embed_dim, 1)

    def forward(self, features, padding_mask=None):
        if features.ndim != 3 or features.shape[-1] != len(CHANNELS):
            raise ValueError("Expected (batch, frames, 69) features")
        b, t, _ = features.shape
        if b == 0 or not 0 < t <= self.config.max_frames:
            raise ValueError("Empty batch or unsupported window length")
        if padding_mask is None:
            padding_mask = torch.zeros((b, t), dtype=torch.bool, device=features.device)
        if padding_mask.shape != (b, t) or padding_mask.dtype != torch.bool:
            raise ValueError("Expected boolean frame padding mask")
        if padding_mask.all(dim=1).any() or not torch.isfinite(features[~padding_mask]).all():
            raise ValueError("All-padding or nonfinite unpadded window")
        features = features.masked_fill(padding_mask.unsqueeze(-1), 0)
        base = self.backbone
        x = base.dropout(base.projection(features) + base.position[:, :t])
        hidden = base.encoder(x, src_key_padding_mask=padding_mask)
        return self.physical_head(hidden).masked_fill(padding_mask.unsqueeze(-1), 0)

    @torch.no_grad()
    def predict(self, features, *, binding, physical_eligible, padding_mask=None,
                confidence_threshold=0.8):
        if self.training or binding != self.binding:
            raise ValueError("Use eval() and the exact checkpoint physical binding")
        if not 0.5 < confidence_threshold <= 1:
            raise ValueError("Invalid abstention threshold")
        logits = self(features, padding_mask)
        if physical_eligible.shape != logits.shape or physical_eligible.dtype != torch.bool:
            raise ValueError("Expected explicit per-frame physical eligibility mask")
        eligible = physical_eligible.clone()
        if padding_mask is not None:
            eligible &= ~padding_mask.unsqueeze(-1)
        p = logits.sigmoid()
        accepted = eligible & (torch.maximum(p, 1-p) >= confidence_threshold)
        return dict(binding=self.binding, contact_probability=p, accepted=accepted,
                    states=torch.where(accepted, (p >= 0.5).long(), -1))


def save_neutral_checkpoint(path, model, *, metadata, optimizer=None):
    torch.save(dict(format_version=2, kind="identity_neutral_exploratory",
                    feature_version=VERSION, channels=list(CHANNELS),
                    binding=model.binding, config=asdict(model.config),
                    model_state=model.state_dict(),
                    optimizer_state=optimizer.state_dict() if optimizer else None,
                    metadata=metadata), path)


def load_neutral_checkpoint(path):
    record = torch.load(path, map_location="cpu", weights_only=True)
    if (record.get("format_version") != 2 or record.get("kind") != "identity_neutral_exploratory" or
            record.get("feature_version") != VERSION or record.get("channels") != list(CHANNELS)):
        raise ValueError("Incompatible identity-neutral checkpoint")
    model = IdentityNeutralContactModel(ModelConfig(**record["config"]), record["binding"])
    model.load_state_dict(record["model_state"])
    return model, record
