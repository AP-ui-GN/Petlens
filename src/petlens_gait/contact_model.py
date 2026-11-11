"""Independently implemented pose-only temporal Transformer (no upstream weights).

Offline/bidirectional context; outputs are model-channel logits in LF/RF/LH/RH
order, not verified physical identities. Call predict with reviewed identity masks.
"""
from dataclasses import asdict, dataclass

import torch
from torch import nn
from torch.nn import functional as F

from .contact_features import CHANNELS, PAWS, PAW_INDICES, VERSION


@dataclass(frozen=True)
class ModelConfig:
    embed_dim: int = 64
    heads: int = 4
    ff_dim: int = 128
    layers: int = 2
    dropout: float = 0.1
    max_frames: int = 128


class CanineContactTransformer(nn.Module):
    def __init__(self, config=ModelConfig()):
        super().__init__()
        if (min(config.embed_dim, config.heads, config.ff_dim, config.layers,
                config.max_frames) < 1 or config.embed_dim % config.heads or
                not 0 <= config.dropout < 1):
            raise ValueError("Invalid Transformer configuration")
        self.config = config
        self.projection = nn.Linear(len(CHANNELS), config.embed_dim)
        self.position = nn.Parameter(torch.empty(1, config.max_frames, config.embed_dim))
        nn.init.normal_(self.position, std=0.02)
        self.dropout = nn.Dropout(config.dropout)
        layer = nn.TransformerEncoderLayer(config.embed_dim, config.heads,
                                           config.ff_dim, config.dropout, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, config.layers, enable_nested_tensor=False)
        # Independently initialize layers (TransformerEncoder clones its input).
        for block in self.encoder.layers:
            nn.init.xavier_uniform_(block.self_attn.in_proj_weight)
            for module in block.modules():
                if isinstance(module, nn.Linear):
                    nn.init.xavier_uniform_(module.weight)
                    if module.bias is not None:
                        nn.init.zeros_(module.bias)
        self.classifier = nn.Linear(config.embed_dim, len(PAWS))

    def forward(self, features, padding_mask=None):
        if features.ndim != 3 or features.shape[-1] != len(CHANNELS):
            raise ValueError("Expected (batch, frames, 69) features")
        b, t, _ = features.shape
        if b == 0 or not 0 < t <= self.config.max_frames:
            raise ValueError("Empty batch or unsupported window length")
        if padding_mask is None:
            padding_mask = torch.zeros((b, t), dtype=torch.bool, device=features.device)
        if padding_mask.shape != (b, t) or padding_mask.dtype != torch.bool:
            raise ValueError("Expected boolean (batch, frames) padding mask")
        if padding_mask.all(dim=1).any():
            raise ValueError("All-padding windows are forbidden")
        if not torch.isfinite(features[~padding_mask]).all():
            raise ValueError("Nonfinite unpadded features")
        # Padded values must not affect projection/attention, including NaN padding.
        features = features.masked_fill(padding_mask.unsqueeze(-1), 0)
        x = self.dropout(self.projection(features) + self.position[:, :t])
        logits = self.classifier(self.encoder(x, src_key_padding_mask=padding_mask))
        return logits.masked_fill(padding_mask.unsqueeze(-1), 0)

    @torch.no_grad()
    def predict(self, features, *, identity_valid, reference_valid, padding_mask=None,
                confidence_threshold=0.8):
        """CONTACT=1, AIRBORNE=0, abstain=-1. Scores are uncalibrated sigmoid values.

        identity_valid must be reviewed physical mapping/continuity evidence,
        never inferred from A/B names or AP-10K confidence. Use eval() explicitly.
        """
        if self.training:
            raise ValueError("Call eval() before inference")
        if not 0.5 < confidence_threshold <= 1:
            raise ValueError("Confidence threshold must be in (0.5, 1]")
        logits = self(features, padding_mask)
        if identity_valid.shape != logits.shape or identity_valid.dtype != torch.bool:
            raise ValueError("Expected boolean per-paw identity mask")
        if reference_valid.shape != features.shape[:2] or reference_valid.dtype != torch.bool:
            raise ValueError("Expected boolean body-reference mask")
        probability = logits.sigmoid()
        eligible = identity_valid & reference_valid.unsqueeze(-1)
        eligible &= features[..., [4*j+3 for j in PAW_INDICES]] == 1
        if padding_mask is not None:
            eligible &= ~padding_mask.unsqueeze(-1)
        confident = torch.maximum(probability, 1-probability) >= confidence_threshold
        accepted = eligible & confident
        states = torch.where(accepted, (probability >= 0.5).long(), -1)
        return dict(paw_order=PAWS, contact_probability=probability,
                    eligible=eligible, accepted=accepted, states=states)


def masked_contact_loss(logits, targets, target_valid, padding_mask=None):
    """Return None for no supervision; select BEFORE BCE (unknown may be NaN)."""
    if logits.shape != targets.shape or target_valid.shape != logits.shape:
        raise ValueError("Target shape mismatch")
    if target_valid.dtype != torch.bool:
        raise ValueError("Expected boolean target mask")
    mask = target_valid.clone()
    if padding_mask is not None:
        mask &= ~padding_mask.unsqueeze(-1)
    if not mask.any():
        return None
    if not torch.isfinite(targets[mask]).all() or not ((targets[mask] == 0) | (targets[mask] == 1)).all():
        raise ValueError("Supervised targets must be CONTACT=1 or AIRBORNE=0")
    return F.binary_cross_entropy_with_logits(logits[mask], targets[mask])


def save_checkpoint(path, model, *, metadata, optimizer=None):
    torch.save(dict(format_version=1, feature_version=VERSION, channels=list(CHANNELS),
                    paws=list(PAWS), config=asdict(model.config), model_state=model.state_dict(),
                    optimizer_state=optimizer.state_dict() if optimizer else None,
                    metadata=metadata), path)


def load_checkpoint(path):
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if (checkpoint["format_version"] != 1 or checkpoint["feature_version"] != VERSION or
            checkpoint["channels"] != list(CHANNELS) or checkpoint["paws"] != list(PAWS)):
        raise ValueError("Incompatible checkpoint feature/paw contract")
    model = CanineContactTransformer(ModelConfig(**checkpoint["config"]))
    model.load_state_dict(checkpoint["model_state"])
    return model, checkpoint
