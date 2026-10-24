package org.samahealth.onboarding.quality

import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import org.samahealth.quality.RoiSeries
import java.io.File
import java.nio.ByteBuffer

/**
 * The pure arithmetic behind [Mp4Roi], kept apart from the codec so it can be unit-tested on a JVM.
 * BT.601 limited range, the conversion the camera stack writes for recorded video.
 */
object Yuv {
    /** The centred analysis window, the same fraction of the frame the in-app recorder meters (D-033). */
    fun roiRect(width: Int, height: Int, fraction: Float): IntArray {
        val half = fraction / 2f
        val x0 = ((0.5f - half) * width).toInt().coerceIn(0, width - 1)
        val x1 = ((0.5f + half) * width).toInt().coerceIn(x0 + 1, width)
        val y0 = ((0.5f - half) * height).toInt().coerceIn(0, height - 1)
        val y1 = ((0.5f + half) * height).toInt().coerceIn(y0 + 1, height)
        return intArrayOf(x0, y0, x1, y1)
    }

    fun r(y: Int, u: Int, v: Int): Double = clamp8(1.164 * (y - 16) + 1.596 * (v - 128))

    fun g(y: Int, u: Int, v: Int): Double = clamp8(1.164 * (y - 16) - 0.813 * (v - 128) - 0.391 * (u - 128))

    fun b(y: Int, u: Int, v: Int): Double = clamp8(1.164 * (y - 16) + 2.018 * (u - 128))

    fun clamp8(x: Double): Double = if (x < 0.0) 0.0 else if (x > 255.0) 255.0 else x

    /** A pixel counts as clipped when its luma is at or above this (the recorder's rule). */
    const val CLIP_LEVEL = 250
}

/** One frame's ROI means, accumulated pixel by pixel. */
internal class FrameStats {
    var n = 0
    var sy = 0.0
    var sr = 0.0
    var sg = 0.0
    var sb = 0.0
    var clipped = 0
    private val gridSum = DoubleArray(9)
    private val gridN = IntArray(9)

    fun add(y: Int, u: Int, v: Int, cell: Int) {
        n++
        sy += y.toDouble()
        sr += Yuv.r(y, u, v)
        sg += Yuv.g(y, u, v)
        sb += Yuv.b(y, u, v)
        if (y >= Yuv.CLIP_LEVEL) clipped++
        gridSum[cell] += y.toDouble()
        gridN[cell]++
    }

    fun grid(): DoubleArray = DoubleArray(9) { if (gridN[it] > 0) gridSum[it] / gridN[it] else 0.0 }
}

/**
 * Reduces a recorded MP4 to the same [RoiSeries] the in-app recorder logs, so one scorer serves clips taken with
 * the app and clips taken with another camera app. Decodes in ByteBuffer mode (no surface), reads the
 * YUV_420_888 planes with their strides, averages the centred ROI over every 4th pixel, and uses the frame's
 * presentation time as its timestamp.
 */
object Mp4Roi {
    private const val ROI_FRACTION = 0.40f
    private const val STEP = 4
    private const val TIMEOUT_US = 10_000L

