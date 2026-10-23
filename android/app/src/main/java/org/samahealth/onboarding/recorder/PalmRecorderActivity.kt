/*
 * PalmRecorderActivity: custom Camera2 recorder for the OnePlus 12 (protocol sections 4.6 and 5), launched from a
 * clip screen of the onboarding survey. Adapted from palmppg/capture/android/PalmRecorder.kt with a layout built in
 * code (no XML resources) and a result returned to the survey.
 *
 * 1920x1080 / 30 fps / H.264 / AAC audio (the sync beep is in the audio). Focus is fixed at the rig distance from the
 * first frame (no AF hunt to catch mid-sweep); the main sensor is opened by id so the logical camera cannot hand off to
 * the ultrawide at palm distance; zoom pinned at 1.0; sRGB tone curve, lens shading and aberration correction off; AE
 * metered on the palm ROI. 2 s auto settle, then manual exposure (capped at 12 ms, light moved into ISO) and the
 * settled colour gains re-sent as manual white balance; OIS and EIS off; scene modes, noise reduction and edge
 * enhancement off; torch only in sequential capture mode. Mirrors palmppg/capture/android/SamaPalmRecorder/CameraRig.kt.
 * Writes <clip>.mp4, <clip>_frames.csv (frame_idx, sensor_ts_ns = SENSOR_TIMESTAMP, wall_ns, iso, exposure_ns) and
 * <clip>_meta.json under Android/data/org.samahealth.onboarding/files/<PID>/. It must pass the bench acceptance
 * (protocol 4.5) before it is used for study clips.
 */
package org.samahealth.onboarding.recorder

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CameraMetadata
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.CaptureResult
import android.hardware.camera2.TotalCaptureResult
import android.hardware.camera2.params.ColorSpaceTransform
import android.hardware.camera2.params.MeteringRectangle
import android.hardware.camera2.params.RggbChannelVector
import android.hardware.camera2.params.TonemapCurve
import android.graphics.Rect
import kotlin.math.pow
import kotlin.math.roundToInt
import android.media.MediaRecorder
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread
import android.util.Range
import android.view.Gravity
import android.view.Surface
import android.view.SurfaceHolder
import android.view.SurfaceView
import android.widget.Button
import android.widget.FrameLayout
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileWriter

class PalmRecorderActivity : Activity() {
    companion object {
        const val EXTRA_STUDY_ID = "study_id"
        const val EXTRA_CLIP_ID = "clip_id"
        const val EXTRA_CAPTURE_MODE = "capture_mode"
        const val EXTRA_MP4 = "mp4_path"
        /** OnePlus 12 main sensor. Logical camera 0 fuses it with the ultrawide and may hand off at palm distance. */
        const val PREFERRED_PHYSICAL_ID = "2"
        /** Lens-to-palm distance the rig is built for; sets the fixed focus plane (1/m = diopters). */
        const val DISTANCE_CM = 17f
        /** Longest shutter during capture; light lost to the cap is restored as sensitivity. */
        const val MAX_EXPOSURE_NS = 12_000_000L
        const val ROI_FRACTION = 0.40f
    }

    private val studyId: String get() = intent.getStringExtra(EXTRA_STUDY_ID) ?: "SWHT-PP-003-0000"
    private val clipId: String get() = intent.getStringExtra(EXTRA_CLIP_ID) ?: "clip1"
    private val captureMode: String get() = intent.getStringExtra(EXTRA_CAPTURE_MODE) ?: "simultaneous"
    private val torchOn: Boolean get() = captureMode == "sequential"

