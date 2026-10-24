package org.samahealth.onboarding.ecg

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.samahealth.ecgmodel.FounderPrep
import java.io.File
import java.nio.FloatBuffer

/** One label's combined probability, with how the windows were combined. */
data class FounderLabel(val index: Int, val name: String, val rule: String, val prob: Double)

/**
 * What the model said about one strip. [labels] is the rhythm subset in descending probability. This is a
 * research pre-read for the study clinician, never a result for the participant (design section 9).
 */
data class FounderResult(
    val labels: List<FounderLabel>,
    val nWindows: Int,
    val polarityFlipped: Boolean,
    val filtered: Boolean,
    val modelFile: String,
    val notes: List<String>,
)

/**
 * Runs the exported ECGFounder single-lead graph with ONNX Runtime, after the shared preprocessing in
 * :ecg-model. The model file is large, so it is optional: the app works without it and simply offers no
 * pre-read. It is looked for in the APK assets first (the CI model job puts it there) and then in
 * `<externalFilesDir>/model/`, so a phone can be given the file without a new build.
 *
 * Export and parity checks: tools/export_ecgfounder_onnx.py, docs/ecg_model.md.
 */
object FounderOnnx {

    private const val TAG = "FounderOnnx"
    const val ASSET_NAME = "ecgfounder_1lead_fp32.onnx"
    private const val INPUT = "ecg"
    private const val OUTPUT_PROBS = "probs"

    /** The rhythm subset of the 150 outputs (palmppg/ecg/founder_prep.py RHYTHM_LABELS). */
    val RHYTHM_LABELS: Map<Int, String> = linkedMapOf(
        1 to "NORMAL SINUS RHYTHM", 3 to "SINUS RHYTHM", 4 to "SINUS BRADYCARDIA",
        5 to "ATRIAL FIBRILLATION", 6 to "SINUS TACHYCARDIA", 9 to "PREMATURE VENTRICULAR COMPLEXES",
        16 to "PREMATURE ATRIAL COMPLEXES", 19 to "PREMATURE SUPRAVENTRICULAR COMPLEXES",
        32 to "ATRIAL FLUTTER", 33 to "MARKED SINUS BRADYCARDIA", 34 to "WITH SINUS ARRHYTHMIA",
        39 to "UNDETERMINED RHYTHM", 49 to "JUNCTIONAL RHYTHM", 79 to "WITH 1ST DEGREE AV BLOCK",
        91 to "IN A PATTERN OF BIGEMINY", 93 to "SUPRAVENTRICULAR TACHYCARDIA",
        98 to "VENTRICULAR TACHYCARDIA", 142 to "WITH SINUS PAUSE",
    )

    @Volatile private var env: OrtEnvironment? = null
    @Volatile private var session: OrtSession? = null
    @Volatile private var loadedFrom: String? = null

    /** Where the model file is, or null when this phone does not carry one. */
    fun modelLocation(context: Context): String? {
        val external = File(context.getExternalFilesDir(null), "model/$ASSET_NAME")
        if (external.isFile && external.length() > 0) return external.absolutePath
        return try {
            context.assets.open(ASSET_NAME).use { }
            "asset:$ASSET_NAME"
        } catch (e: Exception) {
            null
        }
    }

    fun isAvailable(context: Context): Boolean = modelLocation(context) != null

    private fun open(context: Context): OrtSession? {
        session?.let { return it }
        synchronized(this) {
            session?.let { return it }
            val where = modelLocation(context) ?: return null
            return try {
                val e = env ?: OrtEnvironment.getEnvironment().also { env = it }
                val opts = OrtSession.SessionOptions().apply { setIntraOpNumThreads(2) }
                val s = if (where.startsWith("asset:")) {
                    context.assets.open(ASSET_NAME).use { input -> e.createSession(input.readBytes(), opts) }
                } else {
                    e.createSession(where, opts)
                }
                loadedFrom = where
                session = s
                s
            } catch (e: Throwable) {
                Log.w(TAG, "the model could not be loaded from $where", e)
                null
            }
        }
    }

    /** Frees the session; the next call reloads it. */
    fun close() {
        synchronized(this) {
            runCatching { session?.close() }
            session = null
        }
    }

    /**
     * Runs the strip through preprocessing and the model. Returns null when this phone carries no model file or
     * the strip is too short for a single 10 s window.
     */
    suspend fun run(context: Context, mv: DoubleArray, fs: Double, filtered: Boolean = true): FounderResult? =
        withContext(Dispatchers.Default) {
            val s = open(context) ?: return@withContext null
            val w = FounderPrep.preprocess(mv, fs, filtered = filtered)
            if (w.n == 0) {
                return@withContext FounderResult(
                    emptyList(), 0, w.polarityFlipped, filtered, loadedFrom ?: "?", w.notes,
                )
            }
            val probs = try {
                infer(s, w)
            } catch (e: Throwable) {
                Log.w(TAG, "inference failed", e)
                return@withContext null
            }
            val combined = FounderPrep.combineWindows(probs)
            val labels = RHYTHM_LABELS.entries
                .filter { it.key < combined.size }
                .map { (i, name) -> FounderLabel(i, name, FounderPrep.combineRule(i), combined[i]) }
                .sortedByDescending { it.prob }
            FounderResult(labels, w.n, w.polarityFlipped, filtered, loadedFrom ?: "?", w.notes)
        }

    /** (n, 150) sigmoid probabilities for the prepared windows. */
    private fun infer(s: OrtSession, w: FounderPrep.Windows): Array<DoubleArray> {
        val e = env ?: OrtEnvironment.getEnvironment().also { env = it }
        val flat = w.toFloatArray()
        val shape = longArrayOf(w.n.toLong(), 1L, FounderPrep.WIN.toLong())
        OnnxTensor.createTensor(e, FloatBuffer.wrap(flat), shape).use { tensor ->
            s.run(mapOf(INPUT to tensor)).use { out ->
                val name = if (out.any { it.key == OUTPUT_PROBS }) OUTPUT_PROBS else out.first().key
                @Suppress("UNCHECKED_CAST")
                val raw = out.get(name).get().value as Array<FloatArray>
                return Array(raw.size) { i -> DoubleArray(raw[i].size) { j -> raw[i][j].toDouble() } }
            }
        }
    }
}