    fun read(file: File, onProgress: (Float) -> Unit = {}): RoiSeries {
        val extractor = MediaExtractor()
        extractor.setDataSource(file.absolutePath)
        var track = -1
        var format: MediaFormat? = null
        for (i in 0 until extractor.trackCount) {
            val f = extractor.getTrackFormat(i)
            if (f.getString(MediaFormat.KEY_MIME)?.startsWith("video/") == true) {
                track = i
                format = f
                break
            }
        }
        require(track >= 0 && format != null) { "no video track in ${file.name}" }
        extractor.selectTrack(track)
        val durationUs = if (format.containsKey(MediaFormat.KEY_DURATION)) format.getLong(MediaFormat.KEY_DURATION) else 0L

        val codec = MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME)!!)
        codec.configure(format, null, null, 0)
        codec.start()

        val tS = ArrayList<Double>()
        val rs = ArrayList<Double>()
        val gs = ArrayList<Double>()
        val bs = ArrayList<Double>()
        val ys = ArrayList<Double>()
        val clip = ArrayList<Double>()
        val grids = ArrayList<DoubleArray>()
        val info = MediaCodec.BufferInfo()
        var sawInputEos = false
        var sawOutputEos = false

        try {
            while (!sawOutputEos) {
                if (!sawInputEos) {
                    val inIdx = codec.dequeueInputBuffer(TIMEOUT_US)
                    if (inIdx >= 0) {
                        val buf: ByteBuffer = codec.getInputBuffer(inIdx)!!
                        val size = extractor.readSampleData(buf, 0)
                        if (size < 0) {
                            codec.queueInputBuffer(inIdx, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            sawInputEos = true
                        } else {
                            codec.queueInputBuffer(inIdx, 0, size, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                    }
                }
                val outIdx = codec.dequeueOutputBuffer(info, TIMEOUT_US)
                if (outIdx >= 0) {
                    if (info.size > 0) {
                        val image = codec.getOutputImage(outIdx)
                        if (image != null) {
                            val st = measure(image)
                            if (st != null && st.n > 0) {
                                tS.add(info.presentationTimeUs / 1e6)
                                ys.add(st.sy / st.n)
                                rs.add(st.sr / st.n)
                                gs.add(st.sg / st.n)
                                bs.add(st.sb / st.n)
                                clip.add(st.clipped.toDouble() / st.n)
                                grids.add(st.grid())
                            }
                            image.close()
                        }
                    }
                    codec.releaseOutputBuffer(outIdx, false)
                    if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) sawOutputEos = true
                    if (durationUs > 0) onProgress((info.presentationTimeUs.toFloat() / durationUs).coerceIn(0f, 1f))
                } else if (outIdx == MediaCodec.INFO_TRY_AGAIN_LATER && sawInputEos) {
                    // the decoder has nothing more to give
                    if (tS.isNotEmpty()) sawOutputEos = true
                }
            }
        } finally {
            runCatching { codec.stop() }
            codec.release()
            extractor.release()
        }
        onProgress(1f)

        val t0 = tS.firstOrNull() ?: 0.0
        val grid = if (grids.isEmpty()) null else Array(9) { k -> DoubleArray(grids.size) { grids[it][k] } }
        return RoiSeries(
            tS = DoubleArray(tS.size) { tS[it] - t0 },
            r = rs.toDoubleArray(), g = gs.toDoubleArray(), b = bs.toDoubleArray(), y = ys.toDoubleArray(),
            clipFrac = clip.toDoubleArray(), grid = grid,
        )
    }

    /** Averages the centred ROI of one decoded frame; null when the planes are not the expected 4:2:0 layout. */
    private fun measure(image: android.media.Image): FrameStats? {
        val planes = image.planes
        if (planes.size < 3) return null
        val w = image.width
        val h = image.height
        val (x0, y0, x1, y1) = Yuv.roiRect(w, h, ROI_FRACTION).let { listOf(it[0], it[1], it[2], it[3]) }
        val yBuf = planes[0].buffer
        val uBuf = planes[1].buffer
        val vBuf = planes[2].buffer
        val yRow = planes[0].rowStride
        val yPix = planes[0].pixelStride
        val uRow = planes[1].rowStride
        val uPix = planes[1].pixelStride
        val vRow = planes[2].rowStride
        val vPix = planes[2].pixelStride
        val st = FrameStats()
        val cw = (x1 - x0).coerceAtLeast(1)
        val ch = (y1 - y0).coerceAtLeast(1)
        var yy = y0
        while (yy < y1) {
            var xx = x0
            while (xx < x1) {
                val yi = yy * yRow + xx * yPix
                val ci = (yy / 2) * uRow + (xx / 2) * uPix
                val vi = (yy / 2) * vRow + (xx / 2) * vPix
                if (yi < yBuf.limit() && ci < uBuf.limit() && vi < vBuf.limit()) {
                    val yv = yBuf.get(yi).toInt() and 0xFF
                    val uv = uBuf.get(ci).toInt() and 0xFF
                    val vv = vBuf.get(vi).toInt() and 0xFF
                    val cell = ((yy - y0) * 3 / ch).coerceIn(0, 2) * 3 + ((xx - x0) * 3 / cw).coerceIn(0, 2)
                    st.add(yv, uv, vv, cell)
                }
                xx += STEP
            }
            yy += STEP
        }
        return st
    }

    private operator fun <T> List<T>.component4(): T = this[3]
}
