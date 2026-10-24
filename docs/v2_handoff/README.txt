compile_app.sh: local compile check for android/app (no Android SDK needed).
  /tmp/claude-0/-home-user-samapalm/1767d121-93b8-57dc-bbea-5d5b03c9a3eb/scratchpad/kc/compile_app.sh
It compiles every .kt under android/app/src/main/java against:
  - the real Android 15 framework classes (androidall/android-all-15-robolectric-*.jar)
  - AndroidX signature stubs you can extend: stubs/java/androidx/** (Java) and stubs/kt/*.kt (Kotlin)
    (Room, WorkManager, lifecycle, navigation-compose, activity-compose, security-crypto, LocalContext)
  - real Compose desktop 1.7.1 jars (m2/), kotlinx-serialization 1.7.3, crf-core and quality-core jars
If you use an AndroidX API that has no stub yet (e.g. androidx.core.content.FileProvider), add a minimal,
signature-accurate stub under stubs/java/androidx/... or stubs/kt/. Never stub android.* (the real jar has it).
Output: "compile_app: N app classes" plus any errors. 0 classes or listed errors = fix them.
GitHub Actions CI (./gradlew :app:assembleDebug) is the final judge; this harness only catches type errors early.
