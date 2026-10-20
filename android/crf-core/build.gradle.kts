plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.serialization)
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

kotlin {
    compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) }
}

dependencies {
    api(libs.kotlinx.serialization.json)
    api(libs.okhttp)
    testImplementation(kotlin("test-junit"))
    testImplementation(libs.junit)
    testImplementation(libs.okhttp.mockwebserver)
}

// The schema and golden fixtures live in the repository's configs/ so the Python pipeline and the app share them.
val repoConfigs = rootProject.layout.projectDirectory.dir("../configs")
tasks.test {
    systemProperty("crf.schema", repoConfigs.file("crf_schema.json").asFile.absolutePath)
    systemProperty("crf.golden", repoConfigs.file("crf_fixtures/golden.json").asFile.absolutePath)
    testLogging { events("failed"); exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL }
}
