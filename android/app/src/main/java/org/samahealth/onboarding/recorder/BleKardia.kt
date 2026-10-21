package org.samahealth.onboarding.recorder

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import android.os.SystemClock
import android.util.Log
import java.io.BufferedWriter
import java.io.File
import java.io.FileWriter
import java.security.MessageDigest
import java.util.UUID

/**
 * BLE path for KardiaMobile 6L / Card class devices (they do not use the ultrasonic audio channel).
 * Protocol per public interop notes (github.com/ShaneBreazeale/kardia-rs):
 *
 *   service  ac060001-328c-a28f-9846-5a8aa212661b
 *   command  ac060002-...  (write + indicate; requires bonded/encrypted link)
 *   ecg      ac060003-...  (notify)
 *
 * Startup: bond -> enable command indications -> write "M2 <token>" where token = 'K' + first 8 bytes
 * of SHA-256("Triangle" + advertised device name) as lowercase hex -> enable ECG notifications.
 * Stream: 36-byte packets, 9 interleaved little-endian int16 pairs (lead I, lead II), 300 Hz/channel.
 * Provisional scale: mV = raw * 10 / 65536 (10 mV pk-pk, 14-bit left-aligned) — NOT electrically
 * calibrated, carried through to the outputs as a declared constant rather than applied silently.
 *
 * Timing. Packets are stamped with [SystemClock.elapsedRealtimeNanos] (CLOCK_BOOTTIME, the study
 * reference clock) on arrival, but arrival is later than the sample by an unknown BLE transport
 * delay that varies packet to packet. A per-packet stamp would therefore inherit that jitter. The
 * session instead records raw arrivals and recovers the sample timeline at stop from the *lower
 * envelope* of arrival times (see [finalise]): the least-delayed packets lie closest to the true
 * sample instants, and a line through the early and late minima recovers both the offset and the
 * device's actual sample rate. The residual bias is the minimum achievable transport delay, which
 * is constant within a session and is reported, not hidden.
 */
@SuppressLint("MissingPermission")
class BleKardia(private val context: Context) {

    companion object {
        private const val TAG = "BleKardia"
        val SERVICE_UUID: UUID = UUID.fromString("ac060001-328c-a28f-9846-5a8aa212661b")
        val CCCD_UUID: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
        const val ECG_FS = 300
        const val MV_PER_COUNT = 10.0 / 65536.0
        const val SAMPLE_NS = 1_000_000_000L / ECG_FS
        /** Arrival later than the running minimum by more than this means samples were dropped. */
        private const val GAP_NS = 100_000_000L

        fun unlockToken(deviceName: String): String {
            val digest = MessageDigest.getInstance("SHA-256")
                .digest("Triangle$deviceName".toByteArray(Charsets.UTF_8))
            return "K" + digest.take(8).joinToString("") { "%02x".format(it) }
        }
    }

    @Volatile var statusLine = "BLE: idle"; private set
    @Volatile var streaming = false; private set
    @Volatile var packetCount = 0L; private set
    @Volatile var deviceName: String? = null; private set
    @Volatile var deviceAddress: String? = null; private set
    @Volatile var modeUsed: String? = null; private set
    @Volatile var heartRateBpm = 0.0; private set
    @Volatile var loggedSamples = 0L; private set

    /** ~3 s of lead I in mV for the on-screen trace. */
    val traceRing = FloatArray(3 * ECG_FS)
    @Volatile var traceWriteIdx = 0; private set

    private val handler = Handler(Looper.getMainLooper())
    private var gatt: BluetoothGatt? = null
    private var cmdChar: BluetoothGattCharacteristic? = null
    private var ecgChar: BluetoothGattCharacteristic? = null
    private var started = false
    private var triedM1Fallback = false
    private var bondReceiverRegistered = false
    private var pendingDevice: BluetoothDevice? = null
    @Volatile private var servicesDiscovered = false
    @Volatile private var connecting = false

