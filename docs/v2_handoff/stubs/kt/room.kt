package androidx.room
import kotlin.reflect.KClass
@Target(AnnotationTarget.CLASS) annotation class Dao
@Target(AnnotationTarget.CLASS) annotation class Database(val entities: Array<KClass<*>> = [], val views: Array<KClass<*>> = [], val version: Int, val exportSchema: Boolean = true, val autoMigrations: Array<AutoMigration> = [])
annotation class AutoMigration(val from: Int, val to: Int)
@Target(AnnotationTarget.CLASS) annotation class Entity(val tableName: String = "", val primaryKeys: Array<String> = [])
@Target(AnnotationTarget.FIELD, AnnotationTarget.FUNCTION) annotation class PrimaryKey(val autoGenerate: Boolean = false)
@Target(AnnotationTarget.FUNCTION) annotation class Query(val value: String)
@Target(AnnotationTarget.FUNCTION) annotation class Upsert(val entity: KClass<*> = Any::class)
abstract class RoomDatabase {
    open class Builder<T : RoomDatabase> { open fun build(): T = TODO() }
}
object Room {
    @JvmStatic fun <T : RoomDatabase> databaseBuilder(context: android.content.Context, klass: Class<T>, name: String?): RoomDatabase.Builder<T> = TODO()
}
