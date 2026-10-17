"""palmppg: SWHT-PP-003 camera palm photoplethysmography pilot stack.

Two tracks are enforced throughout (see palmppg.core.tracks):
  product_candidate  - phone-camera-producible features only, no ECG, no raw Bayer
  science            - Pi raw, ECG-aligned features, pulse arrival time
Nothing from the science track may be reported as a product result.
"""
__version__ = "0.1.0"
