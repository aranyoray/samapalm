package androidx.lifecycle.viewmodel.compose
import androidx.compose.runtime.Composable
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelStoreOwner
import androidx.lifecycle.viewmodel.CreationExtras
object LocalViewModelStoreOwner { val current: ViewModelStoreOwner @Composable get() = TODO() }
@Composable
inline fun <reified VM : ViewModel> viewModel(
    viewModelStoreOwner: ViewModelStoreOwner = LocalViewModelStoreOwner.current,
    key: String? = null,
    noinline initializer: CreationExtras.() -> VM
): VM = TODO()
