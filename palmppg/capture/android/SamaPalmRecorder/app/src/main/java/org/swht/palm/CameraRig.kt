package org.swht.palm

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.graphics.Rect
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CameraMetadata
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.CaptureResult
import android.hardware.camera2.TotalCaptureResult
import android.hardware.camera2.params.ColorSpaceTransform
import android.hardware.camera2.params.MeteringRectangle
import android.hardware.camera2.params.RggbChannelVector
import android.hardware.camera2.params.TonemapCurve
import android.os.Build
import android.os.SystemClock
import android.util.Log
import android.util.Range
import android.util.Size
import android.widget.ImageView
import androidx.camera.camera2.interop.Camera2CameraControl
import androidx.camera.camera2.interop.Camera2CameraInfo
import androidx.camera.camera2.interop.Camera2Interop
import androidx.camera.camera2.interop.CaptureRequestOptions
import androidx.camera.camera2.interop.ExperimentalCamera2Interop
import androidx.camera.core.Camera
import androidx.camera.core.CameraFilter
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.FallbackStrategy
import androidx.camera.video.FileOutputOptions
import androidx.camera.video.Quality
import androidx.camera.video.QualitySelector
import androidx.camera.video.Recorder
import androidx.camera.video.Recording
import androidx.camera.video.VideoCapture
import androidx.camera.video.VideoRecordEvent
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedWriter
import java.io.File
import java.io.FileWriter
import java.util.concurrent.Executors

/**
 * The phone leg of the capture: a 1080p30 clip with every automatic control pinned, a per-frame
 * timestamp and control log on the study reference clock, and a pre-encoder palm-ROI colour trace
 * written *during* the clip, not only between clips.
 *
 * Why the controls are pinned (protocol section 5): auto-exposure, auto white balance, autofocus
 * and stabilisation all modulate pixel values frame to frame. That modulation lands in the same
 * band as the pulse and is indistinguishable from it afterwards, so a clip recorded with any of
 * them running is not recoverable by processing. The arithmetic lives in [PalmControls]; this
 * class only sends it to the camera and reports what the camera actually did.
 *
 * What changed from the first build, and why, each traced to a clip recorded on the OnePlus 12:
 *
 * - **Focus is fixed, never searched.** Continuous AF was left running until the lock, and the
 *   lock pinned wherever the lens happened to be at t = 2 s. On a textureless palm that is a
 *   random point of a hunt, which is what "sometimes blurry" looks like. Now `CONTROL_AF_MODE_OFF`
 *   with `LENS_FOCUS_DISTANCE` for the rig distance is in the very first request, so there is no
 *   hunt to catch mid-sweep and nothing for the operator to watch refocus on screen.
 * - **The main sensor is selected by id.** `DEFAULT_BACK_CAMERA` is logical camera 0, which fuses
 *   the main (id 2, closest focus 13 cm) and the ultrawide (id 3, 4 cm). At palm distance the HAL
 *   is free to hand off between them, and the result keys do not report when it does. Binding
 *   the main sensor directly, with zoom pinned at 1.0, removes the possibility.
 * - **Exposure is metered on the ROI and checked before the clip.** Every clip recorded before
 *   this had a near-black ROI (mean Y of 2-11 out of 255) and the app said nothing, because the
 *   live readout is unbound the moment REC is pressed. The readout now runs through the clip.
 * - **The tone curve is sent, not inherited.** The ingest inverts sRGB; the vendor's `FAST` curve
 *   is not sRGB and cannot be recovered. An explicit 64-point sRGB curve makes the inversion exact.
 * - **White balance is frozen as numbers.** `AWB_LOCK` holds whatever the settle reached and does
 *   not say what that was. The settled gains and transform are read back and re-sent as manual
 *   colour correction, and both land in the clip metadata for cross-session normalisation.
 */
