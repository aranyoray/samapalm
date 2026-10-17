"""Spatial decomposition of the palm (protocol sections 6.1 hand presence and 6.2).

Modules
  landmarks      hand landmark providers (MediaPipe, synthetic ground truth, skin-segmentation fallback)
                 and the 4 fps landmark run with the jitter motion proxy
  rois           21-landmark palm ROI polygons, rasterisation, thumb exclusion, 16 x 24 patch grid
  traces         streaming per-ROI / per-patch statistics on Bayer planes or RGB frames onto the uniform grid
  stmaps         spatio-temporal maps from the patch grid, zarr helpers, CNN input images
  static_colour  first-2-s colour features (chromaticity, melanin proxy, spatial variance, pallor index)
  run            orchestration: landmarks -> rois -> traces/patches -> static colour, written per camera
"""
