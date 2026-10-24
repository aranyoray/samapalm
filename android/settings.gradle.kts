// SamaHealth onboarding app (SWHT-PP-003). Two modules:
//   :crf-core  pure Kotlin/JVM: survey engine, PID allocation, Supabase REST client (unit-tested on any JVM)
//   :app       Android UI, Room outbox, WorkManager sync, phone recorder (needs the Android SDK)
// :app is included only when an Android SDK is configured (local.properties sdk.dir or ANDROID_HOME), so the
// JVM tests of :crf-core run on machines and CI images without the SDK.
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "samahealth-onboarding"
include(":crf-core")
include(":quality-core")

val localProps = java.util.Properties().apply {
    val f = file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
val sdkDir = localProps.getProperty("sdk.dir") ?: System.getenv("ANDROID_HOME") ?: System.getenv("ANDROID_SDK_ROOT")
if (sdkDir != null && file(sdkDir).exists()) {
    include(":app")
} else {
    logger.lifecycle("No Android SDK found: building :crf-core only (set sdk.dir in local.properties to build :app)")
}
