package org.swht.palm

import android.annotation.SuppressLint
import android.content.Context
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraMetadata
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.CaptureResult
import android.hardware.camera2.TotalCaptureResult
import android.os.SystemClock
import android.util.Log
import android.util.Range
import android.util.Size
import androidx.camera.camera2.interop.Camera2CameraControl
import androidx.camera.camera2.interop.Camera2CameraInfo
import androidx.camera.camera2.interop.Camera2Interop
import androidx.camera.camera2.interop.CaptureRequestOptions
import androidx.camera.camera2.interop.ExperimentalCamera2Interop
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
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
import java.io.BufferedWriter
import java.io.File
import java.io.FileWriter
import java.util.concurrent.Executors

/**
 * The phone leg of the capture: a 1080p30 clip with every automatic control pinned, a per-frame
 * timestamp log on the study reference clock, and a live palm-ROI mean so the operator can see a
 * pulse before committing to the clip.
 *
 * Why the controls are pinned (protocol section 5): auto-exposure, auto white balance and
 * stabilisation all modulate pixel values frame to frame. That modulation lands in the same band as
 * the pulse and is indistinguishable from it afterwards, so a clip recorded with them running is
 * not recoverable by any amount of processing. They are locked once, before the recording starts,
 * and the values actually achieved are written to the clip metadata.
 */
