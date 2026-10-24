#!/bin/sh
# Local compile check for android/app without the Android SDK (dl.google.com is blocked here).
# Classpath: the real Android 15 framework (Robolectric android-all jar from Maven Central), AndroidX signature stubs
# (stubs/java/androidx -> jout, stubs/kt -> kout: Room, WorkManager, lifecycle, navigation, activity-compose,
# security-crypto, LocalContext), the real Compose desktop 1.7.1 jars, kotlinx-serialization, crf-core and any extra
# module jars (quality-core when present). CI (GitHub Actions) is the final judge.
# Usage: compile_app.sh [app_src_dir]   (also compiles app/src/test when JUNIT is found)
# Each run compiles into its own temporary directory, so parallel runs do not clobber each other.
S=/tmp/claude-0/-home-user-samapalm/1767d121-93b8-57dc-bbea-5d5b03c9a3eb/scratchpad
ROOT=/home/user/samapalm/android
APP=${1:-$ROOT/app/src/main/java}
M=$S/m2
C=/root/.gradle/caches/modules-2/files-2.1
AA=$(ls $S/androidall/android-all-*.jar | head -1)
set -e
MODS=":crf-core:jar"
[ -d $ROOT/quality-core ] && MODS="$MODS :quality-core:jar"
(cd $ROOT && ./gradlew --offline -q $MODS >/dev/null 2>&1) || { echo "module jar build failed: (cd $ROOT && ./gradlew --offline $MODS)"; exit 1; }
CMP=$(ls $M/*-desktop-1.7.1.jar | tr '\n' ':')
SER=$(ls $C/org.jetbrains.kotlinx/kotlinx-serialization-core-jvm/1.7.3/*/*.jar):$(ls $C/org.jetbrains.kotlinx/kotlinx-serialization-json-jvm/1.7.3/*/*.jar)
OK=$(ls $C/com.squareup.okhttp3/okhttp/*/*/*.jar 2>/dev/null | head -1)
QJ=$(ls $ROOT/quality-core/build/libs/*.jar 2>/dev/null | head -1)
BASE="$AA:$CMP$M/kotlinx-coroutines-core-jvm-1.8.1.jar:$M/atomicfu-jvm-0.23.2.jar:$SER:$ROOT/crf-core/build/libs/crf-core.jar:$OK:$QJ"
W=$(mktemp -d $S/kc/run.XXXXXX)
mkdir -p $W/jout $W/kout $W/appout
javac -nowarn -cp "$AA" -d $W/jout $(find $S/stubs/java/androidx -name "*.java") 2>&1 | grep -v JAVA_TOOL || true
EXTRA_CP="$BASE:$W/jout" $S/kc/kc.sh -nowarn -Xplugin=$M/kotlin-compose-compiler-plugin-embeddable-2.0.21.jar -jvm-target 17 -d $W/kout $S/stubs/kt/*.kt 2>&1 | grep -v JAVA_TOOL || true
EXTRA_CP="$BASE:$W/jout:$W/kout" $S/kc/kc.sh -nowarn -Xplugin=$M/kotlin-compose-compiler-plugin-embeddable-2.0.21.jar -jvm-target 17 -d $W/appout $(find $APP -name "*.kt") 2>&1 | grep -v JAVA_TOOL || true
n=$(find $W/appout -name "*.class" 2>/dev/null | wc -l)
echo "compile_app: $n app classes written to $W/appout (errors, if any, are listed above)"
