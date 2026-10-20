/*
 * PalmRecorderActivity: custom Camera2 recorder for the OnePlus 12 (protocol sections 4.6 and 5), launched from a
 * clip screen of the onboarding survey. Adapted from palmppg/capture/android/PalmRecorder.kt with a layout built in
 * code (no XML resources) and a result returned to the survey.
 *
 * 1920x1080 / 30 fps / H.264 / AAC audio (the sync beep is in the audio); 2 s auto settle, then AE, AWB and AF locked;
 * OIS and EIS off; scene modes, noise reduction and edge enhancement off; torch only in sequential capture mode.
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
    private var surfaceReady = false
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

    private fun backCameraId(): String {
        val cm = getSystemService(CAMERA_SERVICE) as CameraManager
        return cm.cameraIdList.first { id ->
            cm.getCameraCharacteristics(id).get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK
        }
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
        b.set(CaptureRequest.TONEMAP_MODE, CameraMetadata.TONEMAP_MODE_FAST)
        b.set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(30, 30))
        b.set(CaptureRequest.FLASH_MODE, if (torchOn) CameraMetadata.FLASH_MODE_TORCH else CameraMetadata.FLASH_MODE_OFF)
        b.set(CaptureRequest.CONTROL_AE_LOCK, lock)
        b.set(CaptureRequest.CONTROL_AWB_LOCK, lock)
        if (lock && lockedFocusDistance >= 0f) {
            b.set(CaptureRequest.CONTROL_AF_MODE, CameraMetadata.CONTROL_AF_MODE_OFF)
            b.set(CaptureRequest.LENS_FOCUS_DISTANCE, lockedFocusDistance)
        } else {
            b.set(CaptureRequest.CONTROL_AF_MODE, CameraMetadata.CONTROL_AF_MODE_AUTO)
        }
    }

    private val frameLogger = object : CameraCaptureSession.CaptureCallback() {
        override fun onCaptureCompleted(s: CameraCaptureSession, req: CaptureRequest, result: TotalCaptureResult) {
            val ts = result.get(CaptureResult.SENSOR_TIMESTAMP) ?: return
            val iso = result.get(CaptureResult.SENSOR_SENSITIVITY) ?: -1
            val exp = result.get(CaptureResult.SENSOR_EXPOSURE_TIME) ?: -1L
            val focus = result.get(CaptureResult.LENS_FOCUS_DISTANCE) ?: -1f
            if (!recording) { lockedIso = iso; lockedExposureNs = exp; lockedFocusDistance = focus; return }
            val wallNs = System.currentTimeMillis() * 1_000_000L
            framesCsv?.write("$frameIdx,$ts,$wallNs,$iso,$exp\n")
            frameIdx += 1
        }
    }

    private fun startRecording() {
        if (!surfaceReady) return
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) return
        val cm = getSystemService(CAMERA_SERVICE) as CameraManager
        cm.openCamera(backCameraId(), object : CameraDevice.StateCallback() {
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
                settle.set(CaptureRequest.CONTROL_AF_TRIGGER, CameraMetadata.CONTROL_AF_TRIGGER_START)
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
            .put("iso", lockedIso)
            .put("exposure_ns", lockedExposureNs)
            .put("wb_locked", true)
            .put("focus_locked", lockedFocusDistance >= 0f)
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
