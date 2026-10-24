package org.samahealth.onboarding.data

import android.content.Context
import androidx.room.Room
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Opens a real v1 database through Room's own migration path. The SQL is checked separately in
 * [MigrationSqlTest]; what this adds is that Room accepts the result, because a schema Room disagrees with
 * throws on the first open and a phone carrying un-uploaded v1 visits would meet that in the field.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], application = android.app.Application::class)   // not our App: it builds the encrypted prefs
class RoomMigrationTest {

    private val context: Context = ApplicationProvider.getApplicationContext()
    private val dbFile: File = context.getDatabasePath("migration-test.db")
    private var db: AppDatabase? = null

    @AfterTest
    fun tearDown() {
        db?.close()
        dbFile.delete()
        File("${dbFile.path}-shm").delete()
        File("${dbFile.path}-wal").delete()
    }

    /** Builds the database v1 shipped, with one un-uploaded draft and one submitted row waiting to go up. */
    private fun writeV1Database() {
        dbFile.parentFile?.mkdirs()
        dbFile.delete()
        val cfg = androidx.sqlite.db.SupportSQLiteOpenHelper.Configuration.builder(context)
            .name(dbFile.name)
            .callback(object : androidx.sqlite.db.SupportSQLiteOpenHelper.Callback(1) {
                override fun onCreate(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                    db.execSQL(
                        """CREATE TABLE visits (
                            visitUuid TEXT NOT NULL PRIMARY KEY, pid TEXT, answersJson TEXT NOT NULL,
                            screenLogJson TEXT NOT NULL, currentScreen TEXT NOT NULL, status TEXT NOT NULL,
                            createdAt TEXT NOT NULL, updatedAt TEXT NOT NULL, submittedAt TEXT,
                            screenFailReason TEXT, crfJson TEXT, syncState TEXT NOT NULL, syncError TEXT,
                            identitySynced INTEGER NOT NULL)""",
                    )
                    db.execSQL(
                        """CREATE TABLE identity (visitUuid TEXT NOT NULL PRIMARY KEY, pid TEXT, name TEXT,
                            hospitalRegNo TEXT, phone TEXT)""",
                    )
                    db.execSQL(
                        """INSERT INTO visits VALUES ('u-1', 'SW-001', '{"study_id":"SW-001"}', '[]', 'review',
                            'draft', '2026-10-01T09:00:00+05:30', '2026-10-01T09:30:00+05:30', NULL, NULL, NULL,
                            'local', NULL, 0)""",
                    )
                    db.execSQL(
                        """INSERT INTO visits VALUES ('u-2', 'SW-002', '{"study_id":"SW-002"}', '[]', 'review',
                            'submitted', '2026-10-01T10:00:00+05:30', '2026-10-01T10:30:00+05:30',
                            '2026-10-01T10:30:00+05:30', NULL, '{"study_id":"SW-002"}', 'pending', NULL, 0)""",
                    )
                    db.execSQL("INSERT INTO identity VALUES ('u-1', 'SW-001', 'A Name', 'H-9', '99999')")
                }

                override fun onUpgrade(db: androidx.sqlite.db.SupportSQLiteDatabase, old: Int, new: Int) = Unit
            })
            .build()
        FrameworkSQLiteOpenHelperFactory().create(cfg).writableDatabase.close()
    }

    private fun openV2(): AppDatabase =
        Room.databaseBuilder(context, AppDatabase::class.java, dbFile.name)
            .addMigrations(AppDatabase.MIGRATION_1_2)
            .build()
            .also { db = it }

    @Test
    fun roomOpensTheMigratedDatabaseAndTheV1VisitsAreStillThere() = runBlocking {
        writeV1Database()
        val d = openV2()
        // the first query is what runs the migration and Room's schema check
        val all = d.visits().all()
        assertEquals(2, all.size, "both v1 visits must survive")
        val byId = all.associateBy { it.visitUuid }
        val draft = byId.getValue("u-1")
        assertEquals("SW-001", draft.pid)
        assertEquals(VisitEntity.PART_FULL, draft.part)
        assertTrue(draft.isLegacy, "a v1 row is a legacy record")
        assertEquals(false, draft.everSubmitted)
        assertEquals(false, draft.serverAccepted)
        assertEquals("{}", draft.settingsJson)

        val sent = byId.getValue("u-2")
        assertEquals(true, sent.everSubmitted, "a submitted v1 row may not be discarded later")
        assertEquals("""{"study_id":"SW-002"}""", sent.crfJson, "the frozen export must survive")
    }

    @Test
    fun aV1RowStillWaitingToUploadIsStillQueued() = runBlocking {
        writeV1Database()
        val d = openV2()
        val queued = d.visits().queued()
        assertEquals(listOf("SW-002"), queued.map { it.pid })
    }

    @Test
    fun theEcgInboxWorksOnTheMigratedDatabase() = runBlocking {
        writeV1Database()
        val d = openV2()
        d.ecgInbox().upsert(
            EcgInboxEntity(visitUuid = "u-1", clipId = "clip1", relPath = "SW-001/clip1_kardia.pdf",
                createdAt = "2026-10-24T10:00:00+05:30"),
        )
        val rows = d.ecgInbox().observe("u-1").first()
        assertEquals(1, rows.size)
        assertEquals("clip1", rows[0].clipId)
        d.ecgInbox().consume(rows[0].id)
        assertEquals(0, d.ecgInbox().observe("u-1").first().size)
    }

    @Test
    fun theDraftUpdateIsConditionalOnTheVisitStillBeingADraft() = runBlocking {
        writeV1Database()
        val d = openV2()
        val t = "2026-10-24T12:00:00+05:30"
        assertEquals(1, d.visits().updateDraft("u-1", "SW-001", "{\"a\":1}", "[]", "review", t),
            "a draft takes the autosave")
        assertEquals(0, d.visits().updateDraft("u-2", "SW-002", "{\"a\":1}", "[]", "review", t),
            "a submitted record must not be written over by a late autosave")
        assertEquals("""{"study_id":"SW-002"}""", d.visits().get("u-2")!!.answersJson,
            "the submitted record's answers are untouched")
        assertEquals("""{"a":1}""", d.visits().get("u-1")!!.answersJson)
    }

    @Test
    fun onlyANeverSubmittedDraftCanBeDiscarded() = runBlocking {
        writeV1Database()
        val d = openV2()
        assertEquals(0, d.visits().deleteDraft("u-2"), "a submitted record cannot be discarded")
        assertEquals(1, d.visits().deleteDraft("u-1"), "an untouched draft can")
        assertEquals(1, d.visits().all().size)
    }
}
