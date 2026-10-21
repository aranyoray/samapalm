package org.swht.palm

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View

/**
 * Draws the measurement ROI so the operator positions the palm over the region actually sampled.
 *
 * The box is placed over the *image*, not over this view. With the preview letterboxed to show the
 * whole camera frame, the two differ, and a box drawn over the view would point at a region the
 * analyser never reads — worse than no box at all, because it looks authoritative.
 */
class RoiOverlay(context: Context, attrs: AttributeSet?) : View(context, attrs) {

    var rig: CameraRig? = null

    private val box = Paint().apply {
        style = Paint.Style.STROKE
        strokeWidth = 3f
        color = Color.argb(200, 255, 235, 59)
    }
    private val edge = Paint().apply {
        style = Paint.Style.STROKE
        strokeWidth = 1f
        color = Color.argb(90, 255, 235, 59)
    }
    private val label = Paint().apply {
        color = Color.argb(200, 255, 235, 59)
        textSize = 28f
        isAntiAlias = true
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val aspect = rig?.previewDisplayAspect ?: 0f

        // the letterboxed image rectangle inside this view
        var iw = width.toFloat()
        var ih = height.toFloat()
        if (aspect > 0f) {
            if (iw / ih > aspect) iw = ih * aspect else ih = iw / aspect
        }
        val ix = (width - iw) / 2f
        val iy = (height - ih) / 2f
        canvas.drawRect(ix, iy, ix + iw, iy + ih, edge)

        val half = CameraRig.ROI_FRACTION / 2f
        val l = ix + (0.5f - half) * iw
        val t = iy + (0.5f - half) * ih
        val r = ix + (0.5f + half) * iw
        val b = iy + (0.5f + half) * ih
        canvas.drawRect(l, t, r, b, box)
        canvas.drawText("palm ROI", l, (t - 10f).coerceAtLeast(label.textSize), label)
    }
}
