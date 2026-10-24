plugins {
    alias(libs.plugins.kotlin.jvm)
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

kotlin {
    compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) }
}

dependencies {
    testImplementation(kotlin("test-junit"))
    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.serialization.json)   // reads the shared fixtures only
}

// The fixtures live in the repository's configs/ so the Python reference (palmppg/quality/onsite.py) and the app
// share them; regenerate with: python tools/make_quality_fixtures.py
val repoConfigs = rootProject.layout.projectDirectory.dir("../configs")
tasks.test {
    systemProperty("quality.fixtures", repoConfigs.dir("quality_fixtures").asFile.absolutePath)
    testLogging { events("failed"); exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL }
}