class CameraRig(
    private val context: Context,
    private val previewView: PreviewView,
) {

    companion object {
        private const val TAG = "CameraRig"
        /** Side of the centred measurement ROI as a fraction of the frame. Shared with [RoiOverlay]. */
        const val ROI_FRACTION = 0.40f
        private const val TARGET_FPS = 30
        /** Protocol section 5 requires 1080p; anything shorter is a failed clip, not a lesser one. */
        private const val MIN_VIDEO_SHORT_SIDE = 1080
    }

    /** Short side of the resolution the encoder actually got, or -1 before binding. */
    private fun videoShortSide(): Int {
        val r = videoCapture?.attachedSurfaceResolution ?: return -1
        return minOf(r.width, r.height)
    }

    private val analysisExecutor = Executors.newSingleThreadExecutor()

    private var camera: Camera? = null
    private var previewUseCase: Preview? = null
    private var videoCapture: VideoCapture<Recorder>? = null
    private var activeRecording: Recording? = null

    var clock: ClockBridge? = null; private set
    @Volatile var analysisBound = false; private set
    @Volatile var videoResolution = "unknown"; private set
    @Volatile var previewResolution = "unknown"; private set
    /**
     * Width over height of the preview frame as it appears on a portrait screen, or 0 before
     * binding. [RoiOverlay] needs it to place the ROI box over the real image area rather than
     * over the whole view, which are not the same rectangle once the frame is letterboxed.
     */
    @Volatile var previewDisplayAspect = 0f; private set
    @Volatile var hardwareLevel = "unknown"; private set
    @Volatile var manualSensorSupported = false; private set

    // latest values observed from capture results, used to choose the lock point
    @Volatile var lastIso = -1; private set
    @Volatile var lastExposureNs = -1L; private set
    @Volatile var lastFocusDistance = -1f; private set
    @Volatile var lockApplied: String = "none"; private set

    @Volatile var frameRows = 0L; private set
    @Volatile var ppgRows = 0L; private set
    @Volatile var droppedFrameRows = 0L; private set
    @Volatile var recordingStartRefNs = 0L; private set

    /** ~6 s of detrended ROI luma for the on-screen trace, with the detected beats beside it. */
    val ppgRing = FloatArray(6 * TARGET_FPS)
    val peakRing = BooleanArray(6 * TARGET_FPS)
    @Volatile var ppgWriteIdx = 0; private set
    @Volatile var ppgLevel = 0f; private set
    val pulse = PulseMeter()

    private val framesLock = Any()
    private var framesCsv: BufferedWriter? = null
    @Volatile private var recording = false

    // ---- binding ----

    /**
     * What is currently bound. Measured on a OnePlus 12 (LEVEL_3): Preview + VideoCapture +
     * ImageAnalysis together force the encoder down to 720p, and shrinking either the preview or
     * the analysis stream does not recover it — three streams is simply the limit. Rather than
     * give up either the protocol resolution or the operator's pulse readout, the two are
     * time-shared: [Mode.MONITOR] while the operator lines the palm up, [Mode.RECORD] for the clip.
     */
    enum class Mode { MONITOR, RECORD }

    @Volatile var mode = Mode.MONITOR; private set

    fun bind(owner: LifecycleOwner, mode: Mode, onReady: (Boolean) -> Unit) {
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener({
            val provider = try {
                future.get()
            } catch (e: Exception) {
                Log.e(TAG, "camera provider failed", e); onReady(false); return@addListener
            }

            val previewBuilder = Preview.Builder()
            Camera2Interop.Extender(previewBuilder).apply {
                applyStaticOptions(this)
                setSessionCaptureCallback(frameCallback)
            }
            val preview = previewBuilder.build()
                .also { it.surfaceProvider = previewView.surfaceProvider }
            previewUseCase = preview

            provider.unbindAll()
            camera = try {
                if (mode == Mode.RECORD) {
                    val recorder = Recorder.Builder()
                        .setQualitySelector(
                            QualitySelector.from(
                                Quality.FHD, FallbackStrategy.higherQualityOrLowerThan(Quality.FHD)
                            )
                        )
                        .build()
                    val vc = VideoCapture.withOutput(recorder)
                    videoCapture = vc
                    analysisBound = false
                    // blank the palm trace rather than leave the last six seconds frozen on
                    // screen, which reads as a live signal when it is not
                    ppgRing.fill(0f)
                    peakRing.fill(false)
                    pulse.reset()
                    provider.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, preview, vc)
                } else {
                    videoCapture = null
                    val analysis = ImageAnalysis.Builder()
                        .setResolutionSelector(
                            ResolutionSelector.Builder().setResolutionStrategy(
                                ResolutionStrategy(
                                    Size(640, 480),
                                    ResolutionStrategy.FALLBACK_RULE_CLOSEST_LOWER_THEN_HIGHER
                                )
                            ).build()
                        )
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build()
                        .also { it.setAnalyzer(analysisExecutor, ::analyse) }
                    analysisBound = true
                    pulse.reset()
                    provider.bindToLifecycle(
                        owner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis
                    )
                }
            } catch (e: Exception) {
                Log.e(TAG, "bind failed in $mode", e); null
            }
            if (camera == null) { onReady(false); return@addListener }

            this.mode = mode
            videoResolution = if (mode == Mode.RECORD) {
                videoCapture?.attachedSurfaceResolution
                    ?.let { "${it.width}x${it.height}" } ?: "unknown"
            } else "monitoring"
            previewResolution = preview.attachedSurfaceResolution
                ?.let { "${it.width}x${it.height}" } ?: "unknown"
            preview.attachedSurfaceResolution?.let {
                // the surface is in sensor (landscape) orientation; on screen it is rotated upright
                previewDisplayAspect =
                    minOf(it.width, it.height).toFloat() / maxOf(it.width, it.height).toFloat()
            }
            Log.i(TAG, "bound $mode: preview=$previewResolution video=$videoResolution " +
                "view=${previewView.width}x${previewView.height} scale=${previewView.scaleType}")
            if (mode == Mode.RECORD && videoShortSide() in 1 until MIN_VIDEO_SHORT_SIDE) {
                Log.w(TAG, "encoder negotiated ${videoShortSide()}p, below the protocol minimum")
            }

            readCharacteristics()
            onReady(true)
        }, ContextCompat.getMainExecutor(context))
    }

    private fun readCharacteristics() {
        val info = camera?.cameraInfo ?: return
        val c2 = Camera2CameraInfo.from(info)
        val source = c2.getCameraCharacteristic(CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE)
        clock = ClockBridge(source).also { it.measure() }

        hardwareLevel = when (c2.getCameraCharacteristic(
            CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL
        )) {
            CameraMetadata.INFO_SUPPORTED_HARDWARE_LEVEL_LEGACY -> "LEGACY"
            CameraMetadata.INFO_SUPPORTED_HARDWARE_LEVEL_LIMITED -> "LIMITED"
            CameraMetadata.INFO_SUPPORTED_HARDWARE_LEVEL_FULL -> "FULL"
            CameraMetadata.INFO_SUPPORTED_HARDWARE_LEVEL_3 -> "LEVEL_3"
            CameraMetadata.INFO_SUPPORTED_HARDWARE_LEVEL_EXTERNAL -> "EXTERNAL"
            else -> "unknown"
        }
        manualSensorSupported = c2.getCameraCharacteristic(
            CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES
        )?.contains(CameraMetadata.REQUEST_AVAILABLE_CAPABILITIES_MANUAL_SENSOR) == true
    }

    private fun <T> applyStaticOptions(ext: Camera2Interop.Extender<T>) {
        ext.setCaptureRequestOption(
            CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(TARGET_FPS, TARGET_FPS)
        )
        ext.setCaptureRequestOption(
            CaptureRequest.CONTROL_SCENE_MODE, CameraMetadata.CONTROL_SCENE_MODE_DISABLED
        )
        ext.setCaptureRequestOption(
            CaptureRequest.CONTROL_VIDEO_STABILIZATION_MODE,
            CameraMetadata.CONTROL_VIDEO_STABILIZATION_MODE_OFF
        )
        ext.setCaptureRequestOption(
            CaptureRequest.LENS_OPTICAL_STABILIZATION_MODE,
            CameraMetadata.LENS_OPTICAL_STABILIZATION_MODE_OFF
        )
        ext.setCaptureRequestOption(
            CaptureRequest.NOISE_REDUCTION_MODE, CameraMetadata.NOISE_REDUCTION_MODE_OFF
        )
        ext.setCaptureRequestOption(CaptureRequest.EDGE_MODE, CameraMetadata.EDGE_MODE_OFF)
        ext.setCaptureRequestOption(
            CaptureRequest.TONEMAP_MODE, CameraMetadata.TONEMAP_MODE_FAST
        )
    }

    fun setTorch(on: Boolean) {
        camera?.cameraControl?.enableTorch(on)
    }

    /**
     * Pins exposure, white balance and focus at whatever the 2 s settle arrived at. Prefers true
     * manual sensor control; falls back to AE/AWB lock on devices that do not expose it. Returns a
     * short description of what was actually achieved, which goes into the clip metadata.
     */
    fun lockControls(): String {
        val control = camera?.cameraControl ?: return "no camera"
        val b = CaptureRequestOptions.Builder()
        b.setCaptureRequestOption(
            CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(TARGET_FPS, TARGET_FPS)
        )
        b.setCaptureRequestOption(
            CaptureRequest.CONTROL_VIDEO_STABILIZATION_MODE,
            CameraMetadata.CONTROL_VIDEO_STABILIZATION_MODE_OFF
        )
        b.setCaptureRequestOption(
            CaptureRequest.LENS_OPTICAL_STABILIZATION_MODE,
            CameraMetadata.LENS_OPTICAL_STABILIZATION_MODE_OFF
        )
        b.setCaptureRequestOption(
            CaptureRequest.NOISE_REDUCTION_MODE, CameraMetadata.NOISE_REDUCTION_MODE_OFF
        )
        b.setCaptureRequestOption(CaptureRequest.EDGE_MODE, CameraMetadata.EDGE_MODE_OFF)

        val iso = lastIso
        val exp = lastExposureNs
        lockApplied = if (manualSensorSupported && iso > 0 && exp > 0) {
            b.setCaptureRequestOption(
                CaptureRequest.CONTROL_AE_MODE, CameraMetadata.CONTROL_AE_MODE_OFF
            )
            b.setCaptureRequestOption(CaptureRequest.SENSOR_SENSITIVITY, iso)
            b.setCaptureRequestOption(CaptureRequest.SENSOR_EXPOSURE_TIME, exp)
            b.setCaptureRequestOption(
                CaptureRequest.SENSOR_FRAME_DURATION, 1_000_000_000L / TARGET_FPS
            )
            "manual_sensor"
        } else {
            b.setCaptureRequestOption(CaptureRequest.CONTROL_AE_LOCK, true)
            "ae_lock"
        }
        b.setCaptureRequestOption(CaptureRequest.CONTROL_AWB_LOCK, true)

        val focus = lastFocusDistance
        if (focus >= 0f) {
            b.setCaptureRequestOption(
                CaptureRequest.CONTROL_AF_MODE, CameraMetadata.CONTROL_AF_MODE_OFF
            )
            b.setCaptureRequestOption(CaptureRequest.LENS_FOCUS_DISTANCE, focus)
            lockApplied += "+af_off"
        }
        Camera2CameraControl.from(control).setCaptureRequestOptions(b.build())
        return lockApplied
    }

    // ---- per-frame metadata ----

    private val frameCallback = object : CameraCaptureSession.CaptureCallback() {
        override fun onCaptureCompleted(
            session: CameraCaptureSession, request: CaptureRequest, result: TotalCaptureResult
        ) {
            val iso = result.get(CaptureResult.SENSOR_SENSITIVITY) ?: -1
            val exp = result.get(CaptureResult.SENSOR_EXPOSURE_TIME) ?: -1L
            val focus = result.get(CaptureResult.LENS_FOCUS_DISTANCE) ?: -1f
            lastIso = iso
            lastExposureNs = exp
            lastFocusDistance = focus
            if (!recording) return
            val sensorTs = result.get(CaptureResult.SENSOR_TIMESTAMP) ?: return
            val refNs = clock?.toReferenceNs(sensorTs) ?: sensorTs
            val wallNs = System.currentTimeMillis() * 1_000_000L
            synchronized(framesLock) {
                val w = framesCsv ?: return
                try {
                    w.write("$frameRows,$refNs,$wallNs,$iso,$exp\n")
                    frameRows++
                } catch (e: Exception) {
                    droppedFrameRows++
                }
            }
        }

        override fun onCaptureFailed(
            session: CameraCaptureSession, request: CaptureRequest,
            failure: android.hardware.camera2.CaptureFailure
        ) {
            if (recording) droppedFrameRows++
        }
    }

    // ---- ROI mean (live PPG) ----

    private fun analyse(image: ImageProxy) {
        try {
            val sensorTs = image.imageInfo.timestamp
            val refNs = clock?.toReferenceNs(sensorTs) ?: sensorTs
            val means = roiMeans(image) ?: return
            ppgLevel = means[0]
            val ac = pulse.push(refNs, means[0].toDouble())
            ppgRing[ppgWriteIdx] = ac
            peakRing[ppgWriteIdx] = pulse.lastSampleWasPeak
            ppgWriteIdx = (ppgWriteIdx + 1) % ppgRing.size
            ppgRows++
        } catch (e: Exception) {
            Log.w(TAG, "analysis frame failed", e)
        } finally {
            image.close()
        }
    }

    /** Mean Y, U and V over the centred ROI, subsampled for cost. Null if the format is unusable. */
    private fun roiMeans(image: ImageProxy): FloatArray? {
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
        var ySum = 0L
        var yN = 0
        var y = y0
        while (y < y1) {
            var x = x0
            val rowBase = y * yStride
            while (x < x1) {
                ySum += (yBuf.get(rowBase + x * yPix).toInt() and 0xFF)
                yN++
                x += 2
            }
            y += 2
        }
        if (yN == 0) return null

        fun chromaMean(idx: Int): Float {
            val p = image.planes[idx]
            val buf = p.buffer
            val stride = p.rowStride
            val pix = p.pixelStride
            var sum = 0L
            var n = 0
            var cy = y0 / 2
            val cy1 = y1 / 2
            while (cy < cy1) {
                var cx = x0 / 2
                val cx1 = x1 / 2
                val base = cy * stride
                while (cx < cx1) {
                    val off = base + cx * pix
                    if (off < buf.limit()) {
                        sum += (buf.get(off).toInt() and 0xFF)
                        n++
                    }
                    cx += 2
                }
                cy += 2
            }
            return if (n == 0) 0f else sum.toFloat() / n
        }

        return floatArrayOf(ySum.toFloat() / yN, chromaMean(1), chromaMean(2))
    }

    // ---- recording ----

    @SuppressLint("MissingPermission")
    fun startRecording(
        mp4: File, framesFile: File, onEvent: (VideoRecordEvent) -> Unit
    ): Boolean {
        val vc = videoCapture ?: return false
        synchronized(framesLock) {
            frameRows = 0
            droppedFrameRows = 0
            framesCsv = BufferedWriter(FileWriter(framesFile)).apply {
                write("frame_idx,sensor_ts_ns,wall_ns,iso,exposure_ns\n")
            }
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
            framesCsv = null
        }
    }

    fun shutdown() {
        try { activeRecording?.stop() } catch (_: Exception) {}
        closeLogs()
        analysisExecutor.shutdown()
    }
}
