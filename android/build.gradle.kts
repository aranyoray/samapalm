// The Android Gradle plugin is put on the root build classpath only when an Android SDK is configured, so the
// JVM-only module (:crf-core) builds and tests on machines and CI images without the SDK or Google's Maven host.
// Keep the version here in step with `agp` in gradle/libs.versions.toml.
buildscript {
    val props = java.util.Properties().apply {
        val f = rootDir.resolve("local.properties")
        if (f.exists()) f.inputStream().use { load(it) }
    }
    val sdk = props.getProperty("sdk.dir") ?: System.getenv("ANDROID_HOME") ?: System.getenv("ANDROID_SDK_ROOT")
    if (sdk != null && java.io.File(sdk).exists()) {
        repositories {
            google()
            mavenCentral()
        }
        dependencies { classpath("com.android.tools.build:gradle:8.7.3") }
    }
}

plugins {
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.ksp) apply false
}
