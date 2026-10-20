package org.samahealth.onboarding.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import org.samahealth.onboarding.container

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface { AppNav(this) }
            }
        }
    }
}

@Composable
fun AppNav(activity: ComponentActivity) {
    val nav = rememberNavController()
    val c = activity.container
    val start = when {
        !c.prefs.isConfigured -> "settings"
        c.prefs.session == null -> "login"
        else -> "home"
    }
    NavHost(navController = nav, startDestination = start) {
        composable("settings") {
            SettingsScreen(onDone = { nav.navigate(if (c.prefs.session == null) "login" else "home") { popUpTo(0) } })
        }
        composable("login") {
            LoginScreen(onSignedIn = { nav.navigate("home") { popUpTo(0) } }, onSettings = { nav.navigate("settings") })
        }
        composable("home") {
            HomeScreen(
                onOpen = { id -> nav.navigate("survey/$id") },
                onSettings = { nav.navigate("settings") },
                onSignedOut = { nav.navigate("login") { popUpTo(0) } },
            )
        }
        composable("survey/{visitUuid}", arguments = listOf(navArgument("visitUuid") { type = NavType.StringType })) { entry ->
            val id = entry.arguments?.getString("visitUuid") ?: return@composable
            SurveyScreen(visitUuid = id, onExit = { nav.popBackStack() })
        }
    }
}
