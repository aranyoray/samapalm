package org.samahealth.crf

/**
 * Offline-safe PID allocation. Each tablet owns a block of numbers (configured in settings, e.g. 0001-0999 for
 * tablet A, 1000-1999 for tablet B), so two tablets working offline can never issue the same PID. Pre-printed
 * folder labels can be typed or scanned instead; the server's unique constraint is the final check.
 */
class PidAllocator(private val prefix: String = "SWHT-PP-003-", private val width: Int = 4) {
    fun format(n: Int): String = prefix + n.toString().padStart(width, '0')

    fun parse(pid: String): Int? = pid.takeIf { it.startsWith(prefix) }?.removePrefix(prefix)?.takeIf { it.length == width }?.toIntOrNull()

    /** Lowest unused number in [start, end], or null when the block is exhausted. */
    fun next(start: Int, end: Int, used: Collection<String>): String? {
        require(start in 1..end) { "invalid block $start-$end" }
        val taken = used.mapNotNull { parse(it) }.toHashSet()
        for (n in start..end) if (n !in taken) return format(n)
        return null
    }

    fun inBlock(pid: String, start: Int, end: Int): Boolean = parse(pid)?.let { it in start..end } ?: false
}
