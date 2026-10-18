"""Classical rPPG extraction on ROI colour traces (protocol section 6.3 "classical on ROI traces").

Every method takes `rgb` (T, 3) float on the uniform reference-clock grid (Pi path: R, (G1+G2)/2, B in
linear calibrated units, never demosaiced; phone and pi_proxy: inverted-sRGB "linear-ish" RGB) and `fs`,
and returns a 1-D pulse signal (T,) that is band-passed to `band` (the config's `pulse.band_rate` unless
another band is passed, e.g. `pulse.band_morph`), z-scored, with NaN where the input was NaN, in the
package polarity: positive = blood-volume increase = negated intensity (CONTRACTS section 6).

Methods: GREEN, CHROM (de Haan & Jeanne 2013), POS (Wang et al. 2017), PBV (de Haan & van Leest 2014),
ICA (Poh et al. 2010; JADE or sklearn FastICA), PCA (Lewandowska et al. 2011), LGI (Pilz et al. 2018),
OMIT (Casado & Lopez 2023) and 2SR (Wang, Stuijk & de Haan 2015, needs per-pixel data: the patch grid
(T, P, 3); with ROI means only, the caller stacks ROIs as "pixels" and labels the output).

Polarity: methods with a deterministic sign (GREEN, CHROM, POS, PBV, LGI, OMIT) are negated analytically
where their native output follows intensity; methods with an arbitrary sign (ICA, PCA, 2SR) and, as a
safeguard, every method are then aligned so the correlation with the negated band-passed green trace is
positive (`align_polarity`). The dispatcher `run_method(name, rgb_or_patches, fs, cfg)` reads the band,
the detrend lambda and the method constants from the config (with the papers' values as defaults).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from palmppg.pulse.preprocess import (
    VOLUME_SIGN,
    bandpass,
    bridge_nans,
    detrend_smoothness_prior,
    hann_window,
    restore_nans,
    zscore,
)
from palmppg.pulse.sqi import periodogram

METHODS: tuple[str, ...] = ("GREEN", "CHROM", "POS", "PBV", "ICA", "PCA", "LGI", "OMIT", "2SR")
ALIASES = {"SSR": "2SR", "G": "GREEN", "CHROME": "CHROM"}

# Method constants from the papers (not protocol quantities); the config may override them.
CHROM_WINDOW_S = 1.6     # de Haan & Jeanne 2013: 32 frames at 20 fps, Hann, 50 % overlap-add
POS_WINDOW_S = 1.6       # Wang et al. 2017: l = 1.6 s (32 frames at 20 fps), one-frame step
SSR_WINDOW_S = 1.0       # Wang et al. 2015: l = fs (1 s)
PBV_STANDARD = (0.33, 0.77, 0.53)  # de Haan & van Leest 2014, normalised R, G, B pulsatile amplitudes


# --------------------------------------------------------------------------- helpers
def _as_rgb(x) -> np.ndarray:
    """(T, 3) float64 from (T, 3) or (T, P, 3) (pixels averaged, NaN-aware)."""
    a = np.asarray(x, dtype=float)
    if a.ndim == 3:
        if a.shape[2] != 3:
            raise ValueError(f"patch input must be (T, P, 3), got {a.shape}")
        with np.errstate(invalid="ignore"):
            a = np.nanmean(a, axis=1)
    if a.ndim != 2 or a.shape[1] != 3:
        raise ValueError(f"rgb must be (T, 3), got {a.shape}")
    return a


def _bridge_rgb(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Bridge NaNs per channel; the time mask is True where any channel was NaN."""
    out = np.empty_like(rgb)
    mask = np.zeros(rgb.shape[0], dtype=bool)
    for c in range(rgb.shape[1]):
        out[:, c], m = bridge_nans(rgb[:, c])
        mask |= m
    return out, mask


def _normalise(rgb: np.ndarray) -> np.ndarray:
    """Temporal normalisation Cn = C / mean_t(C) - 1 per channel (zero-mean, unit DC)."""
    mu = rgb.mean(axis=0)
    mu = np.where(np.abs(mu) > 1e-12, mu, 1.0)
    return rgb / mu - 1.0


