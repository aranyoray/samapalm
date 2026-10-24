package androidx.work
import android.content.Context
import java.util.concurrent.TimeUnit
class WorkerParameters
abstract class ListenableWorker(appContext: Context, workerParams: WorkerParameters) {
    val applicationContext: Context get() = TODO()
    abstract class Result {
        companion object {
            @JvmStatic fun success(): Result = TODO()
            @JvmStatic fun retry(): Result = TODO()
            @JvmStatic fun failure(): Result = TODO()
        }
    }
}
abstract class CoroutineWorker(appContext: Context, params: WorkerParameters) : ListenableWorker(appContext, params) {
    abstract suspend fun doWork(): Result
}
enum class NetworkType { NOT_REQUIRED, CONNECTED, UNMETERED }
enum class BackoffPolicy { EXPONENTIAL, LINEAR }
enum class ExistingWorkPolicy { REPLACE, KEEP, APPEND, APPEND_OR_REPLACE }
enum class ExistingPeriodicWorkPolicy { KEEP, REPLACE, UPDATE, CANCEL_AND_REENQUEUE }
class Constraints {
    class Builder { fun setRequiredNetworkType(networkType: NetworkType): Builder = this; fun build(): Constraints = TODO() }
}
abstract class WorkRequest {
    abstract class Builder<B : Builder<B, *>, W : WorkRequest> {
        fun setConstraints(constraints: Constraints): B = TODO()
        fun setBackoffCriteria(backoffPolicy: BackoffPolicy, backoffDelay: Long, timeUnit: TimeUnit): B = TODO()
        fun build(): W = TODO()
    }
}
class OneTimeWorkRequest : WorkRequest() { class Builder(workerClass: Class<out ListenableWorker>) : WorkRequest.Builder<Builder, OneTimeWorkRequest>() }
class PeriodicWorkRequest : WorkRequest() { class Builder(workerClass: Class<out ListenableWorker>, repeatInterval: Long, repeatIntervalTimeUnit: TimeUnit) : WorkRequest.Builder<Builder, PeriodicWorkRequest>() }
inline fun <reified W : ListenableWorker> OneTimeWorkRequestBuilder(): OneTimeWorkRequest.Builder = OneTimeWorkRequest.Builder(W::class.java)
inline fun <reified W : ListenableWorker> PeriodicWorkRequestBuilder(repeatInterval: Long, repeatIntervalTimeUnit: TimeUnit): PeriodicWorkRequest.Builder =
    PeriodicWorkRequest.Builder(W::class.java, repeatInterval, repeatIntervalTimeUnit)
interface Operation
abstract class WorkManager {
    abstract fun enqueueUniqueWork(uniqueWorkName: String, existingWorkPolicy: ExistingWorkPolicy, work: OneTimeWorkRequest): Operation
    abstract fun enqueueUniquePeriodicWork(uniqueWorkName: String, existingPeriodicWorkPolicy: ExistingPeriodicWorkPolicy, periodicWork: PeriodicWorkRequest): Operation
    companion object { @JvmStatic fun getInstance(context: Context): WorkManager = TODO() }
}
