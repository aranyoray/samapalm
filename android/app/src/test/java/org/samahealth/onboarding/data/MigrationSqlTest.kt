package org.samahealth.onboarding.data

import java.sql.Connection
import java.sql.DriverManager
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Runs the Room 1 -> 2 statements against a throwaway SQLite database holding a v1 row, because a phone may still
 * be carrying un-uploaded v1 visits when the new app lands on it. Nothing of theirs may be lost.
 */
class MigrationSqlTest {

    private val v1Schema = listOf(
        """CREATE TABLE visits (
            visitUuid TEXT NOT NULL PRIMARY KEY, pid TEXT, answersJson TEXT NOT NULL,
            screenLogJson TEXT NOT NULL, currentScreen TEXT NOT NULL, status TEXT NOT NULL,
            createdAt TEXT NOT NULL, updatedAt TEXT NOT NULL, submittedAt TEXT, screenFailReason TEXT,
            crfJson TEXT, syncState TEXT NOT NULL, syncError TEXT, identitySynced INTEGER NOT NULL)""",
        """CREATE TABLE identity (
            visitUuid TEXT NOT NULL PRIMARY KEY, pid TEXT, name TEXT, hospitalRegNo TEXT, phone TEXT)""",
    )

    private fun v1Row(
        uuid: String, pid: String, status: String, syncState: String, submittedAt: String?,
    ): String {
        val sub = submittedAt?.let { "'$it'" } ?: "NULL"
        return """INSERT INTO visits VALUES ('$uuid', '$pid', '{"study_id":"$pid"}', '[]', 'review',
            '$status', '2026-10-01T09:00:00+05:30', '2026-10-01T09:30:00+05:30', $sub, NULL,
            '{"study_id":"$pid"}', '$syncState', NULL, 0)"""
    }

    private fun migrated(): Connection {
        val db = DriverManager.getConnection("jdbc:sqlite::memory:")
        db.createStatement().use { st ->
            for (sql in v1Schema) st.execute(sql)
            st.execute(v1Row("u-draft", "SW-001", "draft", "local", null))
            st.execute(v1Row("u-sent", "SW-002", "submitted", "synced", "2026-10-01T09:30:00+05:30"))
            st.execute(v1Row("u-queued", "SW-003", "submitted", "pending", "2026-10-01T09:40:00+05:30"))
            st.execute("INSERT INTO identity VALUES ('u-draft', 'SW-001', 'A Name', 'H-9', '99999')")
            for (sql in AppDatabase.MIGRATION_1_2_SQL) st.execute(sql)
        }
        return db
    }

    private fun <T> query(db: Connection, sql: String, read: (java.sql.ResultSet) -> T): List<T> {
        val out = ArrayList<T>()
        db.createStatement().use { st ->
            st.executeQuery(sql).use { rs -> while (rs.next()) out.add(read(rs)) }
        }
        return out
    }

    @Test
    fun everyV1RowSurvivesAsALegacyFullRecord() {
        migrated().use { db ->
            val rows = query(db, "SELECT visitUuid, pid, part, status, crfJson FROM visits ORDER BY visitUuid") {
                listOf(it.getString(1), it.getString(2), it.getString(3), it.getString(4), it.getString(5))
            }
            assertEquals(3, rows.size, "no v1 visit may be dropped")
            assertEquals(listOf("u-draft", "u-queued", "u-sent"), rows.map { it[0] })
            assertTrue(rows.all { it[2] == "full" }, "v1 rows become the legacy part: $rows")
            assertEquals("SW-001", rows[0][1])
            assertEquals("""{"study_id":"SW-001"}""", rows[0][4], "the frozen export must be carried across")
        }
    }

    @Test
    fun theNewColumnsAreBackfilledFromWhatV1Knew() {
        migrated().use { db ->
            val rows = query(db, "SELECT visitUuid, serverAccepted, everSubmitted, settingsJson FROM visits") {
                listOf(it.getString(1), it.getInt(2).toString(), it.getInt(3).toString(), it.getString(4))
            }.associateBy { it[0] }
            // only the row the server already took counts as accepted
            assertEquals("1", rows.getValue("u-sent")[1])
            assertEquals("0", rows.getValue("u-queued")[1])
            assertEquals("0", rows.getValue("u-draft")[1])
            // anything that was submitted once may not be discarded later
            assertEquals("1", rows.getValue("u-sent")[2])
            assertEquals("1", rows.getValue("u-queued")[2])
            assertEquals("0", rows.getValue("u-draft")[2])
            assertTrue(rows.values.all { it[3] == "{}" }, "v1 rows have no engine snapshot")
        }
    }

    @Test
    fun aQueuedV1RowCanStillBeUploadedAfterTheMigration() {
        migrated().use { db ->
            val pending = query(db, "SELECT pid FROM visits WHERE syncState = 'pending'") { it.getString(1) }
            assertEquals(listOf("SW-003"), pending, "a v1 row waiting to upload must stay in the queue")
        }
    }

    @Test
    fun theIdentityTableAndItsNamesAreGone() {
        migrated().use { db ->
            val tables = query(db, "SELECT name FROM sqlite_master WHERE type = 'table'") { it.getString(1) }
            assertFalse("identity" in tables, "the names must not survive the upgrade: $tables")
            assertTrue("visits" in tables && "ecg_inbox" in tables, tables.toString())
            assertFalse("visits_new" in tables, "the rebuild table must be renamed away: $tables")
        }
    }

    @Test
    fun theEcgInboxIsUsableStraightAway() {
        migrated().use { db ->
            db.createStatement().use {
                it.execute("""INSERT INTO ecg_inbox (visitUuid, clipId, relPath, createdAt, consumed)
                              VALUES ('u-draft', 'clip1', 'SW-001/clip1_kardia.pdf', '2026-10-24T10:00:00+05:30', 0)""")
            }
            val rows = query(db, "SELECT id, clipId, consumed FROM ecg_inbox") {
                listOf(it.getLong(1).toString(), it.getString(2), it.getInt(3).toString())
            }
            assertEquals(listOf(listOf("1", "clip1", "0")), rows, "the id must auto-increment from 1")
        }
    }
}
