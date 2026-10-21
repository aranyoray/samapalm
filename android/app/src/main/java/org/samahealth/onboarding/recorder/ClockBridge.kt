package org.samahealth.onboarding.recorder

import android.hardware.camera2.CameraMetadata
import android.os.SystemClock

/**
 * Puts the camera and the ECG on one clock.
 *
 * The study reference clock is CLOCK_BOOTTIME (CONTRACTS 3.2), which Android exposes as
 * [SystemClock.elapsedRealtimeNanos]. BLE ECG packets are stamped with it directly. Camera
 * `SENSOR_TIMESTAMP` is only on that clock when the sensor advertises
 * `SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME`; otherwise it is CLOCK_MONOTONIC ([System.nanoTime]).
 * The two differ by however long the device has spent suspended since boot, so treating them as
 * interchangeable is not a small error — it is hours on a phone that has been asleep overnight.
 * Every camera timestamp therefore goes through [toReferenceNs].
 */
class ClockBridge(private val timestampSource: Int?) {

    val sourceIsRealtime =
        timestampSource == CameraMetadata.SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME

    val sourceName: String = when (timestampSource) {
        CameraMetadata.SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME -> "REALTIME"
        CameraMetadata.SENSOR_INFO_TIMESTAMP_SOURCE_UNKNOWN -> "UNKNOWN"
        null -> "unavailable"
        else -> "other($timestampSource)"
    }

    /** boottime minus monotonic, in ns. Zero and unused when the sensor is already on boottime. */
    @Volatile var offsetNs: Long = 0L; private set

    /** Half the shortest read window achieved while measuring — the bound on [offsetNs]. */
    @Volatile var offsetUncertaintyNs: Long = Long.MAX_VALUE; private set

    /**
     * Brackets a monotonic read between two boottime reads and keeps the tightest bracket of
     * [rounds]. Both clocks are read on one thread microseconds apart, so the tightest bracket
     * pins the offset to well under a frame period.
     */
    fun measure(rounds: Int = 64) {
        var bestWindow = Long.MAX_VALUE
        var bestOffset = offsetNs
        repeat(rounds) {
            val b0 = SystemClock.elapsedRealtimeNanos()
            val m = System.nanoTime()
            val b1 = SystemClock.elapsedRealtimeNanos()
            val window = b1 - b0
            if (window in 0 until bestWindow) {
                bestWindow = window
                bestOffset = (b0 + b1) / 2 - m
            }
        }
        if (bestWindow != Long.MAX_VALUE) {
            offsetNs = bestOffset
            offsetUncertaintyNs = bestWindow / 2
        }
    }

    fun toReferenceNs(sensorTs: Long): Long =
        if (sourceIsRealtime) sensorTs else sensorTs + offsetNs

    /**
     * Re-measures and returns how far the offset moved since the last [measure]. Non-zero means
     * the device suspended mid-session, which invalidates frames stamped before the drift.
     */
    fun remeasureDriftNs(): Long {
        val before = offsetNs
        measure()
        return offsetNs - before
    }
}