    private lateinit var preview: SurfaceView
    private lateinit var recordButton: Button
    private lateinit var outDir: File
    private var camera: CameraDevice? = null
    private var session: CameraCaptureSession? = null
    private var recorder: MediaRecorder? = null
    private var framesCsv: FileWriter? = null
    private var frameIdx = 0L
    @Volatile private var recording = false
    private var lockedIso = -1
    private var lockedExposureNs = -1L
    private var lockedFocusDistance = -1f
    private var manualSensor = false
    private var manualPost = false
    private var minFocusDiopters = Float.POSITIVE_INFINITY
    private var isoRange: Range<Int> = Range(100, 6400)
    private var exposureRange: Range<Long> = Range(100_000L, 100_000_000L)
    private var activeArray: Rect? = null
    private var settledGains: RggbChannelVector? = null
    private var settledTransform: ColorSpaceTransform? = null
    private var requestedIso = -1
    private var requestedExposureNs = -1L
    private var exposureCapped = false
    private var lockApplied = "none"
    private var awbApplied = "none"
    private var surfaceReady = false
    private var backCameraIdUsed = "?"
    private val thread = HandlerThread("camera").apply { start() }
    private val handler = Handler(thread.looper)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        preview = SurfaceView(this)
        recordButton = Button(this).apply { text = "RECORD" }
        val root = FrameLayout(this)
        root.addView(preview, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        root.addView(recordButton, FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT,
            Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL))
        setContentView(root)
        preview.holder.setFixedSize(1920, 1080)
        preview.holder.addCallback(object : SurfaceHolder.Callback {
            override fun surfaceCreated(holder: SurfaceHolder) { surfaceReady = true }
            override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {}
            override fun surfaceDestroyed(holder: SurfaceHolder) { surfaceReady = false; if (recording) stopRecording(cancelled = true) }
        })
        outDir = File(getExternalFilesDir(null), studyId).apply { mkdirs() }
        val perms = arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO)
        if (perms.any { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }) requestPermissions(perms, 1)
        recordButton.setOnClickListener { if (recording) stopRecording(cancelled = false) else startRecording() }
    }

    /** The main sensor by id when the HAL lists it; otherwise the first back camera. */
    private fun backCameraId(): String {
        val cm = getSystemService(CAMERA_SERVICE) as CameraManager
        val ids = cm.cameraIdList
        val id = if (PREFERRED_PHYSICAL_ID in ids) PREFERRED_PHYSICAL_ID else ids.first { candidate ->
            cm.getCameraCharacteristics(candidate).get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK
        }
        val c = cm.getCameraCharacteristics(id)
        val caps = c.get(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES) ?: intArrayOf()
        manualSensor = caps.contains(CameraMetadata.REQUEST_AVAILABLE_CAPABILITIES_MANUAL_SENSOR)
        manualPost = caps.contains(CameraMetadata.REQUEST_AVAILABLE_CAPABILITIES_MANUAL_POST_PROCESSING)
        minFocusDiopters = c.get(CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE)?.takeIf { it > 0f } ?: Float.POSITIVE_INFINITY
        c.get(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE)?.let { isoRange = it }
        c.get(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE)?.let { exposureRange = it }
        activeArray = c.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE)
        return id
    }

    /** Requested focus plane, pinned to the lens's closest focus when the rig distance is inside it. */
    private fun focusDiopters(): Float = (100f / DISTANCE_CM).coerceAtMost(minFocusDiopters)

    /** Centre-ROI metering rectangle on the active array for the 16:9 field the clip records. */
    private fun roiMeteringRegion(): MeteringRectangle? {
        val a = activeArray ?: return null
        val w = a.width().toFloat()
        val cropH = minOf(a.height().toFloat(), w * 9f / 16f)
        val cx = a.left + w / 2f
        val cy = a.top + a.height() / 2f
        val half = ROI_FRACTION / 2f
        val l = (cx - half * w).toInt(); val t = (cy - half * cropH).toInt()
        return MeteringRectangle(l, t, ((cx + half * w).toInt() - l), ((cy + half * cropH).toInt() - t), MeteringRectangle.METERING_WEIGHT_MAX)
    }

    /** sRGB OETF at 64 points as Camera2's interleaved (in, out) curve; the ingest inverts exactly this. */
    private fun srgbCurve(): FloatArray {
        val n = 64
        val out = FloatArray(n * 2)
        for (i in 0 until n) {
            val x = i.toFloat() / (n - 1)
            out[2 * i] = x
            out[2 * i + 1] = if (x <= 0.0031308f) 12.92f * x else (1.055 * x.toDouble().pow(1.0 / 2.4) - 0.055).toFloat()
        }
        return out
    }

    private fun buildRecorder(): MediaRecorder {
        val r = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(this) else @Suppress("DEPRECATION") MediaRecorder()
        r.setAudioSource(MediaRecorder.AudioSource.MIC)
        r.setVideoSource(MediaRecorder.VideoSource.SURFACE)
        r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
        r.setOutputFile(File(outDir, "$clipId.mp4").absolutePath)
        r.setVideoEncoder(MediaRecorder.VideoEncoder.H264)
        r.setVideoSize(1920, 1080)
        r.setVideoFrameRate(30)
        r.setVideoEncodingBitRate(100_000_000)
        r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
        r.setAudioSamplingRate(48_000)
        r.setAudioChannels(1)
        r.setAudioEncodingBitRate(128_000)
        r.prepare()
        return r
    }

    private fun applyFixedControls(b: CaptureRequest.Builder, lock: Boolean) {
        b.set(CaptureRequest.CONTROL_MODE, CameraMetadata.CONTROL_MODE_AUTO)
        b.set(CaptureRequest.CONTROL_SCENE_MODE, CameraMetadata.CONTROL_SCENE_MODE_DISABLED)
        b.set(CaptureRequest.CONTROL_VIDEO_STABILIZATION_MODE, CameraMetadata.CONTROL_VIDEO_STABILIZATION_MODE_OFF)
        b.set(CaptureRequest.LENS_OPTICAL_STABILIZATION_MODE, CameraMetadata.LENS_OPTICAL_STABILIZATION_MODE_OFF)
        b.set(CaptureRequest.NOISE_REDUCTION_MODE, CameraMetadata.NOISE_REDUCTION_MODE_OFF)
        b.set(CaptureRequest.EDGE_MODE, CameraMetadata.EDGE_MODE_OFF)
        if (manualPost) {
            val curve = srgbCurve()
            b.set(CaptureRequest.TONEMAP_MODE, CameraMetadata.TONEMAP_MODE_CONTRAST_CURVE)
            b.set(CaptureRequest.TONEMAP_CURVE, TonemapCurve(curve, curve, curve))
            b.set(CaptureRequest.SHADING_MODE, CameraMetadata.SHADING_MODE_OFF)
            b.set(CaptureRequest.COLOR_CORRECTION_ABERRATION_MODE, CameraMetadata.COLOR_CORRECTION_ABERRATION_MODE_OFF)
        } else {
            b.set(CaptureRequest.TONEMAP_MODE, CameraMetadata.TONEMAP_MODE_FAST)
        }
        if (Build.VERSION.SDK_INT >= 30) b.set(CaptureRequest.CONTROL_ZOOM_RATIO, 1.0f)
        roiMeteringRegion()?.let { b.set(CaptureRequest.CONTROL_AE_REGIONS, arrayOf(it)) }
        b.set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(30, 30))
        b.set(CaptureRequest.FLASH_MODE, if (torchOn) CameraMetadata.FLASH_MODE_TORCH else CameraMetadata.FLASH_MODE_OFF)
        // Fixed focus from the first frame: nothing to hunt, nothing to catch mid-sweep.
        b.set(CaptureRequest.CONTROL_AF_MODE, CameraMetadata.CONTROL_AF_MODE_OFF)
        b.set(CaptureRequest.LENS_FOCUS_DISTANCE, focusDiopters())
        if (!lock) {
            b.set(CaptureRequest.CONTROL_AE_LOCK, false)
            b.set(CaptureRequest.CONTROL_AWB_LOCK, false)
            return
        }
        // Exposure: manual at the settled value, shutter capped, the lost light moved into gain.
        if (manualSensor && lockedIso > 0 && lockedExposureNs > 0) {
            var exp = lockedExposureNs.coerceIn(exposureRange.lower, exposureRange.upper)
            var iso = lockedIso
            exposureCapped = exp > MAX_EXPOSURE_NS
            if (exposureCapped) {
                iso = (lockedIso * (exp.toDouble() / MAX_EXPOSURE_NS)).roundToInt()
                exp = MAX_EXPOSURE_NS
            }
            iso = iso.coerceIn(isoRange.lower, isoRange.upper)
            requestedIso = iso; requestedExposureNs = exp
            b.set(CaptureRequest.CONTROL_AE_MODE, CameraMetadata.CONTROL_AE_MODE_OFF)
            b.set(CaptureRequest.SENSOR_SENSITIVITY, iso)
            b.set(CaptureRequest.SENSOR_EXPOSURE_TIME, exp)
            b.set(CaptureRequest.SENSOR_FRAME_DURATION, 1_000_000_000L / 30)
            lockApplied = "manual_sensor" + (if (exposureCapped) "+exposure_capped" else "") + "+af_off_fixed"
        } else {
            b.set(CaptureRequest.CONTROL_AE_LOCK, true)
            lockApplied = "ae_lock+af_off_fixed"
        }
        // White balance: the settled gains and transform re-sent as numbers, so they are known afterwards.
        val g = settledGains; val t = settledTransform
        if (manualPost && g != null && t != null) {
            b.set(CaptureRequest.CONTROL_AWB_MODE, CameraMetadata.CONTROL_AWB_MODE_OFF)
            b.set(CaptureRequest.COLOR_CORRECTION_MODE, CameraMetadata.COLOR_CORRECTION_MODE_TRANSFORM_MATRIX)
            b.set(CaptureRequest.COLOR_CORRECTION_GAINS, g)
            b.set(CaptureRequest.COLOR_CORRECTION_TRANSFORM, t)
            awbApplied = "manual_gains_from_settle"
        } else {
            b.set(CaptureRequest.CONTROL_AWB_LOCK, true)
            awbApplied = "awb_lock"
        }
    }

    private val frameLogger = object : CameraCaptureSession.CaptureCallback() {
        override fun onCaptureCompleted(s: CameraCaptureSession, req: CaptureRequest, result: TotalCaptureResult) {
            val ts = result.get(CaptureResult.SENSOR_TIMESTAMP) ?: return
            val iso = result.get(CaptureResult.SENSOR_SENSITIVITY) ?: -1
            val exp = result.get(CaptureResult.SENSOR_EXPOSURE_TIME) ?: -1L
            val focus = result.get(CaptureResult.LENS_FOCUS_DISTANCE) ?: -1f
            if (!recording) {
                lockedIso = iso; lockedExposureNs = exp; lockedFocusDistance = focus
                if (result.get(CaptureResult.CONTROL_AWB_MODE) != CameraMetadata.CONTROL_AWB_MODE_OFF) {
                    result.get(CaptureResult.COLOR_CORRECTION_GAINS)?.let { settledGains = it }
                    result.get(CaptureResult.COLOR_CORRECTION_TRANSFORM)?.let { settledTransform = it }
                }
                return
            }
            val wallNs = System.currentTimeMillis() * 1_000_000L
            framesCsv?.write("$frameIdx,$ts,$wallNs,$iso,$exp\n")
            frameIdx += 1
        }
    }

    private fun startRecording() {
        if (!surfaceReady) return
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) return
        val cm = getSystemService(CAMERA_SERVICE) as CameraManager
        val id = backCameraId().also { backCameraIdUsed = it }
        cm.openCamera(id, object : CameraDevice.StateCallback() {
            override fun onOpened(dev: CameraDevice) { camera = dev; configureSession(dev) }
            override fun onDisconnected(dev: CameraDevice) { dev.close(); camera = null }
            override fun onError(dev: CameraDevice, error: Int) { dev.close(); camera = null }
        }, handler)
    }

    @Suppress("DEPRECATION")
    private fun configureSession(dev: CameraDevice) {
        val rec = buildRecorder().also { recorder = it }
        val surfaces = listOf(preview.holder.surface, rec.surface)
        dev.createCaptureSession(surfaces, object : CameraCaptureSession.StateCallback() {
            override fun onConfigured(s: CameraCaptureSession) {
                session = s
                val settle = dev.createCaptureRequest(CameraDevice.TEMPLATE_RECORD)
                surfaces.forEach { settle.addTarget(it) }
                applyFixedControls(settle, lock = false)
                s.setRepeatingRequest(settle.build(), frameLogger, handler)
                handler.postDelayed({ lockAndRecord(dev, s, surfaces) }, 2_000L)
            }
            override fun onConfigureFailed(s: CameraCaptureSession) { s.close() }
        }, handler)
    }

    private fun lockAndRecord(dev: CameraDevice, s: CameraCaptureSession, surfaces: List<Surface>) {
        val locked = dev.createCaptureRequest(CameraDevice.TEMPLATE_RECORD)
        surfaces.forEach { locked.addTarget(it) }
        applyFixedControls(locked, lock = true)
        framesCsv = FileWriter(File(outDir, "${clipId}_frames.csv")).apply { write("frame_idx,sensor_ts_ns,wall_ns,iso,exposure_ns\n") }
        frameIdx = 0
        val startWallNs = System.currentTimeMillis() * 1_000_000L
        recorder?.start()
        recording = true
        s.setRepeatingRequest(locked.build(), frameLogger, handler)
        writeMeta(startWallNs)
        runOnUiThread { recordButton.text = "STOP" }
    }

    private fun writeMeta(startWallNs: Long) {
        val meta = JSONObject()
            .put("app", "PalmRecorderActivity (SamaHealth onboarding app, Camera2)")
            .put("device_model", "${Build.MANUFACTURER} ${Build.MODEL}")
            .put("os_build", Build.DISPLAY)
            .put("resolution", JSONArray(listOf(1920, 1080)))
            .put("fps_nominal", 30)
            .put("bitrate_mbps", 100)
            .put("iso", if (requestedIso > 0) requestedIso else lockedIso)
            .put("exposure_ns", if (requestedExposureNs > 0) requestedExposureNs else lockedExposureNs)
            .put("wb_locked", true)
            .put("focus_locked", true)
            // --- beyond CONTRACTS 3.5: what was actually asked of the camera ---
            .put("lock_applied", lockApplied)
            .put("awb_applied", awbApplied)
            .put("camera_id", backCameraIdUsed)
            .put("focus_distance_cm", DISTANCE_CM)
            .put("focus_diopters_applied", focusDiopters())
            .put("focus_diopters_reported_at_lock", lockedFocusDistance)
            .put("lens_minimum_focus_distance_diopters", if (minFocusDiopters.isFinite()) minFocusDiopters else JSONObject.NULL)
            .put("exposure_settled_ns", lockedExposureNs)
            .put("iso_settled", lockedIso)
            .put("exposure_capped_to_ns", if (exposureCapped) MAX_EXPOSURE_NS else JSONObject.NULL)
            .put("tonemap", if (manualPost) "CONTRAST_CURVE(sRGB,64pt)" else "FAST")
            .put("shading_mode", if (manualPost) "OFF" else "device_default")
            .put("zoom_ratio", 1.0)
            .put("ae_metered_on_roi", activeArray != null)
            .put("manual_sensor_supported", manualSensor)
            .put("manual_post_processing_supported", manualPost)
            .put("stabilisation", false)
            .put("hdr", false)
            .put("torch", if (torchOn) "on" else "off")
            .put("capture_mode", captureMode)
            .put("start_wall_ns", startWallNs)
            .put("led_block", JSONObject.NULL)
            .put("study_id", studyId)
            .put("clip_id", clipId)
        File(outDir, "${clipId}_meta.json").writeText(meta.toString(2))
    }

    private fun stopRecording(cancelled: Boolean) {
        recording = false
        try { session?.stopRepeating() } catch (_: Exception) {}
        try { recorder?.stop() } catch (_: Exception) {}
        recorder?.release(); recorder = null
        framesCsv?.flush(); framesCsv?.close(); framesCsv = null
        session?.close(); session = null
        camera?.close(); camera = null
        if (!cancelled) {
            setResult(RESULT_OK, Intent().putExtra(EXTRA_MP4, File(outDir, "$clipId.mp4").absolutePath))
            finish()
        } else {
            runOnUiThread { recordButton.text = "RECORD" }
        }
    }

    override fun onDestroy() {
        if (recording) stopRecording(cancelled = true)
        thread.quitSafely()
        super.onDestroy()
    }
}
