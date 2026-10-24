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

// Fixtures live in the repository's configs/ so the Python reference and the phone share them;
// regenerate with: python tools/make_founder_fixtures.py
val repoConfigs = rootProject.layout.projectDirectory.dir("../configs")
tasks.test {
    systemProperty("founder.fixtures", repoConfigs.dir("founder_fixtures").asFile.absolutePath)
    // -PfounderDump=<dir> writes the tensors this port produces, to run the real model on them
    (findProperty("founderDump") as String?)?.let { systemProperty("founder.dump", it) }
    maxHeapSize = "2g"
    testLogging { events("failed"); exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL }
}