def volume_reference(rgb: np.ndarray, fs: float, band: tuple[float, float]) -> np.ndarray:
    """Band-passed negated normalised green: the reference that fixes the polarity of every method."""
    g = _normalise(rgb)[:, 1]
    return bandpass(VOLUME_SIGN * g, fs, band[0], band[1])


def align_polarity(pulse: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, bool]:
    """Flip `pulse` when its correlation with `reference` is negative. Returns (signal, flipped)."""
    p = np.asarray(pulse, dtype=float)
    r = np.asarray(reference, dtype=float)
    ok = np.isfinite(p) & np.isfinite(r)
    if ok.sum() < 3:
        return p, False
    pc, rc = p[ok] - p[ok].mean(), r[ok] - r[ok].mean()
    den = np.sqrt(np.sum(pc**2) * np.sum(rc**2))
    if den <= 0 or np.sum(pc * rc) / den >= 0:
        return p, False
    return -p, True


def _finalise(pulse: np.ndarray, rgb: np.ndarray, mask: np.ndarray, fs: float, band: tuple[float, float],
              align: bool, order: int = 4) -> np.ndarray:
    """Band-pass to `band`, z-score, polarity safeguard, NaNs restored."""
    y = bandpass(pulse, fs, band[0], band[1], order=order)
    y = zscore(y)
    if align:
        y, _ = align_polarity(y, volume_reference(rgb, fs, band))
    return restore_nans(y, mask)


def _band_peak_ratio(x: np.ndarray, fs: float, band: tuple[float, float]) -> float:
    """Peak power / band power of a periodogram (scale-free "strength" of the dominant peak in `band`)."""
    f, pxx = periodogram(x, fs)
    sel = (f >= band[0]) & (f <= band[1])
    tot = float(np.sum(pxx[sel]))
    return float(np.max(pxx[sel]) / tot) if sel.any() and tot > 0 else 0.0


def _select_component(sources: np.ndarray, fs: float, band: tuple[float, float], rel_var_min: float = 1e-6) -> np.ndarray:
    """The source with the strongest in-band peak among those carrying at least `rel_var_min` of the
    largest source variance (a rank-deficient input leaves a numerically empty component that must not win)."""
    var = np.var(sources, axis=1)
    keep = var >= rel_var_min * max(float(var.max()), 1e-300)
    ratios = [(_band_peak_ratio(s, fs, band) if k else -1.0) for s, k in zip(sources, keep)]
    return sources[int(np.argmax(ratios))]


# --------------------------------------------------------------------------- GREEN
def green(rgb, fs: float, band: tuple[float, float], lam: float | None = None, align: bool = True) -> np.ndarray:
    """GREEN: pulse = -(G / mean(G) - 1), detrended (smoothness prior, `lam`) and band-passed.

    The negation applies the volume polarity: more blood absorbs more green light (Verkruysse 2008).
    Section 6.3. Output: z-scored, unitless.
    """
    rgb = _as_rgb(rgb)
    x, mask = _bridge_rgb(rgb)
    g = _normalise(x)[:, 1]
    if lam is not None:
        g = detrend_smoothness_prior(g, lam)
    return _finalise(VOLUME_SIGN * g, x, mask, fs, band, align)


