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
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import kotlinx.coroutines.flow.Flow

/**
 * One row per participant record. A participant has up to two records ([part] "enrol" and "scan") that meet on the
 * server by PID; rows written by v1 of the app carry part "full" (design section 6).
 *
 * [settingsJson] is the engine settings snapshot taken when the record was created, so the visit always re-opens on
 * the flow it was started on. [crfJson] is the export frozen at submission and is what gets uploaded.
 * [serverAccepted] locks the PID once the server has taken the row; [everSubmitted] keeps a record that was
 * submitted at least once from being discarded.
 * syncState: local (draft, not queued) | pending | synced | error | duplicate (PID already used on the server).
 */
@Entity(tableName = "visits")
data class VisitEntity(
    @PrimaryKey val visitUuid: String,
    val pid: String?,
    val part: String,
    val answersJson: String,
    val screenLogJson: String,
    val currentScreen: String,
    val settingsJson: String,
    val status: String,
    val createdAt: String,
    val updatedAt: String,
    val submittedAt: String?,
    val screenFailReason: String?,
    val crfJson: String?,
    val syncState: String,
    val syncError: String?,
    val serverAccepted: Boolean,
    val everSubmitted: Boolean,
) {
    /** v1 rows cannot be re-opened: the v2 schema has no flow for them. They stay visible and uploadable. */
    val isLegacy: Boolean get() = part == PART_FULL

    companion object {
        const val PART_ENROL = "enrol"
        const val PART_SCAN = "scan"
        const val PART_FULL = "full"
    }
}

/**
 * A Kardia file shared into the app for a clip, waiting for the survey screen to pick it up. The survey is the only
 * writer of a visit's answers, so the share sheet drops the file here instead of writing the answer itself.
 */
@Entity(tableName = "ecg_inbox")
data class EcgInboxEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val visitUuid: String,
    val clipId: String,
    val relPath: String,
    val createdAt: String,
    val consumed: Boolean = false,
)

@Dao
interface VisitDao {
    @Query("SELECT * FROM visits ORDER BY updatedAt DESC")
    fun observeAll(): Flow<List<VisitEntity>>

    @Query("SELECT * FROM visits WHERE part = :part ORDER BY updatedAt DESC")
    fun observePart(part: String): Flow<List<VisitEntity>>

    @Query("SELECT * FROM visits ORDER BY updatedAt DESC")
    suspend fun all(): List<VisitEntity>

    @Query("SELECT * FROM visits WHERE visitUuid = :id")
    suspend fun get(id: String): VisitEntity?

    @Query("SELECT * FROM visits WHERE syncState IN ('pending', 'error')")
    suspend fun pending(): List<VisitEntity>

    /** Rows the automatic queue may retry; 'error' rows wait for the operator to press Retry. */
    @Query("SELECT * FROM visits WHERE syncState = 'pending'")
    suspend fun queued(): List<VisitEntity>

    @Query("SELECT pid FROM visits WHERE pid IS NOT NULL")
    suspend fun usedPids(): List<String>

    @Query("SELECT COUNT(*) FROM visits WHERE pid = :pid AND part = :part AND visitUuid != :visitUuid")
    suspend fun pidUsedByOther(pid: String, part: String, visitUuid: String): Int

    @Query("SELECT * FROM visits WHERE part = 'scan' AND status = 'draft' ORDER BY updatedAt DESC")
    suspend fun activeScanDrafts(): List<VisitEntity>

    /** This phone's submitted enrol parts, for the scan station's PID picker and the local strata counts. */
    @Query("SELECT * FROM visits WHERE part = 'enrol' AND status = 'submitted' ORDER BY updatedAt DESC")
    suspend fun submittedEnrolments(): List<VisitEntity>

    @Query("SELECT * FROM visits WHERE part = 'enrol' AND status = 'submitted' AND syncState != 'synced'")
    suspend fun unsyncedEnrolments(): List<VisitEntity>

    @Upsert
    suspend fun upsert(v: VisitEntity)

    /** Autosave: only ever touches a row that is still a draft. */
    @Query("""UPDATE visits SET pid = :pid, answersJson = :answers, screenLogJson = :log,
                     currentScreen = :screen, updatedAt = :t
              WHERE visitUuid = :id AND status = 'draft'""")
    suspend fun updateDraft(id: String, pid: String?, answers: String, log: String, screen: String, t: String): Int

    @Query("DELETE FROM visits WHERE visitUuid = :id AND status = 'draft' AND everSubmitted = 0")
    suspend fun deleteDraft(id: String): Int
}

@Dao
interface EcgInboxDao {
    @Query("SELECT * FROM ecg_inbox WHERE visitUuid = :id AND consumed = 0 ORDER BY id")
    fun observe(id: String): Flow<List<EcgInboxEntity>>

    @Upsert
    suspend fun upsert(e: EcgInboxEntity)

    @Query("UPDATE ecg_inbox SET consumed = 1 WHERE id = :id")
    suspend fun consume(id: Long)
}

@Database(entities = [VisitEntity::class, EcgInboxEntity::class], version = 2, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun visits(): VisitDao
    abstract fun ecgInbox(): EcgInboxDao

    companion object {
        /**
         * v1 -> v2: the visits table is rebuilt with the part columns (existing rows become the legacy part
         * "full"), the identity table goes away with the names it held, and the ECG inbox is added. Phones may
         * still hold un-uploaded v1 rows, so nothing is dropped from them.
         */
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """CREATE TABLE visits_new (
                        visitUuid TEXT NOT NULL PRIMARY KEY, pid TEXT, part TEXT NOT NULL,
                        answersJson TEXT NOT NULL, screenLogJson TEXT NOT NULL, currentScreen TEXT NOT NULL,
                        settingsJson TEXT NOT NULL, status TEXT NOT NULL, createdAt TEXT NOT NULL,
                        updatedAt TEXT NOT NULL, submittedAt TEXT, screenFailReason TEXT, crfJson TEXT,
                        syncState TEXT NOT NULL, syncError TEXT, serverAccepted INTEGER NOT NULL,
                        everSubmitted INTEGER NOT NULL)""",
                )
                db.execSQL(
                    """INSERT INTO visits_new SELECT visitUuid, pid, 'full', answersJson, screenLogJson,
                        currentScreen, '{}', status, createdAt, updatedAt, submittedAt, screenFailReason, crfJson,
                        syncState, syncError,
                        CASE WHEN syncState = 'synced' THEN 1 ELSE 0 END,
                        CASE WHEN status != 'draft' OR submittedAt IS NOT NULL THEN 1 ELSE 0 END
                       FROM visits""",
                )
                db.execSQL("DROP TABLE visits")
                db.execSQL("ALTER TABLE visits_new RENAME TO visits")
                db.execSQL("DROP TABLE IF EXISTS identity")
                db.execSQL(
                    """CREATE TABLE IF NOT EXISTS ecg_inbox (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, visitUuid TEXT NOT NULL,
                        clipId TEXT NOT NULL, relPath TEXT NOT NULL, createdAt TEXT NOT NULL,
                        consumed INTEGER NOT NULL)""",
                )
            }
        }

        fun build(context: Context): AppDatabase =
            Room.databaseBuilder(context, AppDatabase::class.java, "samahealth.db")
                .addMigrations(MIGRATION_1_2)
                .build()
    }
}
