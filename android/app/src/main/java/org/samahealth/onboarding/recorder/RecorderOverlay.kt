package org.samahealth.onboarding.recorder

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.view.View

/**
 * ROI box and live traces drawn over the preview: lead I from the Kardia on top, the detrended palm
 * ROI with detected beats below.
 *
 * The ROI box is drawn on the same fraction of the same rectangle that [PalmRecorderActivity]
 * averages, so what the operator lines the palm up with is what the analyser reads. The traces are
 * a positioning aid, auto-scaled to their own range; neither is the measurement.
 */
class RecorderOverlay(context: Context) : View(context) {

    var ecg: BleKardia? = null
    var pulse: PulseMeter? = null
    var ppgRing: FloatArray? = null
    var peakRing: BooleanArray? = null
    @Volatile var ppgWriteIdx = 0

    private val box = Paint().apply {
        style = Paint.Style.STROKE; strokeWidth = 3f
        color = Color.argb(200, 255, 235, 59)
    }
    private val ecgPaint = Paint().apply {
        style = Paint.Style.STROKE; strokeWidth = 2f; isAntiAlias = true
        color = Color.rgb(0x4F, 0xC3, 0xF7)
    }
    private val ppgPaint = Paint().apply {
        style = Paint.Style.STROKE; strokeWidth = 2f; isAntiAlias = true
        color = Color.rgb(0x81, 0xC7, 0x84)
    }
    private val peakPaint = Paint().apply {
        style = Paint.Style.FILL; isAntiAlias = true
        color = Color.rgb(0xFF, 0xD5, 0x4F)
    }
    private val panel = Paint().apply { color = Color.argb(140, 0, 0, 0) }
    private val label = Paint().apply {
        color = Color.argb(220, 0xCF, 0xD8, 0xDC); textSize = 24f; isAntiAlias = true
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat()
        val h = height.toFloat()

        val half = PalmRecorderActivity.ROI_FRACTION / 2f
        canvas.drawRect(
            (0.5f - half) * w, (0.5f - half) * h, (0.5f + half) * w, (0.5f + half) * h, box
        )
        canvas.drawText("palm ROI", (0.5f - half) * w, (0.5f - half) * h - 8f, label)

        // trace panel along the bottom
        val panelH = h * 0.30f
        val top = h - panelH
        canvas.drawRect(0f, top, w, h, panel)
        val bandH = panelH / 2f

        ecg?.let { drawRing(canvas, it.traceRing, it.traceWriteIdx, top, bandH, ecgPaint, null) }
        canvas.drawText("ECG lead I", 8f, top + 22f, label)

        val ring = ppgRing
        if (ring != null) {
            drawRing(canvas, ring, ppgWriteIdx, top + bandH, bandH, ppgPaint, peakRing)
        }
        val bpm = pulse?.bpm ?: 0.0
        canvas.drawText(
            if (bpm > 0) "palm pulse  ~%.0f bpm".format(bpm) else "palm pulse",
            8f, top + bandH + 22f, label
        )
    }

    private fun drawRing(
        canvas: Canvas, ring: FloatArray, writeIdx: Int, top: Float, bandH: Float, paint: Paint,
        peaks: BooleanArray?,
    ) {
        val n = ring.size
        if (n < 2) return
        var lo = Float.MAX_VALUE
        var hi = -Float.MAX_VALUE
        for (v in ring) {
            if (v < lo) lo = v
            if (v > hi) hi = v
        }
        val span = (hi - lo).takeIf { it > 1e-6f } ?: 1f
        val pad = bandH * 0.18f
        val usable = bandH - 2 * pad
        val dx = width.toFloat() / (n - 1)
        var prevX = 0f
        var prevY = 0f
        for (i in 0 until n) {
            val idx = (writeIdx + i) % n
            val y = top + pad + usable * (1f - (ring[idx] - lo) / span)
            val x = i * dx
            if (i > 0) canvas.drawLine(prevX, prevY, x, y, paint)
            if (peaks != null && peaks[idx]) canvas.drawCircle(x, y, 4f, peakPaint)
            prevX = x
            prevY = y
        }
    }
}
