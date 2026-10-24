package androidx.lifecycle
import kotlinx.coroutines.CoroutineScope
abstract class ViewModel { protected open fun onCleared() {} }
val ViewModel.viewModelScope: CoroutineScope get() = TODO()
