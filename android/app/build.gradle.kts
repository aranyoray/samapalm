plugins {
    id("com.android.application")   // version from the root buildscript (8.7.3)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
}

android {
    namespace = "org.samahealth.onboarding"
    compileSdk = 35

    defaultConfig {
        applicationId = "org.samahealth.onboarding"
        minSdk = 29
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
    // The survey schema is the repository's configs/crf_schema.json, copied into the APK assets at build time.
    sourceSets["main"].assets.srcDir(layout.buildDirectory.dir("generated/crfAssets"))
}

val copyCrfSchema by tasks.registering(Copy::class) {
    from(rootProject.layout.projectDirectory.file("../configs/crf_schema.json"))
    into(layout.buildDirectory.dir("generated/crfAssets"))
}
tasks.named("preBuild") { dependsOn(copyCrfSchema) }

dependencies {
    implementation(project(":crf-core"))
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)
    implementation(libs.androidx.work.runtime.ktx)
    implementation(libs.androidx.security.crypto)
}
