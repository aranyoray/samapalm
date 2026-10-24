package androidx.navigation.compose
import androidx.compose.animation.AnimatedContentScope
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.navigation.NamedNavArgument
import androidx.navigation.NavBackStackEntry
import androidx.navigation.NavDeepLink
import androidx.navigation.NavGraphBuilder
import androidx.navigation.NavHostController
@Composable fun rememberNavController(): NavHostController = TODO()
@Composable
fun NavHost(navController: NavHostController, startDestination: String, modifier: Modifier = Modifier, contentAlignment: Alignment = Alignment.TopStart,
            route: String? = null, builder: NavGraphBuilder.() -> Unit) {}
fun NavGraphBuilder.composable(route: String, arguments: List<NamedNavArgument> = emptyList(), deepLinks: List<NavDeepLink> = emptyList(),
                               content: @Composable AnimatedContentScope.(NavBackStackEntry) -> Unit) {}
