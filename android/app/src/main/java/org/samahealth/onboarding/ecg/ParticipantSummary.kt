package org.samahealth.onboarding.ecg

import android.content.Context
import android.content.Intent
import android.graphics.Paint
import android.graphics.pdf.PdfDocument
import androidx.core.content.FileProvider
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import org.samahealth.crf.num
import org.samahealth.crf.str
import java.io.File
import java.time.LocalDate

/**
 * The one page a participant takes home (design section 9). It carries the Kardia app's own result as the
 * operator transcribed it, the heart rate, how clear the recording was, and that a study doctor reviews every
 * strip. Research model output never appears here.
 */
object ParticipantSummary {

    private const val PAGE_W = 595          // A4 at 72 dpi
    private const val PAGE_H = 842
    private const val LEFT = 48f
    private const val RIGHT = PAGE_W - 48f

    private const val DISCLAIMER =
        "This is not a medical result. It is part of a research study. A study doctor reviews every recording. " +
            "If you feel unwell, or have chest pain, breathlessness, fainting or palpitations, see a doctor."

    /** Plain words for the grade the signal check gave. */
    internal fun qualityWords(grade: String?): String = when (grade) {
        "good" -> "The recording was clear."
        "borderline" -> "The recording was usable but not perfectly clear."
        "retake" -> "The recording was not clear enough to measure well."
        else -> "The recording has not been checked yet."
    }

    /** The lines of the page, in order. Pure, so the wording can be checked without drawing a PDF. */
    internal fun lines(pid: String, date: String, clip: JsonObject, clinicianReviewed: Boolean): List<Pair<String, Boolean>> {
        val out = ArrayList<Pair<String, Boolean>>()          // text, isHeading
        out.add("Your heart recording (research study)" to true)
        out.add("Participant ID: $pid" to false)
        out.add("Date: $date" to false)
        out.add("" to false)

        val ecgMetrics = clip["ecg_metrics"] as? JsonObject
        val hr = num(ecgMetrics?.get("hr_bpm"))
        out.add("Heart rate" to true)
        out.add((hr?.let { "About ${Math.round(it)} beats per minute during the recording." }
            ?: "The heart rate could not be measured from this recording.") to false)
        out.add("" to false)

        val rhythm = clip["rhythm_sentences"] as? JsonArray
        if (rhythm != null && rhythm.isNotEmpty()) {
            out.add("What the recording showed" to true)
            for (e in rhythm) str(e)?.let { out.add(it to false) }
            out.add("" to false)
        }

        str(clip["kardia_determination"])?.let { det ->
            out.add("The Kardia device's own result" to true)
            out.add("The Kardia app showed: ${kardiaWords(det)}." to false)
            num(clip["kardia_hr"])?.let { out.add("Kardia heart rate: ${Math.round(it)} beats per minute." to false) }
            out.add("" to false)
        }

        out.add("Recording quality" to true)
        out.add(qualityWords(str(clip["ecg_grade"])) to false)
        out.add("" to false)

        out.add("Doctor's review" to true)
        out.add(
            (if (clinicianReviewed) "A study doctor has looked at this recording."
            else "A study doctor has not looked at this recording yet. The study will contact you if anything " +
                "needs attention.") to false,
        )
        out.add("" to false)
        out.add(DISCLAIMER to false)
        return out
    }

    /** The `kardia` choice values in words a participant can read. */
    internal fun kardiaWords(value: String): String = when (value) {
        "nsr" -> "a normal steady rhythm"
        "af" -> "a result the study doctor will look at"
        "bradycardia" -> "a slower than usual heart rate"
        "tachycardia" -> "a faster than usual heart rate"
        "sinus_sve", "sinus_pvc", "sinus_wide_qrs" -> "a steady rhythm with some extra beats"
        "unclassified" -> "a result it could not classify"
        "unreadable" -> "a recording it could not read"
        "too_short" -> "a recording that was too short"
        "not_recorded" -> "no recording"
        else -> value.replace('_', ' ')
    }

    /** Writes the page under the app's files directory and returns it. */
    fun write(context: Context, pid: String, clip: JsonObject, clinicianReviewed: Boolean): File {
        val date = LocalDate.now().toString()
        val doc = PdfDocument()
        val page = doc.startPage(PdfDocument.PageInfo.Builder(PAGE_W, PAGE_H, 1).create())
        val canvas = page.canvas
        val heading = Paint().apply { textSize = 13f; isFakeBoldText = true; isAntiAlias = true }
        val body = Paint().apply { textSize = 11f; isAntiAlias = true }
        val title = Paint().apply { textSize = 18f; isFakeBoldText = true; isAntiAlias = true }

        var y = 72f
        for ((i, line) in lines(pid, date, clip, clinicianReviewed).withIndex()) {
            val (text, isHeading) = line
            if (text.isEmpty()) { y += 10f; continue }
            val paint = if (i == 0) title else if (isHeading) heading else body
            y = drawWrapped(canvas, text, paint, y)
        }
        doc.finishPage(page)

        val dir = File(context.getExternalFilesDir(null), pid).apply { mkdirs() }
        val out = File(dir, "${pid}_ecg_summary.pdf")
        out.outputStream().use { doc.writeTo(it) }
        doc.close()
        return out
    }

    /** Draws [text] wrapped to the page width, returning the next baseline. */
    private fun drawWrapped(canvas: android.graphics.Canvas, text: String, paint: Paint, startY: Float): Float {
        val width = RIGHT - LEFT
        var y = startY
        val words = text.split(" ")
        val line = StringBuilder()
        for (w in words) {
            val candidate = if (line.isEmpty()) w else "$line $w"
            if (paint.measureText(candidate) > width && line.isNotEmpty()) {
                canvas.drawText(line.toString(), LEFT, y, paint)
                y += paint.textSize + 5f
                line.setLength(0)
                line.append(w)
            } else {
                line.setLength(0)
                line.append(candidate)
            }
        }
        if (line.isNotEmpty()) {
            canvas.drawText(line.toString(), LEFT, y, paint)
            y += paint.textSize + 5f
        }
        return y + 3f
    }

    fun shareIntent(context: Context, pdf: File): Intent {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", pdf)
        return Intent(Intent.ACTION_SEND).apply {
            type = "application/pdf"
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
    }
}
