package androidx.activity.result
import android.content.Intent
class ActivityResult(val resultCode: Int, val data: Intent?)
abstract class ActivityResultLauncher<I> {
    fun launch(input: I) { launch(input, null) }
    abstract fun launch(input: I, options: Any?)
}
