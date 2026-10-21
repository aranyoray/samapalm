package org.swht.palm

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View

/**
 * Live ECG and palm-ROI traces, one above the other on a shared time axis. This is a positioning
 * aid, not data: both are auto-scaled to their own range so a flat trace still fills the band.
 */
class TraceView(context: Context, attrs: AttributeSet?) : View(context, attrs) {

    var ecg: BleKardia? = null
    var camera: CameraRig? = null

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
    private val midline = Paint().apply {
        strokeWidth = 1f; color = Color.rgb(0x26, 0x3A, 0x40)
    }
    private val label = Paint().apply {
        color = Color.rgb(0x90, 0xA4, 0xAE); textSize = 22f; isAntiAlias = true
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val halfH = height / 2f
        canvas.drawLine(0f, halfH, width.toFloat(), halfH, midline)

        ecg?.let { drawRing(canvas, it.traceRing, it.traceWriteIdx, 0f, halfH, ecgPaint, null) }
        canvas.drawText("ECG lead I", 8f, 24f, label)

        camera?.let {
            drawRing(canvas, it.ppgRing, it.ppgWriteIdx, halfH, halfH, ppgPaint, it.peakRing)
        }
        val bpm = camera?.pulse?.bpm ?: 0.0
        canvas.drawText(
            if (bpm > 0) "palm pulse  ~%.0f bpm".format(bpm) else "palm pulse",
            8f, halfH + 24f, label
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
        val pad = bandH * 0.12f
        val usable = bandH - 2 * pad
        val dx = width.toFloat() / (n - 1)
        var prevX = 0f
        var prevY = 0f
        for (i in 0 until n) {
            val v = ring[(writeIdx + i) % n]
            val x = i * dx
            val y = top + pad + usable * (1f - (v - lo) / span)
            if (i > 0) canvas.drawLine(prevX, prevY, x, y, paint)
            if (peaks != null && peaks[(writeIdx + i) % n]) {
                canvas.drawCircle(x, y, 5f, peakPaint)
            }
            prevX = x
            prevY = y
        }
    }
}
