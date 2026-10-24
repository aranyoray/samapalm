package org.samahealth.onboarding.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import org.samahealth.onboarding.container
import org.samahealth.onboarding.data.Prefs
import org.samahealth.onboarding.data.VisitEntity

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val openVisit = intent?.getStringExtra(EXTRA_OPEN_VISIT)
        setContent {
            MaterialTheme {
                Surface { AppNav(this, openVisit) }
            }
        }
    }

    companion object {
        /** Set by the Kardia share sheet to jump straight to the visit the file was attached to. */
        const val EXTRA_OPEN_VISIT = "open_visit"
    }
}

/** The four stations of the app (design section 6). */
private enum class Tab(val route: String, val label: String) {
    ENROL("tab/enrol", "Enrol"),
    SCAN("tab/scan", "Scan"),
    QUALITY("tab/quality", "Quality"),
    TARGETS("tab/targets", "Targets"),
}

@Composable
fun AppNav(activity: ComponentActivity, openVisit: String? = null) {
    val nav = rememberNavController()
    val c = activity.container
    val firstTab = when (c.prefs.station) {
        Prefs.STATION_SCAN -> Tab.SCAN
        else -> Tab.ENROL
    }
    val start = when {
        !c.prefs.isConfigured -> "settings"
        c.prefs.session == null -> "login"
        openVisit != null -> "survey/$openVisit"
        else -> firstTab.route
    }
    var tab by remember { mutableStateOf(firstTab) }
    var inTabs by remember { mutableStateOf(start.startsWith("tab/")) }

    fun goTab(t: Tab) {
        tab = t
        nav.navigate(t.route) { popUpTo(firstTab.route) { inclusive = t == firstTab }; launchSingleTop = true }
    }

    Scaffold(
        bottomBar = {
            if (inTabs) {
                NavigationBar {
                    for (t in Tab.entries) {
                        NavigationBarItem(
                            selected = tab == t,
                            onClick = { goTab(t) },
                            icon = {},
                            label = { Text(t.label) },
                        )
                    }
                }
            }
        },
    ) { pad ->
        NavHost(navController = nav, startDestination = start, modifier = Modifier.padding(pad)) {
            composable("settings") {
                inTabs = false
                SettingsScreen(onDone = {
                    if (c.prefs.session == null) nav.navigate("login") { popUpTo(0) }
                    else { inTabs = true; nav.navigate(firstTab.route) { popUpTo(0) } }
                })
            }
            composable("login") {
                inTabs = false
                LoginScreen(
                    onSignedIn = { c.prefs.signInRequired = false; inTabs = true; nav.navigate(firstTab.route) { popUpTo(0) } },
                    onSettings = { nav.navigate("settings") },
                )
            }
            for (t in listOf(Tab.ENROL, Tab.SCAN)) {
                composable(t.route) {
                    inTabs = true
                    tab = t
                    RecordsScreen(
                        part = if (t == Tab.ENROL) VisitEntity.PART_ENROL else VisitEntity.PART_SCAN,
                        onOpen = { id -> nav.navigate("survey/$id") },
                        onSettings = { nav.navigate("settings") },
                        onSignedOut = { nav.navigate("login") { popUpTo(0) } },
                    )
                }
            }
            composable(Tab.QUALITY.route) {
                inTabs = true
                tab = Tab.QUALITY
                QualityScreen(onOpenVisit = { id -> nav.navigate("survey/$id") })
            }
            composable(Tab.TARGETS.route) {
                inTabs = true
                tab = Tab.TARGETS
                TargetsScreen()
            }
            composable("survey/{visitUuid}", arguments = listOf(navArgument("visitUuid") { type = NavType.StringType })) { entry ->
                inTabs = false
                val id = entry.arguments?.getString("visitUuid") ?: return@composable
                SurveyScreen(visitUuid = id, onExit = {
                    inTabs = true
                    if (!nav.popBackStack()) nav.navigate(firstTab.route) { popUpTo(0) }
                })
            }
        }
    }
}
