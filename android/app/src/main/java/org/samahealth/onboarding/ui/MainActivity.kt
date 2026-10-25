package org.samahealth.onboarding.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.Icon
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
import androidx.compose.ui.unit.dp
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.compose.ui.graphics.vector.ImageVector
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
private enum class Tab(val route: String, val label: String, val icon: ImageVector) {
    ENROL("tab/enrol", "Enrol", Icons.Filled.Person),
    SCAN("tab/scan", "Scan", Icons.Filled.Favorite),
    QUALITY("tab/quality", "Quality", Icons.Filled.CheckCircle),
    TARGETS("tab/targets", "Targets", Icons.Filled.Star),
}

@Composable
fun AppNav(activity: ComponentActivity, openVisit: String? = null) {
    val nav = rememberNavController()
    val c = activity.container
    var station by remember { mutableStateOf(c.prefs.station) }
    val firstTab = when (station) {
        Prefs.STATION_SCAN -> Tab.SCAN
        else -> Tab.ENROL
    }
    val start = when {
        !c.prefs.isConfigured -> "settings"
        c.prefs.session == null && !c.prefs.localOnly -> "login"
        openVisit != null -> "survey/$openVisit"
        else -> firstTab.route
    }
    // The station is a mode, not a preference: an enrolling phone hands out PIDs, a scanning phone takes a
    // PID that was handed out elsewhere. Showing the other station's tab only invites someone to start a
    // visit on the wrong phone, so it is not shown at all.
    val tabs = when (station) {
        Prefs.STATION_ENROL -> listOf(Tab.ENROL, Tab.QUALITY, Tab.TARGETS)
        Prefs.STATION_SCAN -> listOf(Tab.SCAN, Tab.QUALITY, Tab.TARGETS)
        else -> Tab.entries.toList()
    }
    var tab by remember { mutableStateOf(firstTab) }
    var inTabs by remember { mutableStateOf(start.startsWith("tab/")) }

    fun goTab(t: Tab) {
        tab = t
        nav.navigate(t.route) { popUpTo(firstTab.route) { inclusive = t == firstTab }; launchSingleTop = true }
    }

    Scaffold(
        topBar = {
            if (inTabs && c.prefs.localOnly) {
                // the colour runs behind the status bar, the words sit below it
                Surface(color = MaterialTheme.colorScheme.tertiaryContainer) {
                    Text(
                        "On this device only: no operator signed in, nothing uploads.",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.fillMaxWidth().statusBarsPadding()
                            .padding(horizontal = 16.dp, vertical = 6.dp),
                    )
                }
            }
        },
        bottomBar = {
            if (inTabs) {
                NavigationBar {
                    for (t in tabs) {
                        NavigationBarItem(
                            selected = tab == t,
                            onClick = { goTab(t) },
                            icon = { Icon(t.icon, contentDescription = null) },
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
                    // The station is a mode, so it has to take effect without a restart. firstTab here is
                    // still the value from before the save, so the destination is read back from prefs.
                    station = c.prefs.station
                    val landing = if (c.prefs.station == Prefs.STATION_SCAN) Tab.SCAN else Tab.ENROL
                    if (c.prefs.session == null && !c.prefs.localOnly) nav.navigate("login") { popUpTo(0) }
                    else {
                        inTabs = true
                        tab = landing
                        nav.navigate(landing.route) { popUpTo(0) }
                    }
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
                SurveyScreen(
                    visitUuid = id,
                    onExit = {
                        inTabs = true
                        if (!nav.popBackStack()) nav.navigate(firstTab.route) { popUpTo(0) }
                    },
                    // The tab bar is hidden inside a survey, which left the operator with no way to the
                    // Quality tab from the one screen they are on straight after recording a clip.
                    onOpenQuality = { goTab(Tab.QUALITY) },
                )
            }
        }
    }
}
