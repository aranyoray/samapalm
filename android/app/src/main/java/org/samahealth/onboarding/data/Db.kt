package org.samahealth.onboarding.data

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

/**
 * One row per participant visit. `answersJson` never holds identity answers (they live in IdentityEntity, which can
 * be purged from the tablet once uploaded). `crfJson` is the export frozen at submission; it is what gets uploaded.
 * syncState: local (draft, not queued) | pending | synced | error | duplicate (PID already used on the server).
 */
@Entity(tableName = "visits")
data class VisitEntity(
    @PrimaryKey val visitUuid: String,
    val pid: String?,
    val answersJson: String,
    val screenLogJson: String,
    val currentScreen: String,
    val status: String,
    val createdAt: String,
    val updatedAt: String,
    val submittedAt: String?,
    val screenFailReason: String?,
    val crfJson: String?,
    val syncState: String,
    val syncError: String?,
    val identitySynced: Boolean,
)

@Entity(tableName = "identity")
data class IdentityEntity(
    @PrimaryKey val visitUuid: String,
    val pid: String?,
    val name: String?,
    val hospitalRegNo: String?,
    val phone: String?,
)

@Dao
interface VisitDao {
    @Query("SELECT * FROM visits ORDER BY updatedAt DESC")
    fun observeAll(): Flow<List<VisitEntity>>

    @Query("SELECT * FROM visits WHERE visitUuid = :id")
    suspend fun get(id: String): VisitEntity?

    @Query("SELECT * FROM visits WHERE syncState IN ('pending', 'error')")
    suspend fun pending(): List<VisitEntity>

    @Query("SELECT pid FROM visits WHERE pid IS NOT NULL")
    suspend fun usedPids(): List<String>

    @Query("SELECT COUNT(*) FROM visits WHERE pid = :pid AND visitUuid != :visitUuid")
    suspend fun pidUsedByOther(pid: String, visitUuid: String): Int

    @Upsert
    suspend fun upsert(v: VisitEntity)

    @Query("DELETE FROM visits WHERE visitUuid = :id AND status = 'draft'")
    suspend fun deleteDraft(id: String)
}

@Dao
interface IdentityDao {
    @Query("SELECT * FROM identity WHERE visitUuid = :id")
    suspend fun get(id: String): IdentityEntity?

    @Upsert
    suspend fun upsert(i: IdentityEntity)

    @Query("DELETE FROM identity WHERE visitUuid = :id")
    suspend fun delete(id: String)
}

@Database(entities = [VisitEntity::class, IdentityEntity::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun visits(): VisitDao
    abstract fun identity(): IdentityDao

    companion object {
        fun build(context: Context): AppDatabase =
            Room.databaseBuilder(context, AppDatabase::class.java, "samahealth.db").build()
    }
}