    // ---- session capture state (guarded by logLock; BLE callbacks arrive on binder threads) ----
    private val logLock = Any()
    private var packetCsv: BufferedWriter? = null
    private var capturing = false
    private var globalSampleIdx = 0L
    private var runningMinAnchorNs = Long.MAX_VALUE
    private var gapCount = 0
    private var missingSamples = 0L
    private var lead1 = IntArray(64 * 1024)
    private var lead2 = IntArray(64 * 1024)
    private var nStored = 0
    /** One entry per packet: index of its last sample, and its arrival time. */
    private var pktEndIdx = LongArray(16 * 1024)
    private var pktRecvNs = LongArray(16 * 1024)
    private var nPkts = 0

    // HR display state
    private var peakEnv = 200.0
    private var lastPeakNs = -1L
    private var hrSmooth = 0.0

    private val adapter: BluetoothAdapter?
        get() = (context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter

    fun start() {
        if (started) return
        started = true
        startScan()
    }

    fun stop() {
        started = false
        handler.removeCallbacksAndMessages(null)
        try { adapter?.bluetoothLeScanner?.stopScan(scanCb) } catch (_: Exception) {}
        gatt?.close()
        gatt = null
        streaming = false
        if (bondReceiverRegistered) {
            context.unregisterReceiver(bondReceiver)
            bondReceiverRegistered = false
        }
        statusLine = "BLE: stopped"
    }

    // ---- capture ----

    /**
     * Begins buffering. The packet log is streamed to disk because it is the irreplaceable raw
     * record; the sample timeline is derived at [finalise] once the whole arrival envelope is known.
     */
    fun startCapture(packetLog: File) {
        synchronized(logLock) {
            globalSampleIdx = 0
            runningMinAnchorNs = Long.MAX_VALUE
            gapCount = 0
            missingSamples = 0
            nStored = 0
            nPkts = 0
            loggedSamples = 0
            packetCsv = BufferedWriter(FileWriter(packetLog)).apply {
                write("packet_idx,recv_ns,n_samples,first_sample_idx,hex\n")
            }
            capturing = true
        }
    }

    class Capture(
        val lead1: IntArray,
        val lead2: IntArray,
        /** Reference-clock (CLOCK_BOOTTIME) time of sample 0. */
        val t0RefNs: Long,
        /** Recovered sample period; 1e9/this is the device's measured rate. */
        val samplePeriodNs: Double,
        val measuredFsHz: Double,
        val gapCount: Int,
        val missingSamples: Long,
        val packetCount: Int,
        /** Spread of arrival delay above the recovered envelope: the transport jitter actually seen. */
        val arrivalJitterMedianNs: Long,
        val arrivalJitterP95Ns: Long,
        val envelopeFitUsed: String,
    ) {
        fun tRefNs(sampleIdx: Int): Long = t0RefNs + Math.round(sampleIdx * samplePeriodNs)
    }

    /**
     * Stops buffering and recovers the sample timeline from the lower envelope of packet arrivals.
     * A line through the minimum-delay packet of the first quarter and that of the last quarter
     * gives both the time origin and the true sample period; with too few packets it falls back to
     * the single minimum at the nominal rate.
     */
    fun finalise(): Capture? {
        synchronized(logLock) {
            capturing = false
            try { packetCsv?.flush(); packetCsv?.close() } catch (_: Exception) {}
            packetCsv = null
            if (nPkts < 2 || nStored == 0) return null

            fun minAnchorIn(from: Int, to: Int): Int {
                var best = from
                var bestVal = Long.MAX_VALUE
                for (i in from until to) {
                    val a = pktRecvNs[i] - pktEndIdx[i] * SAMPLE_NS
                    if (a < bestVal) { bestVal = a; best = i }
                }
                return best
            }

            val quarter = maxOf(1, nPkts / 4)
            val iEarly = minAnchorIn(0, quarter)
            val iLate = minAnchorIn(nPkts - quarter, nPkts)

            var periodNs = SAMPLE_NS.toDouble()
            var t0 = pktRecvNs[iEarly] - pktEndIdx[iEarly] * SAMPLE_NS
            var fit = "single_min_nominal_rate"
            val dIdx = pktEndIdx[iLate] - pktEndIdx[iEarly]
            if (dIdx > ECG_FS) {
                val p = (pktRecvNs[iLate] - pktRecvNs[iEarly]).toDouble() / dIdx
                // reject a nonsense slope (lost connection, huge stall) and keep the nominal rate
                if (p > SAMPLE_NS * 0.9 && p < SAMPLE_NS * 1.1) {
                    periodNs = p
                    t0 = pktRecvNs[iEarly] - Math.round(pktEndIdx[iEarly] * p)
                    fit = "lower_envelope_two_point"
                }
            }

            val delays = LongArray(nPkts) { i ->
                pktRecvNs[i] - (t0 + Math.round(pktEndIdx[i] * periodNs))
            }
            delays.sort()
            val median = delays[nPkts / 2]
            val p95 = delays[minOf(nPkts - 1, (nPkts * 95) / 100)]

            return Capture(
                lead1 = lead1.copyOf(nStored),
                lead2 = lead2.copyOf(nStored),
                t0RefNs = t0,
                samplePeriodNs = periodNs,
                measuredFsHz = 1.0e9 / periodNs,
                gapCount = gapCount,
                missingSamples = missingSamples,
                packetCount = nPkts,
                arrivalJitterMedianNs = median,
                arrivalJitterP95Ns = p95,
                envelopeFitUsed = fit,
            )
        }
    }

    // ---- scan ----

    private fun startScan() {
        val a = adapter
        val scanner = if (a?.isEnabled == true) a.bluetoothLeScanner else null
        if (scanner == null) {
            statusLine = "BLE: bluetooth off, retrying…"
            handler.postDelayed({ if (started) startScan() }, 5000)
            return
        }
        statusLine = "BLE: scanning…"
        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build()
        try {
            scanner.startScan(null, settings, scanCb)
        } catch (e: SecurityException) {
            statusLine = "BLE: no permission"
        }
    }

    private val scanCb = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            val name = result.scanRecord?.deviceName ?: result.device.name
            val uuids = result.scanRecord?.serviceUuids ?: emptyList<ParcelUuid>()
            val isKardia = uuids.any { it.uuid == SERVICE_UUID } ||
                (name?.contains("kardia", ignoreCase = true) == true)
            if (!isKardia || connecting) return
            connecting = true
            try { adapter?.bluetoothLeScanner?.stopScan(this) } catch (_: Exception) {}
            deviceName = name
            deviceAddress = result.device.address
            statusLine = "BLE: found ${name ?: result.device.address}"
            connect(result.device)
        }
    }

    // ---- connect / bond ----

    private fun connect(device: BluetoothDevice) {
        if (device.bondState != BluetoothDevice.BOND_BONDED) {
            pendingDevice = device
            if (!bondReceiverRegistered) {
                context.registerReceiver(
                    bondReceiver, IntentFilter(BluetoothDevice.ACTION_BOND_STATE_CHANGED)
                )
                bondReceiverRegistered = true
            }
            statusLine = "BLE: pairing… (accept dialog)"
            if (!device.createBond()) gattConnect(device)
        } else {
            gattConnect(device)
        }
    }

    private val bondReceiver = object : BroadcastReceiver() {
        override fun onReceive(c: Context, intent: Intent) {
            val state = intent.getIntExtra(BluetoothDevice.EXTRA_BOND_STATE, -1)
            val dev = pendingDevice ?: return
            if (state == BluetoothDevice.BOND_BONDED) {
                statusLine = "BLE: bonded"
                gattConnect(dev)
            } else if (state == BluetoothDevice.BOND_NONE) {
                statusLine = "BLE: bond failed, rescanning"
                connecting = false
                handler.postDelayed({ if (started) startScan() }, 2000)
            }
        }
    }

    private fun gattConnect(device: BluetoothDevice) {
        statusLine = "BLE: connecting…"
        gatt = device.connectGatt(context, false, gattCb, BluetoothDevice.TRANSPORT_LE)
    }

    // ---- GATT state machine ----

    private val gattCb = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                statusLine = "BLE: discovering…"
                servicesDiscovered = false
                g.requestMtu(64)
                handler.postDelayed({ if (!servicesDiscovered) g.discoverServices() }, 3000)
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                streaming = false
                connecting = false
                statusLine = "BLE: disconnected"
                g.close()
                if (started) handler.postDelayed({ if (started) startScan() }, 1500)
            }
        }

        override fun onMtuChanged(g: BluetoothGatt, mtu: Int, status: Int) {
            if (!servicesDiscovered) g.discoverServices()
        }

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            servicesDiscovered = true
            triedM1Fallback = false
            val svc = g.getService(SERVICE_UUID)
                ?: g.services.firstOrNull {
                    it.uuid.toString().startsWith("ac0") && it.characteristics.size >= 2
                }
            if (svc == null) {
                statusLine = "BLE: no Kardia service"
                g.disconnect()
                return
            }
            cmdChar = svc.characteristics.firstOrNull {
                it.properties and BluetoothGattCharacteristic.PROPERTY_WRITE != 0 &&
                    it.properties and BluetoothGattCharacteristic.PROPERTY_INDICATE != 0
            }
            ecgChar = svc.characteristics.firstOrNull {
                it != cmdChar && it.properties and BluetoothGattCharacteristic.PROPERTY_NOTIFY != 0
            }
            if (cmdChar == null || ecgChar == null) {
                statusLine = "BLE: chars missing"
                g.disconnect()
                return
            }
            statusLine = "BLE: unlocking…"
            enableCccd(g, cmdChar!!, indicate = true)
        }

        override fun onDescriptorWrite(g: BluetoothGatt, d: BluetoothGattDescriptor, status: Int) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                statusLine = "BLE: subscribe failed ($status), reconnecting"
                g.disconnect()
                return
            }
            when (d.characteristic) {
                cmdChar -> writeModeCommand(g, "M2")
                ecgChar -> {
                    statusLine = "BLE: waiting for stream…"
                    val before = packetCount
                    handler.postDelayed({
                        if (packetCount == before && !triedM1Fallback) {
                            triedM1Fallback = true
                            writeModeCommand(g, "M1")
                        }
                    }, 4000)
                }
            }
        }

        override fun onCharacteristicWrite(
            g: BluetoothGatt, ch: BluetoothGattCharacteristic, status: Int
        ) {
            if (ch == cmdChar) {
                if (status == BluetoothGatt.GATT_SUCCESS) enableCccd(g, ecgChar!!, indicate = false)
                else statusLine = "BLE: unlock write failed ($status)"
            }
        }

        @Deprecated("pre-33 callback")
        @Suppress("OVERRIDE_DEPRECATION")
        override fun onCharacteristicChanged(g: BluetoothGatt, ch: BluetoothGattCharacteristic) {
            // API 33+ fires both this and the value-carrying overload for one notification
            if (Build.VERSION.SDK_INT >= 33) return
            @Suppress("DEPRECATION")
            handlePacket(ch, ch.value ?: return)
        }

        override fun onCharacteristicChanged(
            g: BluetoothGatt, ch: BluetoothGattCharacteristic, value: ByteArray
        ) {
            handlePacket(ch, value)
        }
    }

    private fun enableCccd(g: BluetoothGatt, ch: BluetoothGattCharacteristic, indicate: Boolean) {
        g.setCharacteristicNotification(ch, true)
        val d = ch.getDescriptor(CCCD_UUID) ?: return
        val v = if (indicate) BluetoothGattDescriptor.ENABLE_INDICATION_VALUE
        else BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
        @Suppress("DEPRECATION")
        d.value = v
        @Suppress("DEPRECATION")
        g.writeDescriptor(d)
    }

    private fun writeModeCommand(g: BluetoothGatt, mode: String) {
        val name = deviceName ?: "Kardia6L"
        val cmd = "$mode ${unlockToken(name)}"
        modeUsed = mode
        Log.i(TAG, "unlock: $cmd")
        val ch = cmdChar ?: return
        @Suppress("DEPRECATION")
        ch.value = cmd.toByteArray(Charsets.UTF_8)
        ch.writeType = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
        @Suppress("DEPRECATION")
        g.writeCharacteristic(ch)
    }

    // ---- data ----

    private fun grow() {
        if (nStored + 64 > lead1.size) {
            lead1 = lead1.copyOf(lead1.size * 2)
            lead2 = lead2.copyOf(lead2.size * 2)
        }
        if (nPkts + 1 > pktEndIdx.size) {
            pktEndIdx = pktEndIdx.copyOf(pktEndIdx.size * 2)
            pktRecvNs = pktRecvNs.copyOf(pktRecvNs.size * 2)
        }
    }

    private fun handlePacket(ch: BluetoothGattCharacteristic, value: ByteArray) {
        if (ch == cmdChar) {
            Log.i(TAG, "cmd indication: ${value.joinToString(" ") { "%02x".format(it) }}")
            return
        }
        if (ch != ecgChar) return
        val recvNs = SystemClock.elapsedRealtimeNanos()
        packetCount += 1
        streaming = true
        statusLine = "BLE: streaming ${deviceName ?: ""} ($modeUsed)"

        val pairs = value.size / 4
        val singleChannel = pairs == 0 && value.size >= 2
        val nSamples = if (singleChannel) value.size / 2 else pairs
        if (nSamples == 0) return

        synchronized(logLock) {
            if (!capturing) {
                // not recording: keep the trace and HR alive for positioning, nothing persisted
                for (i in 0 until nSamples) {
                    val off = if (singleChannel) i * 2 else i * 4
                    updateTraceAndHr(decode(value, off), recvNs)
                }
                return
            }
            grow()

            // A packet far later than the running envelope means notifications were dropped;
            // advance the sample index over the hole so index stays proportional to time.
            val provisionalEnd = globalSampleIdx + nSamples
            val anchor = recvNs - provisionalEnd * SAMPLE_NS
            if (runningMinAnchorNs != Long.MAX_VALUE && anchor - runningMinAnchorNs > GAP_NS) {
                val missing = (anchor - runningMinAnchorNs) / SAMPLE_NS
                globalSampleIdx += missing
                missingSamples += missing
                gapCount += 1
                for (k in 0 until missing) {
                    if (nStored + 1 > lead1.size) {
                        lead1 = lead1.copyOf(lead1.size * 2)
                        lead2 = lead2.copyOf(lead2.size * 2)
                    }
                    lead1[nStored] = 0
                    lead2[nStored] = 0
                    nStored++
                }
            }

            val endIdx = globalSampleIdx + nSamples
            val finalAnchor = recvNs - endIdx * SAMPLE_NS
            if (finalAnchor < runningMinAnchorNs) runningMinAnchorNs = finalAnchor

            pktEndIdx[nPkts] = endIdx
            pktRecvNs[nPkts] = recvNs
            nPkts++

            packetCsv?.write(
                "${nPkts - 1},$recvNs,$nSamples,$globalSampleIdx," +
                    value.joinToString("") { "%02x".format(it) } + "\n"
            )

            for (i in 0 until nSamples) {
                val off = if (singleChannel) i * 2 else i * 4
                val ch1 = decode(value, off)
                val ch2 = if (singleChannel) 0 else decode(value, off + 2)
                lead1[nStored] = ch1
                lead2[nStored] = ch2
                nStored++
                loggedSamples++
                updateTraceAndHr(ch1, recvNs)
            }
            globalSampleIdx = endIdx
            if (nPkts % 100 == 0) {
                try { packetCsv?.flush() } catch (_: Exception) {}
            }
        }
    }

    private fun decode(v: ByteArray, off: Int): Int =
        ((v[off].toInt() and 0xFF) or (v[off + 1].toInt() shl 8)).toShort().toInt()

    private fun updateTraceAndHr(rawCh1: Int, tNs: Long) {
        traceRing[traceWriteIdx] = (rawCh1 * MV_PER_COUNT).toFloat()
        traceWriteIdx = (traceWriteIdx + 1) % traceRing.size

        val v = Math.abs(rawCh1.toDouble())
        peakEnv = maxOf(v, peakEnv * 0.999)
        if (v > 0.6 * peakEnv && peakEnv > 500) {
            if (lastPeakNs > 0 && tNs - lastPeakNs > 250_000_000L) {
                val bpm = 60e9 / (tNs - lastPeakNs)
                if (bpm in 25.0..220.0) {
                    hrSmooth = if (hrSmooth == 0.0) bpm else 0.7 * hrSmooth + 0.3 * bpm
                    heartRateBpm = hrSmooth
                }
                lastPeakNs = tNs
            } else if (lastPeakNs < 0) {
                lastPeakNs = tNs
            }
        }
    }
}
