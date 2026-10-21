package org.samahealth.onboarding.recorder

import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.zip.CRC32

/**
 * Writes AliveCor ATC v1 files byte-compatible with `palmppg/ecg/atc.py` (CONTRACTS 3.6), so a BLE
 * capture enters the pipeline through the same parser as a real Kardia export.
 *
 * Scale: the device streams int16 counts whose provisional mV scale is 10 mV / 65536 =
 * 152.587890625 nV per count (uncalibrated, see [BleKardia]). `fmt ` carries an integer nV/LSB, so
 * counts are stored 1:1 at [RESOLUTION_NV] = 153 and the parser reads back 0.27 % high. That bias is
 * far below the unknown true gain it sits on top of; the exact figure is written to kardia_meta.json
 * so a calibrated scale can replace it without re-reading the ATC.
 */
object AtcWriter {

    const val RESOLUTION_NV = 153
    const val EXACT_NV_PER_COUNT = 1.0e6 * BleKardia.MV_PER_COUNT

    private val MAGIC = "ALIVE".toByteArray(Charsets.US_ASCII)
    private val VERSION = byteArrayOf(1, 0, 0)

    private val INFO_FIELDS = listOf(
        "date" to 32, "uuid" to 40, "phone_udid" to 44, "phone_model" to 32,
        "recorder_sw" to 32, "recorder_hw" to 32, "location" to 52,
    )

    private fun fixedAscii(value: String?, width: Int): ByteArray {
        val raw = (value ?: "").map { if (it.code in 32..126) it.code.toByte() else '?'.code.toByte() }
            .take(width).toByteArray()
        return raw + ByteArray(width - raw.size)
    }

    private fun chunk(id: String, payload: ByteArray): ByteArray {
        val idBytes = id.toByteArray(Charsets.US_ASCII)
        require(idBytes.size == 4) { "block id must be 4 bytes, got '$id'" }
        val crc = CRC32().apply { update(idBytes); update(payload) }.value
        return ByteBuffer.allocate(12 + payload.size).order(ByteOrder.LITTLE_ENDIAN)
            .putInt(payload.size)
            .put(idBytes)
            .put(payload)
            .putInt(crc.toInt())
            .array()
    }

    /**
     * @param samples lead-I device counts, written verbatim as int16.
     * @param startIso ISO8601 wall-clock time of the first sample, for the info date field.
     */
    fun write(
        file: File,
        samples: IntArray,
        fsHz: Int,
        startIso: String,
        info: Map<String, String> = emptyMap(),
    ) {
        val fields = INFO_FIELDS.associate { (name, _) -> name to (info[name] ?: "") }.toMutableMap()
        fields["date"] = startIso
        val infoPayload = INFO_FIELDS.fold(ByteArray(0)) { acc, (name, width) ->
            acc + fixedAscii(fields[name], width)
        }

        val fmtPayload = ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN)
            .put(1)                             // format
            .putShort(fsHz.toShort())           // frequency Hz
            .putShort(RESOLUTION_NV.toShort())  // resolution nV/LSB
            .put(0)                             // flags
            .putShort(0)                        // reserved
            .array()

        val ecgPayload = ByteBuffer.allocate(samples.size * 2).order(ByteOrder.LITTLE_ENDIAN).also { b ->
            for (s in samples) b.putShort(s.coerceIn(-32768, 32767).toShort())
        }.array()

        file.outputStream().buffered().use { out ->
            out.write(MAGIC)
            out.write(VERSION)
            out.write(chunk("info", infoPayload))
            out.write(chunk("fmt ", fmtPayload))
            out.write(chunk("ecg ", ecgPayload))
        }
    }
}
