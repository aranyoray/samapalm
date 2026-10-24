package androidx.activity.result.contract
import android.content.Intent
import androidx.activity.result.ActivityResult
abstract class ActivityResultContract<I, O>
class ActivityResultContracts { class StartActivityForResult : ActivityResultContract<Intent, ActivityResult>() }