@OptIn(ExperimentalCamera2Interop::class)
class CameraRig(
    private val context: Context,
    private val previewView: PreviewView,
    /** Shown in RECORD mode in place of the camera preview, fed from the analysis stream. */
    private val softPreview: ImageView? = null,
) {

    companion object {
        private const val TAG = "CameraRig"
        /** Side of the centred measurement ROI as a fraction of the frame. Shared with [RoiOverlay]. */
        const val ROI_FRACTION = 0.40f
        private const val TARGET_FPS = 30
        /** Protocol section 5 requires 1080p; anything shorter is a failed clip, not a lesser one. */
        private const val MIN_VIDEO_SHORT_SIDE = 1080
        /** OnePlus 12 main sensor (Sony LYT-808, 6.06 mm f/1.6, closest focus 13 cm). */
        const val PREFERRED_PHYSICAL_ID = "2"
        /** Protocol asks for the highest bitrate the encoder offers; it clamps what it cannot do. */
        private const val TARGET_BITRATE = 100_000_000
        private const val SOFT_PREVIEW_EVERY = 3
    }

    enum class Mode { MONITOR, RECORD }

    private val analysisExecutor = Executors.newSingleThreadExecutor()
    private var camera: Camera? = null
    private var videoCapture: VideoCapture<Recorder>? = null
    private var activeRecording: Recording? = null

    // ---- operator settings ----
    /** Rig distance from lens to palm. Applied at the next bind; see [PalmControls.DISTANCE_PRESETS_CM]. */
    @Volatile var distanceCm = PalmControls.DEFAULT_DISTANCE_CM

    // ---- what was bound ----
    @Volatile var mode = Mode.MONITOR; private set
    var clock: ClockBridge? = null; private set
    @Volatile var analysisBound = false; private set
    @Volatile var videoResolution = "unknown"; private set
    @Volatile var previewResolution = "unknown"; private set
    @Volatile var analysisResolution = "unknown"; private set
    /** Width over height of the frame as it appears on the portrait screen, for [RoiOverlay]. */
    @Volatile var previewDisplayAspect = 0f; private set
    @Volatile var cameraId = "?"; private set
    @Volatile var cameraSelection = "none"; private set
    @Volatile var hardwareLevel = "unknown"; private set
    @Volatile var manualSensorSupported = false; private set
    @Volatile var manualPostProcessingSupported = false; private set
    @Volatile var minimumFocusDistance: Float? = null; private set
    @Volatile var focusCalibration = "unknown"; private set
    @Volatile var isoRange: IntRange = 100..6400; private set
    @Volatile var exposureRange: LongRange = 100_000L..100_000_000L; private set
    @Volatile var focus = PalmControls.focusFor(PalmControls.DEFAULT_DISTANCE_CM, null); private set
    private var activeArray: Rect? = null

    // ---- latest capture result ----
    @Volatile var lastIso = -1; private set
    @Volatile var lastExposureNs = -1L; private set
    @Volatile var lastFocusDistance = -1f; private set
    @Volatile var lastLensState = -1; private set
    @Volatile var lastFlashState = -1; private set
    @Volatile var lastAeMode = -1; private set
    @Volatile var lastAfMode = -1; private set
    @Volatile var lastAwbMode = -1; private set
    @Volatile var lastTonemapMode = -1; private set
    @Volatile var lastShadingMode = -1; private set
    @Volatile var lastAberrationMode = -1; private set
    @Volatile var lastZoom = -1f; private set
    @Volatile private var lastGains: RggbChannelVector? = null
    @Volatile private var lastTransform: ColorSpaceTransform? = null
    @Volatile var resultFps = 0f; private set
    private var lastResultTs = -1L

    // ---- what the lock did ----
    @Volatile var lockApplied = "none"; private set
    @Volatile var awbApplied = "none"; private set
    @Volatile var requestedExposure: PalmControls.Exposure? = null; private set
    @Volatile var settledExposure: PalmControls.Exposure? = null; private set
    @Volatile var lockedGains: RggbChannelVector? = null; private set
    @Volatile var lockedTransform: ColorSpaceTransform? = null; private set
    @Volatile var preflight: PalmControls.Verdict? = null; private set

    // ---- logs ----
    @Volatile var frameRows = 0L; private set
    @Volatile var roiRows = 0L; private set
    @Volatile var droppedFrameRows = 0L; private set
    @Volatile var recordingStartRefNs = 0L; private set
    private val framesLock = Any()
    private var framesCsv: BufferedWriter? = null
    private var controlsCsv: BufferedWriter? = null
    private val roiLock = Any()
    private var roiCsv: BufferedWriter? = null
    @Volatile private var recording = false

    // ---- live ROI ----
    /** ~6 s of detrended ROI luma for the on-screen trace, with the detected beats beside it. */
    val ppgRing = FloatArray(6 * TARGET_FPS)
    val peakRing = BooleanArray(6 * TARGET_FPS)
    @Volatile var ppgWriteIdx = 0; private set
    /** Mean Y over the ROI of the latest analysis frame, 0-255. */
    @Volatile var roiLuma = Float.NaN; private set
    @Volatile var roiClipFraction = Float.NaN; private set
    @Volatile var analysisFps = 0f; private set
    private var lastAnalysisTs = -1L
    private var analysisCount = 0L
    val pulse = PulseMeter()

    init {
        readStaticCharacteristics()
    }

    // ---- characteristics, before any bind ----

    /**
     * Reads the limits [PalmControls] needs from the sensor this rig intends to use, so the fixed
     * focus can be in the first request rather than applied after a bind has already started a
     * hunt. Falls back to the first back camera if the preferred id is not openable.
     */
    private fun readStaticCharacteristics() {
        val cm = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
        val ids = try { cm.cameraIdList.toList() } catch (e: Exception) { Log.e(TAG, "camera list", e); emptyList() }
        val id = ids.firstOrNull { it == PREFERRED_PHYSICAL_ID } ?: ids.firstOrNull {
            try {
                cm.getCameraCharacteristics(it).get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK
            } catch (_: Exception) { false }
        } ?: return
        try {
            applyCharacteristics(cm.getCameraCharacteristics(id))
        } catch (e: Exception) {
            Log.e(TAG, "characteristics for $id", e)
        }
    }

    private fun applyCharacteristics(c: CameraCharacteristics) {
        hardwareLevel = when (c.get(CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL)) {
            CameraMetadata.INFO_SUPPORTED_HARDWARE_LEVEL_LEGACY -> "LEGACY"
            CameraMetadata.INFO_SUPPORTED_HARDWARE_LEVEL_LIMITED -> "LIMITED"
            CameraMetadata.INFO_SUPPORTED_HARDWARE_LEVEL_FULL -> "FULL"
            CameraMetadata.INFO_SUPPORTED_HARDWARE_LEVEL_3 -> "LEVEL_3"
            CameraMetadata.INFO_SUPPORTED_HARDWARE_LEVEL_EXTERNAL -> "EXTERNAL"
            else -> "unknown"
        }
        val caps = c.get(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES) ?: intArrayOf()
        manualSensorSupported = caps.contains(CameraMetadata.REQUEST_AVAILABLE_CAPABILITIES_MANUAL_SENSOR)
        manualPostProcessingSupported = caps.contains(CameraMetadata.REQUEST_AVAILABLE_CAPABILITIES_MANUAL_POST_PROCESSING)
        minimumFocusDistance = c.get(CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE)
        focusCalibration = when (c.get(CameraCharacteristics.LENS_INFO_FOCUS_DISTANCE_CALIBRATION)) {
            CameraMetadata.LENS_INFO_FOCUS_DISTANCE_CALIBRATION_CALIBRATED -> "CALIBRATED"
            CameraMetadata.LENS_INFO_FOCUS_DISTANCE_CALIBRATION_APPROXIMATE -> "APPROXIMATE"
            CameraMetadata.LENS_INFO_FOCUS_DISTANCE_CALIBRATION_UNCALIBRATED -> "UNCALIBRATED"
            else -> "unknown"
        }
        c.get(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE)?.let { isoRange = it.lower..it.upper }
        c.get(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE)?.let { exposureRange = it.lower..it.upper }
        activeArray = c.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE)
        clock = ClockBridge(c.get(CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE)).also { it.measure() }
        focus = PalmControls.focusFor(distanceCm, minimumFocusDistance)
    }

    /** Centre-ROI metering rectangle on the active array, for the 16:9 field the clip records. */
    private fun roiMeteringRegion(): MeteringRectangle? {
        val a = activeArray ?: return null
        val w = a.width().toFloat()
        val cropH = minOf(a.height().toFloat(), w * 9f / 16f)
        val cx = a.left + w / 2f
        val cy = a.top + a.height() / 2f
        val half = ROI_FRACTION / 2f
        val l = (cx - half * w).toInt()
        val t = (cy - half * cropH).toInt()
        val r = (cx + half * w).toInt()
        val b = (cy + half * cropH).toInt()
        return MeteringRectangle(l, t, r - l, b - t, MeteringRectangle.METERING_WEIGHT_MAX)
    }

    // ---- the request options every stream carries ----

    /**
     * Everything that is fixed for the whole session, settle included. Set on every bound use
     * case so the merged repeating request carries them whichever streams are present.
     */
    private fun <T> applyStaticOptions(ext: Camera2Interop.Extender<T>) {
        for ((key, value) in staticOptions()) {
            @Suppress("UNCHECKED_CAST")
            ext.setCaptureRequestOption(key as CaptureRequest.Key<Any>, value)
        }
    }

    private fun staticOptions(): List<Pair<CaptureRequest.Key<*>, Any>> {
        focus = PalmControls.focusFor(distanceCm, minimumFocusDistance)
        val curve = PalmControls.srgbCurve()
        val opts = mutableListOf<Pair<CaptureRequest.Key<*>, Any>>(
            CaptureRequest.CONTROL_MODE to CameraMetadata.CONTROL_MODE_AUTO,
            CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE to Range(TARGET_FPS, TARGET_FPS),
            CaptureRequest.CONTROL_SCENE_MODE to CameraMetadata.CONTROL_SCENE_MODE_DISABLED,
            CaptureRequest.CONTROL_VIDEO_STABILIZATION_MODE to CameraMetadata.CONTROL_VIDEO_STABILIZATION_MODE_OFF,
            CaptureRequest.LENS_OPTICAL_STABILIZATION_MODE to CameraMetadata.LENS_OPTICAL_STABILIZATION_MODE_OFF,
            CaptureRequest.NOISE_REDUCTION_MODE to CameraMetadata.NOISE_REDUCTION_MODE_OFF,
            CaptureRequest.EDGE_MODE to CameraMetadata.EDGE_MODE_OFF,
            // Fixed focus from the first frame: no hunt, nothing to catch mid-sweep.
            CaptureRequest.CONTROL_AF_MODE to CameraMetadata.CONTROL_AF_MODE_OFF,
            CaptureRequest.LENS_FOCUS_DISTANCE to focus.appliedDiopters,
        )
        if (manualPostProcessingSupported) {
            opts += CaptureRequest.TONEMAP_MODE to CameraMetadata.TONEMAP_MODE_CONTRAST_CURVE
            opts += CaptureRequest.TONEMAP_CURVE to TonemapCurve(curve, curve, curve)
            opts += CaptureRequest.SHADING_MODE to CameraMetadata.SHADING_MODE_OFF
            opts += CaptureRequest.COLOR_CORRECTION_ABERRATION_MODE to CameraMetadata.COLOR_CORRECTION_ABERRATION_MODE_OFF
        } else {
            opts += CaptureRequest.TONEMAP_MODE to CameraMetadata.TONEMAP_MODE_FAST
        }
        if (Build.VERSION.SDK_INT >= 30) {
            opts += CaptureRequest.CONTROL_ZOOM_RATIO to 1.0f
        }
        roiMeteringRegion()?.let { opts += CaptureRequest.CONTROL_AE_REGIONS to arrayOf(it) }
        return opts
    }

    // ---- camera choice ----

    private fun selectors(provider: ProcessCameraProvider): List<Pair<CameraSelector, String>> {
        val out = mutableListOf<Pair<CameraSelector, String>>()
        val direct = CameraSelector.Builder()
            .requireLensFacing(CameraSelector.LENS_FACING_BACK)
            .addCameraFilter(CameraFilter { infos ->
                infos.filter { Camera2CameraInfo.from(it).cameraId == PREFERRED_PHYSICAL_ID }
            })
            .build()
        val directOk = try { provider.hasCamera(direct) } catch (_: Exception) { false }
        if (directOk) out += direct to "direct:$PREFERRED_PHYSICAL_ID"
        out += CameraSelector.Builder()
            .requireLensFacing(CameraSelector.LENS_FACING_BACK)
            .setPhysicalCameraId(PREFERRED_PHYSICAL_ID)
            .build() to "logical_back:physical=$PREFERRED_PHYSICAL_ID"
        out += CameraSelector.DEFAULT_BACK_CAMERA to "default_back(logical, may hand off sensors)"
        return out
    }

    // ---- binding ----

    /**
     * Measured on this OnePlus 12 (LEVEL_3): Preview + VideoCapture + ImageAnalysis together force
     * the encoder to 720p — three streams is the limit, not a resolution budget. The first build
     * dropped ImageAnalysis for the clip and lost the readout exactly when it mattered. This one
     * drops the *Preview* instead: VideoCapture + ImageAnalysis, with the analysis frames painted
     * into [softPreview] so the operator still sees the palm. If even two streams negotiate below
     * 1080p the rig falls back to Preview + VideoCapture and says so in the metadata.
     */
    fun bind(owner: LifecycleOwner, mode: Mode, onReady: (Boolean) -> Unit) {
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener({
            val provider = try { future.get() } catch (e: Exception) {
                Log.e(TAG, "camera provider failed", e); onReady(false); return@addListener
            }
            provider.unbindAll()
            pulse.reset()
            ppgRing.fill(0f); peakRing.fill(false)
            roiLuma = Float.NaN; roiClipFraction = Float.NaN

            var bound = false
            for ((selector, label) in selectors(provider)) {
                bound = try {
                    if (mode == Mode.RECORD) bindRecord(owner, provider, selector) else bindMonitor(owner, provider, selector)
                    true
                } catch (e: Exception) {
                    Log.w(TAG, "bind $mode via $label failed: ${e.message}"); provider.unbindAll(); false
                }
                if (bound) { cameraSelection = label; break }
            }
            val cam = camera
            if (!bound || cam == null) { onReady(false); return@addListener }

            this.mode = mode
            val c2 = Camera2CameraInfo.from(cam.cameraInfo)
            cameraId = c2.cameraId
            // The bound camera is the authority on its own limits, logical or not.
            try { applyCharacteristicsFromInfo(c2) } catch (e: Exception) { Log.w(TAG, "info characteristics", e) }
            Log.i(TAG, "bound $mode via $cameraSelection (id $cameraId): preview=$previewResolution " +
                "video=$videoResolution analysis=$analysisResolution focus=${focus.appliedDiopters}D " +
                "(${PalmControls.centimetres(focus.appliedDiopters)} cm, clamped=${focus.clampedToLens})")
            onReady(true)
        }, ContextCompat.getMainExecutor(context))
    }

    private fun applyCharacteristicsFromInfo(c2: Camera2CameraInfo) {
        c2.getCameraCharacteristic(CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE)?.let { minimumFocusDistance = it }
        c2.getCameraCharacteristic(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE)?.let { isoRange = it.lower..it.upper }
        c2.getCameraCharacteristic(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE)?.let { exposureRange = it.lower..it.upper }
        val source = c2.getCameraCharacteristic(CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE)
        if (clock == null || clock?.sourceName != ClockBridge(source).sourceName) clock = ClockBridge(source).also { it.measure() }
        focus = PalmControls.focusFor(distanceCm, minimumFocusDistance)
    }

    private fun previewUseCase(withCallback: Boolean): Preview {
        val b = Preview.Builder()
        Camera2Interop.Extender(b).apply {
            applyStaticOptions(this)
            if (withCallback) setSessionCaptureCallback(frameCallback)
        }
        return b.build().also { it.surfaceProvider = previewView.surfaceProvider }
    }

    private fun analysisUseCase(withCallback: Boolean): ImageAnalysis {
        val b = ImageAnalysis.Builder()
            .setResolutionSelector(
                ResolutionSelector.Builder()
                    // 16:9 so the analysis frame covers the same field as the 1080p clip and the
                    // centred ROI is the same physical patch of palm in both.
                    .setAspectRatioStrategy(AspectRatioStrategy.RATIO_16_9_FALLBACK_AUTO_STRATEGY)
                    .setResolutionStrategy(ResolutionStrategy(Size(640, 360), ResolutionStrategy.FALLBACK_RULE_CLOSEST_LOWER_THEN_HIGHER))
                    .build()
            )
            .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
        Camera2Interop.Extender(b).apply {
            applyStaticOptions(this)
            if (withCallback) setSessionCaptureCallback(frameCallback)
        }
        return b.build().also { it.setAnalyzer(analysisExecutor, ::analyse) }
    }

    private fun videoUseCase(): VideoCapture<Recorder> {
        val recorder = Recorder.Builder()
            .setQualitySelector(QualitySelector.from(Quality.FHD, FallbackStrategy.higherQualityOrLowerThan(Quality.FHD)))
            .setTargetVideoEncodingBitRate(TARGET_BITRATE)
            .build()
        val b = VideoCapture.Builder(recorder)
        Camera2Interop.Extender(b).apply { applyStaticOptions(this) }
        return b.build()
    }

    private fun bindMonitor(owner: LifecycleOwner, provider: ProcessCameraProvider, selector: CameraSelector) {
        val preview = previewUseCase(withCallback = true)
        val analysis = analysisUseCase(withCallback = false)
        videoCapture = null
        camera = provider.bindToLifecycle(owner, selector, preview, analysis)
        analysisBound = true
        softPreview?.post { softPreview.visibility = android.view.View.GONE }
        videoResolution = "monitoring"
        previewResolution = preview.attachedSurfaceResolution?.let { "${it.width}x${it.height}" } ?: "unknown"
        analysisResolution = analysis.attachedSurfaceResolution?.let { "${it.width}x${it.height}" } ?: "unknown"
        preview.attachedSurfaceResolution?.let { previewDisplayAspect = minOf(it.width, it.height).toFloat() / maxOf(it.width, it.height) }
    }

    private fun bindRecord(owner: LifecycleOwner, provider: ProcessCameraProvider, selector: CameraSelector) {
        // Two streams: the clip and the ROI tap. The preview is painted from the tap.
        var vc = videoUseCase()
        val analysis = analysisUseCase(withCallback = true)
        camera = provider.bindToLifecycle(owner, selector, vc, analysis)
        var short = vc.attachedSurfaceResolution?.let { minOf(it.width, it.height) } ?: -1
        if (short in 1 until MIN_VIDEO_SHORT_SIDE) {
            Log.w(TAG, "video+analysis negotiated ${short}p; rebinding preview+video without the ROI tap")
            provider.unbindAll()
            vc = videoUseCase()
            val preview = previewUseCase(withCallback = true)
            camera = provider.bindToLifecycle(owner, selector, preview, vc)
            analysisBound = false
            softPreview?.post { softPreview.visibility = android.view.View.GONE }
            previewResolution = preview.attachedSurfaceResolution?.let { "${it.width}x${it.height}" } ?: "unknown"
            analysisResolution = "dropped_for_1080p"
            preview.attachedSurfaceResolution?.let { previewDisplayAspect = minOf(it.width, it.height).toFloat() / maxOf(it.width, it.height) }
            short = vc.attachedSurfaceResolution?.let { minOf(it.width, it.height) } ?: -1
        } else {
            analysisBound = true
            softPreview?.post { softPreview.visibility = android.view.View.VISIBLE }
            previewResolution = "soft_from_analysis"
            analysisResolution = analysis.attachedSurfaceResolution?.let { "${it.width}x${it.height}" } ?: "unknown"
            analysis.attachedSurfaceResolution?.let { previewDisplayAspect = minOf(it.width, it.height).toFloat() / maxOf(it.width, it.height) }
        }
        videoCapture = vc
        videoResolution = vc.attachedSurfaceResolution?.let { "${it.width}x${it.height}" } ?: "unknown"
        if (short in 1 until MIN_VIDEO_SHORT_SIDE) Log.w(TAG, "encoder negotiated ${short}p, below the protocol minimum")
    }

    fun setTorch(on: Boolean) {
        camera?.cameraControl?.enableTorch(on)
    }

    // ---- lock ----

    /** Snapshot of the settled state for [PalmControls.preflight]. */
    fun reading(torchRequested: Boolean): PalmControls.Reading = PalmControls.Reading(
        roiLuma = roiLuma.takeIf { !it.isNaN() && analysisBound },
        clipFraction = roiClipFraction.takeIf { !it.isNaN() && analysisBound },
        fps = resultFps.takeIf { it > 0f },
        exposureNs = lastExposureNs,
        iso = lastIso,
        focusRequestedDiopters = focus.appliedDiopters,
        focusReportedDiopters = lastFocusDistance.takeIf { it >= 0f },
        torchRequested = torchRequested,
        torchLit = when (lastFlashState) {
            CameraMetadata.FLASH_STATE_FIRED -> true
            CameraMetadata.FLASH_STATE_READY, CameraMetadata.FLASH_STATE_UNAVAILABLE -> false
            else -> null
        },
        perfusionPct = pulse.perfusionPct.takeIf { analysisBound && analysisCount > TARGET_FPS },
    )

    /**
     * Pins exposure, white balance and (again) focus at the settled values, after one proportional
     * exposure correction if the pre-flight asked for it. Returns what was actually applied, which
     * goes into the clip metadata as `lock_applied` / `awb_applied`.
     */
    fun lockControls(torchRequested: Boolean): String {
        val control = camera?.cameraControl ?: return "no camera"
        val verdict = PalmControls.preflight(reading(torchRequested)).also { preflight = it }
        val b = CaptureRequestOptions.Builder()
        for ((key, value) in staticOptions()) {
            @Suppress("UNCHECKED_CAST")
            b.setCaptureRequestOption(key as CaptureRequest.Key<Any>, value)
        }

        val settled = PalmControls.Exposure(lastExposureNs, lastIso, capped = false, isoSaturated = false)
        settledExposure = settled
        var exp = PalmControls.capExposure(lastExposureNs, lastIso, isoRange, exposureRange)
        val luma = roiLuma
        if (verdict.exposureCorrection != null && !luma.isNaN()) {
            exp = PalmControls.correctExposure(exp, luma, isoRange, exposureRange)
        }
        requestedExposure = exp

        lockApplied = if (manualSensorSupported && exp.iso > 0 && exp.exposureNs > 0) {
            b.setCaptureRequestOption(CaptureRequest.CONTROL_AE_MODE, CameraMetadata.CONTROL_AE_MODE_OFF)
            b.setCaptureRequestOption(CaptureRequest.SENSOR_SENSITIVITY, exp.iso)
            b.setCaptureRequestOption(CaptureRequest.SENSOR_EXPOSURE_TIME, exp.exposureNs)
            b.setCaptureRequestOption(CaptureRequest.SENSOR_FRAME_DURATION, 1_000_000_000L / TARGET_FPS)
            "manual_sensor" + (if (exp.capped) "+exposure_capped" else "") + (if (verdict.exposureCorrection != null) "+roi_corrected" else "")
        } else {
            b.setCaptureRequestOption(CaptureRequest.CONTROL_AE_LOCK, true)
            "ae_lock"
        }

        val gains = lastGains
        val transform = lastTransform
        awbApplied = if (manualPostProcessingSupported && gains != null && transform != null) {
            b.setCaptureRequestOption(CaptureRequest.CONTROL_AWB_MODE, CameraMetadata.CONTROL_AWB_MODE_OFF)
            b.setCaptureRequestOption(CaptureRequest.COLOR_CORRECTION_MODE, CameraMetadata.COLOR_CORRECTION_MODE_TRANSFORM_MATRIX)
            b.setCaptureRequestOption(CaptureRequest.COLOR_CORRECTION_GAINS, gains)
            b.setCaptureRequestOption(CaptureRequest.COLOR_CORRECTION_TRANSFORM, transform)
            lockedGains = gains; lockedTransform = transform
            "manual_gains_from_settle"
        } else {
            b.setCaptureRequestOption(CaptureRequest.CONTROL_AWB_LOCK, true)
            "awb_lock"
        }
        lockApplied += "+af_off_fixed"
        Camera2CameraControl.from(control).setCaptureRequestOptions(b.build())
        Log.i(TAG, "lock: $lockApplied / $awbApplied; ${verdict.line}; exposure ${settled.exposureNs}ns@${settled.iso} -> ${exp.exposureNs}ns@${exp.iso}")
        return lockApplied
    }

    /**
     * Torch under manual exposure: Camera2 lets `FLASH_MODE_TORCH` drive the LED with AE off, but
     * a vendor HAL may not. If the flash state says the torch went out when AE went manual, fall
     * back to AE lock (AE stays on, so the torch does) and say so in `lock_applied`.
     */
    fun torchFellBackToAeLock(torchRequested: Boolean): Boolean {
        if (!torchRequested || !lockApplied.startsWith("manual_sensor")) return false
        if (lastFlashState == CameraMetadata.FLASH_STATE_FIRED || lastFlashState < 0) return false
        val control = camera?.cameraControl ?: return false
        val b = CaptureRequestOptions.Builder()
        for ((key, value) in staticOptions()) {
            @Suppress("UNCHECKED_CAST")
            b.setCaptureRequestOption(key as CaptureRequest.Key<Any>, value)
        }
        b.setCaptureRequestOption(CaptureRequest.CONTROL_AE_LOCK, true)
        lockedGains?.let { g -> lockedTransform?.let { t ->
            b.setCaptureRequestOption(CaptureRequest.CONTROL_AWB_MODE, CameraMetadata.CONTROL_AWB_MODE_OFF)
            b.setCaptureRequestOption(CaptureRequest.COLOR_CORRECTION_MODE, CameraMetadata.COLOR_CORRECTION_MODE_TRANSFORM_MATRIX)
            b.setCaptureRequestOption(CaptureRequest.COLOR_CORRECTION_GAINS, g)
            b.setCaptureRequestOption(CaptureRequest.COLOR_CORRECTION_TRANSFORM, t)
        } } ?: b.setCaptureRequestOption(CaptureRequest.CONTROL_AWB_LOCK, true)
        Camera2CameraControl.from(control).setCaptureRequestOptions(b.build())
        lockApplied = "ae_lock(torch_fallback)+af_off_fixed"
        Log.w(TAG, "torch not lit under manual exposure; reverted to AE lock")
        return true
    }

    // ---- per-frame metadata ----

    private val frameCallback = object : CameraCaptureSession.CaptureCallback() {
        override fun onCaptureCompleted(session: CameraCaptureSession, request: CaptureRequest, result: TotalCaptureResult) {
            lastIso = result.get(CaptureResult.SENSOR_SENSITIVITY) ?: -1
            lastExposureNs = result.get(CaptureResult.SENSOR_EXPOSURE_TIME) ?: -1L
            lastFocusDistance = result.get(CaptureResult.LENS_FOCUS_DISTANCE) ?: -1f
            lastLensState = result.get(CaptureResult.LENS_STATE) ?: -1
            lastFlashState = result.get(CaptureResult.FLASH_STATE) ?: -1
            lastAeMode = result.get(CaptureResult.CONTROL_AE_MODE) ?: -1
            lastAfMode = result.get(CaptureResult.CONTROL_AF_MODE) ?: -1
            lastAwbMode = result.get(CaptureResult.CONTROL_AWB_MODE) ?: -1
            lastTonemapMode = result.get(CaptureResult.TONEMAP_MODE) ?: -1
            lastShadingMode = result.get(CaptureResult.SHADING_MODE) ?: -1
            lastAberrationMode = result.get(CaptureResult.COLOR_CORRECTION_ABERRATION_MODE) ?: -1
            if (Build.VERSION.SDK_INT >= 30) lastZoom = result.get(CaptureResult.CONTROL_ZOOM_RATIO) ?: -1f
            // Only the settle's own AWB output is worth remembering; under manual mode these echo our request.
            if (lastAwbMode != CameraMetadata.CONTROL_AWB_MODE_OFF) {
                result.get(CaptureResult.COLOR_CORRECTION_GAINS)?.let { lastGains = it }
                result.get(CaptureResult.COLOR_CORRECTION_TRANSFORM)?.let { lastTransform = it }
            }
            val sensorTs = result.get(CaptureResult.SENSOR_TIMESTAMP) ?: return
            if (lastResultTs > 0L) {
                val dt = (sensorTs - lastResultTs) / 1e9f
                if (dt > 0f) resultFps = if (resultFps == 0f) 1f / dt else 0.9f * resultFps + 0.1f / dt
            }
            lastResultTs = sensorTs
            if (!recording) return
            val refNs = clock?.toReferenceNs(sensorTs) ?: sensorTs
            val wallNs = System.currentTimeMillis() * 1_000_000L
            synchronized(framesLock) {
                val w = framesCsv ?: return
                try {
                    w.write("$frameRows,$refNs,$wallNs,$lastIso,$lastExposureNs\n")
                    controlsCsv?.write(
                        "$frameRows,$refNs,$lastIso,$lastExposureNs,$lastFocusDistance,$lastLensState,$lastZoom," +
                            "${gainsCsv(result.get(CaptureResult.COLOR_CORRECTION_GAINS))},$lastAwbMode,$lastAeMode,$lastAfMode," +
                            "$lastTonemapMode,$lastShadingMode,$lastFlashState\n"
                    )
                    frameRows++
                } catch (e: Exception) {
                    droppedFrameRows++
                }
            }
        }

        override fun onCaptureFailed(session: CameraCaptureSession, request: CaptureRequest, failure: android.hardware.camera2.CaptureFailure) {
            if (recording) droppedFrameRows++
        }
    }

    private fun gainsCsv(g: RggbChannelVector?): String =
        if (g == null) ",,," else "%.4f,%.4f,%.4f,%.4f".format(g.red, g.greenEven, g.greenOdd, g.blue)

    // ---- ROI tap (live PPG, and the pre-encoder record of it) ----

    private fun analyse(image: ImageProxy) {
        try {
            val sensorTs = image.imageInfo.timestamp
            val refNs = clock?.toReferenceNs(sensorTs) ?: sensorTs
            val stats = roiStats(image) ?: return
            roiLuma = stats.y
            roiClipFraction = stats.clipFraction
            if (lastAnalysisTs > 0L) {
                val dt = (sensorTs - lastAnalysisTs) / 1e9f
                if (dt > 0f) analysisFps = if (analysisFps == 0f) 1f / dt else 0.9f * analysisFps + 0.1f / dt
            }
            lastAnalysisTs = sensorTs
            analysisCount++
            val ac = pulse.push(refNs, stats.y.toDouble())
            ppgRing[ppgWriteIdx] = ac
            peakRing[ppgWriteIdx] = pulse.lastSampleWasPeak
            ppgWriteIdx = (ppgWriteIdx + 1) % ppgRing.size
            if (recording) {
                val rgb = PalmControls.yuvMeanToRgb(stats.y, stats.u, stats.v)
                synchronized(roiLock) {
                    roiCsv?.let { w ->
                        w.write(
                            "$roiRows,$sensorTs,$refNs,${stats.n},%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.5f,%s\n".format(
                                stats.y, stats.u, stats.v, rgb[0], rgb[1], rgb[2], stats.clipFraction,
                                stats.grid.joinToString(",") { "%.2f".format(it) }
                            )
                        )
                        roiRows++
                    }
                }
            }
            val sp = softPreview
            if (sp != null && mode == Mode.RECORD && analysisCount % SOFT_PREVIEW_EVERY == 0L) {
                paintSoftPreview(image, sp)
            }
        } catch (e: Exception) {
            Log.w(TAG, "analysis frame failed", e)
        } finally {
            image.close()
        }
    }

    private class RoiStats(val y: Float, val u: Float, val v: Float, val n: Int, val clipFraction: Float, val grid: FloatArray)

    /**
     * Mean Y, U, V over the centred ROI at full analysis resolution, the fraction of clipped pixels,
     * and a 3x3 grid of Y means so motion and uneven light are visible after the fact.
     */
    private fun roiStats(image: ImageProxy): RoiStats? {
        if (image.planes.size < 3) return null
        val w = image.width
        val h = image.height
        val half = ROI_FRACTION / 2f
        val x0 = ((0.5f - half) * w).toInt().coerceIn(0, w - 2)
        val x1 = ((0.5f + half) * w).toInt().coerceIn(x0 + 1, w)
        val y0 = ((0.5f - half) * h).toInt().coerceIn(0, h - 2)
        val y1 = ((0.5f + half) * h).toInt().coerceIn(y0 + 1, h)

        val yPlane = image.planes[0]
        val yBuf = yPlane.buffer
        val yStride = yPlane.rowStride
        val yPix = yPlane.pixelStride
        val gridSum = LongArray(9)
        val gridN = IntArray(9)
        var ySum = 0L
        var n = 0
        var clipped = 0
        val cellW = (x1 - x0) / 3f
        val cellH = (y1 - y0) / 3f
        var y = y0
        while (y < y1) {
            val rowBase = y * yStride
            val gy = ((y - y0) / cellH).toInt().coerceIn(0, 2)
            var x = x0
            while (x < x1) {
                val v = yBuf.get(rowBase + x * yPix).toInt() and 0xFF
                ySum += v
                n++
                if (v >= PalmControls.CLIP_LEVEL) clipped++
                val gi = gy * 3 + ((x - x0) / cellW).toInt().coerceIn(0, 2)
                gridSum[gi] += v
                gridN[gi]++
                x++
            }
            y++
        }
        if (n == 0) return null

        fun chromaMean(idx: Int): Float {
            val p = image.planes[idx]
            val buf = p.buffer
            val stride = p.rowStride
            val pix = p.pixelStride
            var sum = 0L
            var cnt = 0
            var cy = y0 / 2
            val cy1 = y1 / 2
            val cx0 = x0 / 2
            val cx1 = x1 / 2
            while (cy < cy1) {
                val base = cy * stride
                var cx = cx0
                while (cx < cx1) {
                    val off = base + cx * pix
                    if (off < buf.limit()) { sum += (buf.get(off).toInt() and 0xFF); cnt++ }
                    cx++
                }
                cy++
            }
            return if (cnt == 0) 128f else sum.toFloat() / cnt
        }

        val grid = FloatArray(9) { if (gridN[it] == 0) 0f else gridSum[it].toFloat() / gridN[it] }
        return RoiStats(ySum.toFloat() / n, chromaMean(1), chromaMean(2), n, clipped.toFloat() / n, grid)
    }

    private fun paintSoftPreview(image: ImageProxy, view: ImageView) {
        val bmp = try { image.toBitmap() } catch (_: Exception) { return }
        val deg = image.imageInfo.rotationDegrees
        val shown = if (deg == 0) bmp else Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height, Matrix().apply { postRotate(deg.toFloat()) }, false)
        view.post { view.setImageBitmap(shown) }
    }

    // ---- recording ----

    @SuppressLint("MissingPermission")
    fun startRecording(mp4: File, framesFile: File, controlsFile: File, roiFile: File?, onEvent: (VideoRecordEvent) -> Unit): Boolean {
        val vc = videoCapture ?: return false
        synchronized(framesLock) {
            frameRows = 0
            droppedFrameRows = 0
            framesCsv = BufferedWriter(FileWriter(framesFile)).apply { write("frame_idx,sensor_ts_ns,wall_ns,iso,exposure_ns\n") }
            controlsCsv = BufferedWriter(FileWriter(controlsFile)).apply {
                write("frame_idx,sensor_ts_ns,iso,exposure_ns,focus_diopters,lens_state,zoom_ratio,gain_r,gain_g_even,gain_g_odd,gain_b," +
                    "awb_mode,ae_mode,af_mode,tonemap_mode,shading_mode,flash_state\n")
            }
        }
        synchronized(roiLock) {
            roiRows = 0
            roiCsv = if (roiFile != null && analysisBound) BufferedWriter(FileWriter(roiFile)).apply {
                write("roi_idx,sensor_ts_ns_raw,t_ref_ns,n_px,y_mean,u_mean,v_mean,r_mean,g_mean,b_mean,clip_frac," +
                    "g00,g01,g02,g10,g11,g12,g20,g21,g22\n")
            } else null
        }
        val opts = FileOutputOptions.Builder(mp4).build()
        activeRecording = vc.output.prepareRecording(context, opts)
            .withAudioEnabled()
            .start(ContextCompat.getMainExecutor(context)) { event ->
                if (event is VideoRecordEvent.Start) {
                    recordingStartRefNs = SystemClock.elapsedRealtimeNanos()
                    recording = true
                }
                onEvent(event)
            }
        return true
    }

    fun stopRecording() {
        recording = false
        try { activeRecording?.stop() } catch (e: Exception) { Log.e(TAG, "stop", e) }
        activeRecording = null
    }

    /** Closes the CSV writers. Call after the video Finalize event so no late row is lost. */
    fun closeLogs() {
        synchronized(framesLock) {
            try { framesCsv?.flush(); framesCsv?.close() } catch (_: Exception) {}
            try { controlsCsv?.flush(); controlsCsv?.close() } catch (_: Exception) {}
            framesCsv = null; controlsCsv = null
        }
        synchronized(roiLock) {
            try { roiCsv?.flush(); roiCsv?.close() } catch (_: Exception) {}
            roiCsv = null
        }
    }

    /** Requested versus reported, for `clip1_meta.json`. The reported values are the last capture result. */
    fun controlsJson(): JSONObject {
        val req = requestedExposure
        val set = settledExposure
        fun gains(g: RggbChannelVector?) = if (g == null) JSONObject.NULL else JSONArray(listOf(g.red, g.greenEven, g.greenOdd, g.blue))
        fun transform(t: ColorSpaceTransform?): Any {
            if (t == null) return JSONObject.NULL
            val arr = JSONArray()
            for (r in 0 until 3) for (c in 0 until 3) arr.put(t.getElement(c, r).toDouble())
            return arr
        }
        return JSONObject()
            .put("camera_id", cameraId)
            .put("camera_selection", cameraSelection)
            .put("preferred_physical_id", PREFERRED_PHYSICAL_ID)
            .put("hardware_level", hardwareLevel)
            .put("manual_sensor_supported", manualSensorSupported)
            .put("manual_post_processing_supported", manualPostProcessingSupported)
            .put("focus", JSONObject()
                .put("distance_cm", distanceCm)
                .put("requested_diopters", focus.requestedDiopters)
                .put("applied_diopters", focus.appliedDiopters)
                .put("clamped_to_lens", focus.clampedToLens)
                .put("lens_minimum_focus_distance_diopters", minimumFocusDistance ?: JSONObject.NULL)
                .put("lens_closest_focus_cm", minimumFocusDistance?.let { PalmControls.centimetres(it) } ?: JSONObject.NULL)
                .put("calibration", focusCalibration)
                .put("reported_diopters", lastFocusDistance)
                .put("af_mode_reported", lastAfMode)
                .put("lens_state_reported", lastLensState))
            .put("exposure", JSONObject()
                .put("settled_ns", set?.exposureNs ?: JSONObject.NULL)
                .put("settled_iso", set?.iso ?: JSONObject.NULL)
                .put("requested_ns", req?.exposureNs ?: JSONObject.NULL)
                .put("requested_iso", req?.iso ?: JSONObject.NULL)
                .put("capped_to_ns", PalmControls.MAX_EXPOSURE_NS)
                .put("was_capped", req?.capped ?: false)
                .put("iso_saturated", req?.isoSaturated ?: false)
                .put("reported_ns", lastExposureNs)
                .put("reported_iso", lastIso)
                .put("ae_mode_reported", lastAeMode)
                .put("metered_on_roi", activeArray != null))
            .put("white_balance", JSONObject()
                .put("applied", awbApplied)
                .put("awb_mode_reported", lastAwbMode)
                .put("gains_rggb", gains(lockedGains))
                .put("transform_row_major", transform(lockedTransform)))
            .put("tonemap_mode_requested", if (manualPostProcessingSupported) "CONTRAST_CURVE(sRGB,64pt)" else "FAST")
            .put("tonemap_mode_reported", lastTonemapMode)
            .put("shading_mode_reported", lastShadingMode)
            .put("aberration_mode_reported", lastAberrationMode)
            .put("zoom_ratio_reported", lastZoom)
            .put("flash_state_reported", lastFlashState)
            .put("result_fps", resultFps)
            .put("analysis_fps", analysisFps)
            .put("analysis_resolution", analysisResolution)
            .put("roi_tap_during_clip", analysisBound)
            .put("yuv_to_rgb", "BT.601 full range (JFIF), applied to ROI means")
            .put("preflight", preflight?.let { v ->
                JSONObject().put("ok", v.ok).put("warnings", JSONArray(v.warnings)).put("exposure_correction_factor", v.exposureCorrection ?: JSONObject.NULL)
            } ?: JSONObject.NULL)
    }

    fun shutdown() {
        try { activeRecording?.stop() } catch (_: Exception) {}
        closeLogs()
        analysisExecutor.shutdown()
    }
}