# --------------------------------------------------------------------------- CHROM
def chrom(rgb, fs: float, band: tuple[float, float], window_s: float = CHROM_WINDOW_S, align: bool = True) -> np.ndarray:
    """CHROM (de Haan & Jeanne 2013), windowed with Hann overlap-add (window `window_s`, 50 % overlap).

    Per window: Rn, Gn, Bn = R, G, B divided by their window means;
        Xs = 3 Rn - 2 Gn,   Ys = 1.5 Rn + Gn - 1.5 Bn   (eq. 10-11 of the paper, skin-tone standardised),
        Xf, Yf = band-passed Xs, Ys,   alpha = sigma(Xf) / sigma(Yf),   S = Xf - alpha Yf   (eq. 12).
    Windows are Hann-weighted and overlap-added (normalised by the window sum). For a skin pulse vector
    (green strongest) S already follows blood volume, so no analytic negation is applied; the polarity
    safeguard then confirms it. Section 6.3.
    """
    rgb = _as_rgb(rgb)
    x, mask = _bridge_rgb(rgb)
    n = x.shape[0]
    win = min(max(int(round(window_s * fs)), 4), n)
    step = max(win // 2, 1)
    starts = list(range(0, n - win + 1, step))
    if starts[-1] + win < n:
        starts.append(n - win)
    w = hann_window(win)
    h = np.zeros(n)
    wsum = np.zeros(n)
    for s in starts:
        seg = x[s:s + win]
        cn = seg / np.where(np.abs(seg.mean(axis=0)) > 1e-12, seg.mean(axis=0), 1.0)
        xs = 3.0 * cn[:, 0] - 2.0 * cn[:, 1]
        ys = 1.5 * cn[:, 0] + cn[:, 1] - 1.5 * cn[:, 2]
        xf = bandpass(xs, fs, band[0], band[1])
        yf = bandpass(ys, fs, band[0], band[1])
        sy = float(np.std(yf))
        alpha = float(np.std(xf)) / sy if sy > 1e-12 else 0.0
        sig = xf - alpha * yf
        h[s:s + win] += w * sig
        wsum[s:s + win] += w
    h = np.where(wsum > 1e-3, h / np.maximum(wsum, 1e-3), 0.0)
    return _finalise(h, x, mask, fs, band, align)


# --------------------------------------------------------------------------- POS
def pos(rgb, fs: float, band: tuple[float, float], window_s: float = POS_WINDOW_S, align: bool = True) -> np.ndarray:
    """POS, plane-orthogonal-to-skin (Wang, den Brinker, Stuijk & de Haan 2017), Algorithm 1.

    For every frame n with window m = n - l + 1 (l = `window_s` x fs):
        Cn = C[m:n] / mean(C[m:n])                      (temporal normalisation per channel)
        S = P Cn,  P = [[0, 1, -1], [-2, 1, 1]]          (projection onto the plane orthogonal to skin tone)
        h = S1 + (sigma(S1) / sigma(S2)) S2              (alpha tuning)
        H[m:n] += h - mean(h)                            (overlap-add)
    With intensity decreasing as blood volume rises and green the strongest channel, h follows
    intensity, so H is negated (`VOLUME_SIGN`) to the volume polarity. Section 6.3.
    """
    rgb = _as_rgb(rgb)
    x, mask = _bridge_rgb(rgb)
    n = x.shape[0]
    win = min(max(int(round(window_s * fs)), 3), n)
    wins = sliding_window_view(x, win, axis=0)          # (n - win + 1, 3, win)
    mu = wins.mean(axis=2, keepdims=True)
    cn = wins / np.where(np.abs(mu) > 1e-12, mu, 1.0)
    s1 = cn[:, 1, :] - cn[:, 2, :]
    s2 = -2.0 * cn[:, 0, :] + cn[:, 1, :] + cn[:, 2, :]
    sd2 = s2.std(axis=1, keepdims=True)
    alpha = np.where(sd2 > 1e-12, s1.std(axis=1, keepdims=True) / np.maximum(sd2, 1e-12), 0.0)
    h = s1 + alpha * s2
    h = h - h.mean(axis=1, keepdims=True)
    out = np.zeros(n)
    for k in range(h.shape[0]):
        out[k:k + win] += h[k]
    return _finalise(VOLUME_SIGN * out, x, mask, fs, band, align)


# --------------------------------------------------------------------------- PBV
def pbv(rgb, fs: float, band: tuple[float, float], pbv_vector: Sequence[float] = PBV_STANDARD,
        lam: float | None = None, align: bool = True) -> np.ndarray:
    """PBV, blood-volume pulse signature (de Haan & van Leest 2014).

    With Cn (3, T) the normalised (C / mean - 1), detrended and band-passed colour traces and Pbv the
    (unit-free) pulsatile amplitude vector of normalised R, G, B (`pbv_vector`, the paper's standard
    [0.33, 0.77, 0.53] by default), the pulse is the linear combination whose colour signature is Pbv:
        Q = Cn Cn^T,   W = k Q^-1 Pbv,   k = 1 / (Pbv^T Q^-1 Pbv),   S = W^T Cn,
    so that Cn S^T = k Pbv (eq. 9-10 of the paper). S follows intensity along Pbv and is negated to the
    volume polarity. Section 6.3.
    """
    rgb = _as_rgb(rgb)
    x, mask = _bridge_rgb(rgb)
    cn = _normalise(x)
    cols = []
    for c in range(3):
        v = detrend_smoothness_prior(cn[:, c], lam) if lam is not None else cn[:, c]
        cols.append(bandpass(v, fs, band[0], band[1]))
    cn = np.asarray(cols)                                # (3, T)
    p = np.asarray(pbv_vector, dtype=float).reshape(3)
    p = p / np.linalg.norm(p)
    q = cn @ cn.T
    q = q + 1e-12 * np.trace(q) * np.eye(3)
    w = np.linalg.solve(q, p)
    k = 1.0 / max(float(p @ w), 1e-18)
    s = k * (w @ cn)
    return _finalise(VOLUME_SIGN * s, x, mask, fs, band, align)


# --------------------------------------------------------------------------- ICA (JADE)
def jade(x: np.ndarray, n_components: int | None = None, max_sweeps: int = 100) -> tuple[np.ndarray, np.ndarray]:
    """JADE blind source separation (Cardoso & Souloumiac 1993) for a small number of sources.

    `x` is (n, T). Whitening by PCA, fourth-order cumulant matrices Q_ij (Cardoso's parametrisation),
    joint approximate diagonalisation by Jacobi (Givens) rotations until no rotation exceeds
    1 / (100 sqrt(T)). Returns (sources (m, T), demixing matrix (m, n)). Sources are ordered by
    decreasing variance of their contribution.
    """
    x = np.asarray(x, dtype=float)
    n, t = x.shape
    m = n if n_components is None else int(n_components)
    x = x - x.mean(axis=1, keepdims=True)
    cov = x @ x.T / t
    d, u = np.linalg.eigh(cov)
    order = np.argsort(d)[::-1][:m]
    d, u = d[order], u[:, order]
    rank = int(np.sum(d > 1e-10 * max(float(d[0]), 1e-300)))   # drop numerically empty directions
    m = max(min(m, rank), 1)
    d, u = d[:m], u[:, :m]
    b = (u / np.sqrt(np.maximum(d, 1e-18))).T          # whitening (m, n)
    z = b @ x                                           # (m, T)
    eye = np.eye(m)
    cms = []
    for im in range(m):
        xim = z[im]
        q = ((z * (xim * xim)) @ z.T) / t - eye - 2.0 * np.outer(eye[:, im], eye[:, im])
        cms.append(q)
        for jm in range(im):
            q = np.sqrt(2.0) * (((z * (xim * z[jm])) @ z.T) / t - np.outer(eye[:, im], eye[:, jm])
                                - np.outer(eye[:, jm], eye[:, im]))
            cms.append(q)
    cm = np.concatenate(cms, axis=1)                    # (m, m * nbcm)
    nbcm = len(cms)
    v = np.eye(m)
    seuil = 1.0 / np.sqrt(t) / 100.0
    for _ in range(max_sweeps):
        rotated = False
        for p in range(m - 1):
            for q in range(p + 1, m):
                ip = np.arange(p, m * nbcm, m)
                iq = np.arange(q, m * nbcm, m)
                g = np.vstack([cm[p, ip] - cm[q, iq], cm[p, iq] + cm[q, ip]])
                gg = g @ g.T
                ton = gg[0, 0] - gg[1, 1]
                toff = gg[0, 1] + gg[1, 0]
                theta = 0.5 * np.arctan2(toff, ton + np.sqrt(ton * ton + toff * toff))
                if abs(theta) > seuil:
                    rotated = True
                    c, s = np.cos(theta), np.sin(theta)
                    giv = np.array([[c, -s], [s, c]])
                    v[:, [p, q]] = v[:, [p, q]] @ giv
                    cm[[p, q], :] = giv.T @ cm[[p, q], :]
                    cp, cq = cm[:, ip].copy(), cm[:, iq].copy()
                    cm[:, ip] = c * cp + s * cq
                    cm[:, iq] = -s * cp + c * cq
        if not rotated:
            break
    w = v.T @ b                                         # demixing (m, n)
    a = np.linalg.pinv(w)
    energy = np.sum(a**2, axis=0)
    idx = np.argsort(energy)[::-1]
    w = w[idx]
    signs = np.sign(np.sign(a[0, idx]) + 0.1)           # fix a conventional sign (first row of mixing positive)
    w = w * signs[:, None]
    return w @ x, w


def ica(rgb, fs: float, band: tuple[float, float], lam: float | None = None, algorithm: str = "jade",
        seed: int = 0, align: bool = True) -> np.ndarray:
    """ICA (Poh, McDuff & Picard 2010): detrended, standardised R, G, B -> 3 independent components.

    x_i(t) = (C_i(t) - mu_i) / sigma_i (detrended with the smoothness prior, `lam`), s = W x with W from
    JADE (`algorithm="jade"`, the paper's choice) or sklearn FastICA. The component with the strongest
    spectral peak in `band` (largest peak-power / band-power ratio) is the pulse; its sign is arbitrary
    and is fixed by `align_polarity`. Section 6.3.
    """
    rgb = _as_rgb(rgb)
    x, mask = _bridge_rgb(rgb)
    cn = _normalise(x)
    comps = []
    for c in range(3):
        v = detrend_smoothness_prior(cn[:, c], lam) if lam is not None else cn[:, c]
        sd = float(np.std(v))
        comps.append((v - v.mean()) / sd if sd > 1e-12 else v - v.mean())
    xx = np.asarray(comps)                               # (3, T)
    if algorithm.lower() == "jade":
        sources, _ = jade(xx, 3)
    elif algorithm.lower() == "fastica":
        from sklearn.decomposition import FastICA

        model = FastICA(n_components=3, random_state=int(seed), max_iter=1000, whiten="unit-variance")
        sources = model.fit_transform(xx.T).T
    else:
        raise ValueError("algorithm must be 'jade' or 'fastica'")
    best = _select_component(sources, fs, band)
    return _finalise(best, x, mask, fs, band, align)


# --------------------------------------------------------------------------- PCA
def pca(rgb, fs: float, band: tuple[float, float], lam: float | None = None, align: bool = True) -> np.ndarray:
    """PCA (Lewandowska et al. 2011): principal components of the detrended, standardised R, G, B traces.

    Covariance Sigma = X X^T / T of the (3, T) standardised traces, eigenvectors e_k, components
    y_k = e_k^T X. The component with the strongest spectral peak in `band` is kept (the paper selects
    among the leading components by their periodicity). Sign fixed by `align_polarity`. Section 6.3.
    """
    rgb = _as_rgb(rgb)
    x, mask = _bridge_rgb(rgb)
    cn = _normalise(x)
    comps = []
    for c in range(3):
        v = detrend_smoothness_prior(cn[:, c], lam) if lam is not None else cn[:, c]
        sd = float(np.std(v))
        comps.append((v - v.mean()) / sd if sd > 1e-12 else v - v.mean())
    xx = np.asarray(comps)
    cov = xx @ xx.T / xx.shape[1]
    _, vec = np.linalg.eigh(cov)
    comps_pc = vec.T[::-1] @ xx                           # descending eigenvalue order
    best = _select_component(comps_pc, fs, band)
    return _finalise(best, x, mask, fs, band, align)


# --------------------------------------------------------------------------- LGI
def lgi(rgb, fs: float, band: tuple[float, float], align: bool = True) -> np.ndarray:
    """LGI, local group invariance (Pilz, Zaunseder, Krajewski & Blazek 2018).

    X (3, T) raw colour traces; U S V^T = svd(X); u1 the first left singular vector (the dominant,
    illumination-driven direction); P = I - u1 u1^T; Y = P X; pulse = Y[1] (green row of the
    projected traces). Follows intensity, negated to the volume polarity. Section 6.3.
    """
    rgb = _as_rgb(rgb)
    x, mask = _bridge_rgb(rgb)
    xx = x.T
    u, _, _ = np.linalg.svd(xx, full_matrices=False)
    u1 = u[:, 0:1]
    proj = np.eye(3) - u1 @ u1.T
    y = proj @ xx
    return _finalise(VOLUME_SIGN * y[1], x, mask, fs, band, align)


# --------------------------------------------------------------------------- OMIT
def omit(rgb, fs: float, band: tuple[float, float], align: bool = True) -> np.ndarray:
    """OMIT, orthogonal matrix image transformation (Casado & Lopez 2023), QR based.

    X (3, T) raw colour traces; Q R = qr(X) (reduced); S = Q[:, 0] (the orthonormal basis vector of the
    first colour sample); P = I - S S^T; Y = P X; pulse = Y[1]. Follows intensity, negated to the volume
    polarity. Section 6.3.
    """
    rgb = _as_rgb(rgb)
    x, mask = _bridge_rgb(rgb)
    xx = x.T
    q, _ = np.linalg.qr(xx)
    s = q[:, 0:1]
    proj = np.eye(3) - s @ s.T
    y = proj @ xx
    return _finalise(VOLUME_SIGN * y[1], x, mask, fs, band, align)


# --------------------------------------------------------------------------- 2SR
def ssr(patches, fs: float, band: tuple[float, float], window_s: float = SSR_WINDOW_S, align: bool = True) -> np.ndarray:
    """2SR, spatial subspace rotation (Wang, Stuijk & de Haan 2015), on per-pixel data (T, P, 3).

    Per frame t with V_t (N_t x 3) the skin pixels: C_t = V_t^T V_t / N_t, eigen-decomposition
    C_t = U_t Lambda_t U_t^T (eigenvalues descending; u1 oriented positive, the Perron direction). For
    every window [tau, k], k = tau + l - 1 (l = `window_s` x fs) and every t in it:
        R_t  = u1_tau^T [u2_t u3_t]                                  (eq. 6, rotation)
        S_t  = [sqrt(lambda1_tau / lambda2_t), sqrt(lambda1_tau / lambda3_t)]   (eq. 7, scale)
        SR_t = (S_t o R_t) [u2_t u3_t]^T                              (eq. 8, back-projection, 1 x 3)
        p    = SR[:, 0] - (sigma(SR[:, 0]) / sigma(SR[:, 1])) SR[:, 1]  (eq. 9)
        P[tau:k] += p - mean(p)                                      (eq. 10, overlap-add)
    The sign of P is arbitrary (eigenvector orientation) and is fixed by `align_polarity` against the
    pixel-mean green trace. Pixels that are NaN throughout are dropped; NaN frames are bridged in time
    and restored. Section 6.3.
    """
    v = np.asarray(patches, dtype=float)
    if v.ndim != 3 or v.shape[2] != 3:
        raise ValueError(f"2SR needs (T, P, 3) per-pixel data, got {v.shape}")
    t_len = v.shape[0]
    keep = ~np.all(np.isnan(v.reshape(t_len, -1)), axis=0).reshape(v.shape[1], 3).any(axis=1)
    v = v[:, keep, :]
    if v.shape[1] < 3:
        raise ValueError("2SR needs at least three pixels (patches or ROI means) with data")
    mask = np.zeros(t_len, dtype=bool)
    for p in range(v.shape[1]):
        for c in range(3):
            v[:, p, c], m = bridge_nans(v[:, p, c])
            mask |= m
    n_pix = v.shape[1]
    cov = np.einsum("tpi,tpj->tij", v, v) / n_pix                         # (T, 3, 3)
    lam, u = np.linalg.eigh(cov)                                           # ascending
    lam = lam[:, ::-1]
    u = u[:, :, ::-1]
    sgn = np.sign(u[:, :, 0].sum(axis=1))
    sgn[sgn == 0] = 1.0
    u[:, :, 0] *= sgn[:, None]
    lam = np.maximum(lam, 1e-18)
    win = min(max(int(round(window_s * fs)), 3), t_len)
    out = np.zeros(t_len)
    u23 = u[:, :, 1:3]                                                     # (T, 3, 2)
    for tau in range(t_len - win + 1):
        k = tau + win
        u1 = u[tau, :, 0]
        r = np.einsum("i,tij->tj", u1, u23[tau:k])                          # (l, 2)
        s = np.sqrt(lam[tau, 0] / lam[tau:k, 1:3])                          # (l, 2)
        sr = np.einsum("tj,tij->ti", s * r, u23[tau:k])                     # (l, 3)
        sd1 = float(np.std(sr[:, 1]))
        p = sr[:, 0] - (float(np.std(sr[:, 0])) / sd1 if sd1 > 1e-18 else 0.0) * sr[:, 1]
        out[tau:k] += p - p.mean()
    rgb_mean = v.mean(axis=1)
    return _finalise(out, rgb_mean, mask, fs, band, align)


# --------------------------------------------------------------------------- dispatcher
def canonical_name(name: str) -> str:
    n = str(name).upper()
    n = ALIASES.get(n, n)
    if n not in METHODS:
        raise ValueError(f"unknown method {name!r}; known: {METHODS}")
    return n


def run_method(name: str, rgb_or_patches, fs: float, cfg, band: tuple[float, float] | None = None,
               align: bool = True, **overrides) -> np.ndarray:
    """Dispatch one classical method on ROI means (T, 3) or patches (T, P, 3) (section 6.3).

    `band` defaults to `pulse.band_rate`; the detrend lambda is `pulse.detrend_lambda`; method constants
    may be overridden in the config (`pulse.chrom_window_s`, `pulse.pos_window_s`, `pulse.ssr_window_s`,
    `pulse.pbv_vector`, `pulse.ica_algorithm`) or by keyword. 2SR requires per-pixel data: pass the patch
    grid (T, P, 3), or stack ROI means as "pixels" and label the result accordingly (see `run.run_pulse`).
    Every other method averages patches over pixels first.
    """
    n = canonical_name(name)
    get = cfg.get if hasattr(cfg, "section") else (lambda k, d=None: _dotted(cfg, k, d))
    band = tuple(band) if band is not None else tuple(get("pulse.band_rate"))
    lam = get("pulse.detrend_lambda", None)
    seed = int(get("study.seed", 0) or 0)
    if n == "GREEN":
        return green(rgb_or_patches, fs, band, lam=overrides.get("lam", lam), align=align)
    if n == "CHROM":
        return chrom(rgb_or_patches, fs, band, window_s=float(overrides.get("window_s", get("pulse.chrom_window_s", CHROM_WINDOW_S))), align=align)
    if n == "POS":
        return pos(rgb_or_patches, fs, band, window_s=float(overrides.get("window_s", get("pulse.pos_window_s", POS_WINDOW_S))), align=align)
    if n == "PBV":
        return pbv(rgb_or_patches, fs, band, pbv_vector=overrides.get("pbv_vector", get("pulse.pbv_vector", PBV_STANDARD)),
                   lam=overrides.get("lam", lam), align=align)
    if n == "ICA":
        return ica(rgb_or_patches, fs, band, lam=overrides.get("lam", lam),
                   algorithm=str(overrides.get("algorithm", get("pulse.ica_algorithm", "jade"))), seed=seed, align=align)
    if n == "PCA":
        return pca(rgb_or_patches, fs, band, lam=overrides.get("lam", lam), align=align)
    if n == "LGI":
        return lgi(rgb_or_patches, fs, band, align=align)
    if n == "OMIT":
        return omit(rgb_or_patches, fs, band, align=align)
    a = np.asarray(rgb_or_patches, dtype=float)
    if a.ndim != 3:
        raise ValueError("2SR needs per-pixel data (T, P, 3): pass the patch grid or a stack of ROI means")
    return ssr(a, fs, band, window_s=float(overrides.get("window_s", get("pulse.ssr_window_s", SSR_WINDOW_S))), align=align)


def run_all(rgb_or_patches, fs: float, cfg, band: tuple[float, float] | None = None,
            methods: Sequence[str] | None = None) -> dict[str, np.ndarray]:
    """Run every method in `methods` (default `pulse.methods`) on the same input; 2SR is skipped on (T, 3)."""
    get = cfg.get if hasattr(cfg, "section") else (lambda k, d=None: _dotted(cfg, k, d))
    names = [canonical_name(m) for m in (methods or get("pulse.methods"))]
    a = np.asarray(rgb_or_patches, dtype=float)
    out = {}
    for m in names:
        if m == "2SR" and a.ndim != 3:
            continue
        out[m] = run_method(m, a, fs, cfg, band=band)
    return out


def _dotted(d: Mapping, key: str, default=None):
    node = d
    for part in key.split("."):
        if isinstance(node, Mapping) and part in node:
            node = node[part]
        else:
            return default
    return node
