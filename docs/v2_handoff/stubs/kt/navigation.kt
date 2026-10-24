package androidx.navigation
import android.os.Bundle
open class NavController {
    fun navigate(route: String, builder: NavOptionsBuilder.() -> Unit) {}
    fun navigate(route: String, navOptions: NavOptions? = null, navigatorExtras: Any? = null) {}
    fun <T : Any> navigate(route: T, builder: NavOptionsBuilder.() -> Unit) {}
    fun <T : Any> navigate(route: T, navOptions: NavOptions? = null, navigatorExtras: Any? = null) {}
    open fun popBackStack(): Boolean = true
}
class NavOptions
open class NavHostController : NavController()
class PopUpToBuilder { var inclusive: Boolean = false; var saveState: Boolean = false }
class NavOptionsBuilder {
    var launchSingleTop: Boolean = false
    fun popUpTo(id: Int, popUpToBuilder: PopUpToBuilder.() -> Unit = {}) {}
    fun popUpTo(route: String, popUpToBuilder: PopUpToBuilder.() -> Unit = {}) {}
    inline fun <reified T : Any> popUpTo(noinline popUpToBuilder: PopUpToBuilder.() -> Unit = {}) {}
    fun <T : Any> popUpTo(route: T, popUpToBuilder: PopUpToBuilder.() -> Unit = {}) {}
}
class NavBackStackEntry { val arguments: Bundle? get() = null }
abstract class NavType<T>(open val isNullableAllowed: Boolean) {
    companion object {
        @JvmField val StringType: NavType<String?> = TODO()
        @JvmField val IntType: NavType<Int> = TODO()
    }
}
class NavArgumentBuilder { var type: NavType<*> = TODO(); var nullable: Boolean = false }
class NamedNavArgument
fun navArgument(name: String, builder: NavArgumentBuilder.() -> Unit): NamedNavArgument = TODO()
class NavDeepLink
open class NavGraphBuilder
