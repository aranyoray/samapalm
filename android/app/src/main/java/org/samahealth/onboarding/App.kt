package org.samahealth.onboarding

import android.app.Application
import android.content.Context
import org.samahealth.crf.CrfEngine
import org.samahealth.crf.SupabaseClient
import org.samahealth.crf.SupabaseConfig
import org.samahealth.onboarding.data.AppDatabase
import org.samahealth.onboarding.data.Prefs
import org.samahealth.onboarding.data.Repository
import org.samahealth.onboarding.sync.SyncScheduler

/** Process-wide objects: database, encrypted settings, the schema text and a Supabase client factory. */
class AppContainer(val context: Context) {
    val prefs = Prefs(context)
    val db: AppDatabase = AppDatabase.build(context)
    val repo = Repository(db, prefs)
    val schemaText: String by lazy { context.assets.open("crf_schema.json").bufferedReader().use { it.readText() } }
    val appVersion: String by lazy {
        try { context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: "dev" } catch (e: Exception) { "dev" }
    }

    /** The engine for a new record of [part]; an open visit rebuilds its own from the snapshot it was created with. */
    fun engine(part: String = Prefs.PART_ENROL): CrfEngine = CrfEngine.fromJson(schemaText, prefs.engineSettings(part))

    /** Recruitment targets bundled with the app; the server copy wins when it has been fetched. */
    val targetsText: String by lazy {
        context.assets.open("recruitment_targets.json").bufferedReader().use { it.readText() }
    }

    fun client(): SupabaseClient? {
        // On-device mode has no signed-in operator, so nothing recorded under it carries an identity.
        // Refusing a client here is what keeps that data off a study table if a URL is pasted in later.
        if (prefs.localOnly) return null
        val url = prefs.supabaseUrl
        val key = prefs.supabaseAnonKey
        return if (url.isNullOrBlank() || key.isNullOrBlank()) null else SupabaseClient(SupabaseConfig(url, key))
    }
}

class App : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        SyncScheduler.schedulePeriodic(this)
    }
}

val Context.container: AppContainer get() = (applicationContext as App).container
