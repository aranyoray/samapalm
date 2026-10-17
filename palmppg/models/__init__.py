"""Model zoo for SWHT-PP-003 (protocol sections 9, 10 and 11).

Every estimator here is sklearn-compatible so that it can be wrapped by
:class:`palmppg.models.track.TrackGuard`, which enforces the two model tracks
(``product_candidate`` versus ``science``) through ``palmppg.core.tracks.REGISTRY``
before anything is fitted or predicted.

Sub-modules (heavy dependencies are imported lazily inside functions):

* ``track``        TrackGuard and target-leak checks (protocol 9, 11.5).
* ``tabular``      GBDTs with monotone constraints, linear baselines, quantile pairs, the two
                   mandatory baselines (protocol 9, 11.2).
* ``temporal``     Conv1D / TCN / GRU / small transformer on beat and IBI sequences (torch).
* ``cnn``          ResNet-18 on spatio-temporal maps (torch).
* ``graph``        ST-GCN on the palm ROI graph from ``cfg rois.graph`` (torch).
* ``visibility``   natural and horizontal visibility-graph features of an IBI series (networkx).
* ``adversarial``  DANN-style domain-adversarial features (torch; protocol E11).
* ``fm``           PaPaGei and SiamQuality embedding interfaces (torch; protocol E10).
* ``fusion``       late fusion with ridge-learned weights and cross-attention fusion (torch).
* ``gan``          PulseGAN and Dual-GAN denoising trainers (torch; never headline results).
* ``uncertainty``  deep ensembles, MC dropout, split conformal intervals, abstain policy (protocol 10).
* ``zoo``          the name -> factory registry and ``build()``.
"""
from __future__ import annotations

from palmppg.core.tracks import REGISTRY, FeatureRegistry


def register_features(registry: FeatureRegistry = REGISTRY, **kw) -> list[str]:
    """Register every feature column this package can produce (idempotent).

    Delegates to the ``register_features`` of ``visibility``, ``fm`` and ``adversarial``;
    returns the full list of registered column names. Serves CONTRACTS section 5.
    """
    from palmppg.models import adversarial, fm, visibility

    names: list[str] = []
    names += visibility.register_features(registry, **kw)
    names += fm.register_features(registry, **kw)
    names += adversarial.register_features(registry, **kw)
    return names


__all__ = ["register_features"]
