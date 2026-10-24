package org.samahealth.quality

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * A rule-based quality grade (design contract section 4). [level] is "good" | "borderline" | "retake"; [reasons] are
 * short plain-English strings for the operator; [metrics] keep the numbers behind them (null when not measurable,
 * flags as 1.0 / 0.0). Python twin: palmppg/quality/onsite.py, pinned by configs/quality_fixtures.
 */
data class Grade(val level: String, val reasons: List<String>, val metrics: Map<String, Double?>)

/** One row per analysis frame of `<clip>_roi.csv`; [tS] in seconds from the first row; [grid] is 9 x n luma or null. */
class RoiSeries(
    val tS: DoubleArray,
    val r: DoubleArray,
    val g: DoubleArray,
    val b: DoubleArray,
    val y: DoubleArray,
    val clipFrac: DoubleArray,
    val grid: Array<DoubleArray>?,
)

/** A lead-I ECG in millivolts at [fs] Hz; Kardia PDF page fields are filled when the reader found them. */
data class EcgTrace(
    val fs: Double,
    val mv: DoubleArray,
    val warnings: List<String>,
    val determination: String? = null,
    val hrBpm: Int? = null,
    val enhancedFilter: Boolean? = null,
    val mainsHz: Int? = null,
)

/**
 * Participant-facing rhythm summary. [rhythm] is "regular" | "irregular" | "insufficient"; "irregular" means the beat
 * spacing varied (a screening heuristic for clinician review), never a rhythm name. [sentences] end with [CLOSING].
 */
data class RhythmSummary(
    val hrBpm: Double?,
    val rhythm: String,
    val inverted: Boolean,
    val nBeats: Int,
    val rrMinS: Double?,
    val rrMaxS: Double?,
    val irregularFlag: Boolean,
    val sentences: List<String>,
) {
    val text: String get() = sentences.joinToString(" ")

    companion object {
        const val CLOSING = "This is not a medical opinion. A study doctor reviews every recording."
    }
}

/** PROVISIONAL video thresholds, to be calibrated on pilot clips (as DECISIONS D-008). */
data class VideoQualityConfig(
    val minDurationFrac: Double = 0.9,        // retake: duration < 0.9 x the clip length asked for
    val minMeanLevel: Double = 25.0,          // retake: median Y below this (torch off, palm off the lens)
    val darkLevel: Double = 20.0,             // a row with Y below this counts as dark
    val maxDarkFrac: Double = 0.2,
    val retakeClippedFrac: Double = 0.25,
    val retakeDroppedFrac: Double = 0.05,
    val retakeSnrDb: Double = -3.0,           // de Haan & Jeanne 2013 SNR
    val borderlineSnrDb: Double = 1.5,
    val borderlineClippedFrac: Double = 0.05,
    val borderlineMotion: Double = 0.02,
    val borderlineDroppedFrac: Double = 0.01,
    val maxRefHrDiffBpm: Double = 8.0,
    val resampleHz: Double = 30.0,
    val posWindowS: Double = 1.6,             // Wang et al. 2017
    val pulseLoHz: Double = 0.7,
    val pulseHiHz: Double = 3.5,
    val snrLoHz: Double = 0.5,
    val snrHiHz: Double = 4.0,
    val snrF0HalfwidthHz: Double = 0.1,
    val snrH2HalfwidthHz: Double = 0.2,
)

/** PROVISIONAL ECG thresholds, to be calibrated on pilot clips (as DECISIONS D-008). */
data class EcgQualityConfig(
    val minDurationS: Double = 20.0,
    val retakeFlatFrac: Double = 0.3,
    val minBeats: Int = 8,
    val retakeTemplateCorr: Double = 0.5,
    val retakeHrLo: Double = 30.0,
    val retakeHrHi: Double = 220.0,
    val borderlineTemplateCorr: Double = 0.66,  // Orphanidou et al. 2015
    val minKsqi: Double = 5.0,                  // Clifford et al. 2012 (Pearson kurtosis, Gaussian = 3)
    val maxRrS: Double = 3.0,
    val borderlineHrLo: Double = 40.0,
    val borderlineHrHi: Double = 180.0,
    val borderlineFlatFrac: Double = 0.1,
    val maxRrRatio: Double = 2.2,               // skipped when the irregular flag is set
    val flatPtpMv: Double = 0.05,
    val bandLoHz: Double = 0.5,
    val bandHiHz: Double = 40.0,
    val irregularRmssdRatio: Double = 0.1,      // Dash et al. 2009
    val irregularShannon: Double = 0.7,
    val minRrForRhythm: Int = 8,
)

/** Decimal text of [x] rounded half away from zero to [nd] places; the Python reference prints the same digits. */
internal fun fmt(x: Double, nd: Int): String = BigDecimal(x + 0.0).setScale(nd, RoundingMode.HALF_UP).toPlainString()
