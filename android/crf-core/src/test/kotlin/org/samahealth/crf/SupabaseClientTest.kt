package org.samahealth.crf

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import java.io.IOException
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class SupabaseClientTest {
    private lateinit var server: MockWebServer
    private lateinit var client: SupabaseClient

    @BeforeTest fun up() { server = MockWebServer(); server.start(); client = SupabaseClient(SupabaseConfig(server.url("/").toString(), "anon-key")) }
    @AfterTest fun down() { server.shutdown() }

    private fun payload(pid: String = "SWHT-PP-003-0001", part: String = "enrol") = VisitPayload("uuid-1", pid, part, "submitted",
        JsonObject(mapOf("study_id" to JsonPrimitive(pid), "part" to JsonPrimitive(part))),
        "2026-10-24.1", "2.0", "tab-A", "op1", "pilot", "2026-10-20T10:00:00+05:30", "2026-10-20T10:20:00+05:30", "2026-10-20T10:20:00+05:30", null)

    @Test fun signInParsesTheSessionAndSendsTheAnonKey() {
        server.enqueue(MockResponse().setBody("""{"access_token":"jwt","refresh_token":"r","expires_in":3600,"user":{"id":"u1","email":"op1@x.org"}}"""))
        val s = client.signIn("op1@x.org", "pw")
        assertEquals("jwt", s.accessToken); assertEquals("u1", s.userId)
        val r = server.takeRequest()
        assertEquals("/auth/v1/token?grant_type=password", r.path)
        assertEquals("anon-key", r.getHeader("apikey"))
        assertEquals("op1@x.org", str(CrfJson.parseToJsonElement(r.body.readUtf8()).jsonObject["email"]))
    }

    @Test fun upsertIsIdempotentAndClassifiesResponses() {
        server.enqueue(MockResponse().setResponseCode(201))
        assertEquals(SyncResult.Ok, client.upsertVisit("jwt", payload()))
        val r = server.takeRequest()
        assertEquals("/rest/v1/visits?on_conflict=visit_uuid", r.path)
        assertEquals("Bearer jwt", r.getHeader("Authorization"))
        assertTrue(r.getHeader("Prefer")!!.contains("merge-duplicates"))
        val body = CrfJson.parseToJsonElement(r.body.readUtf8()).jsonObject
        assertEquals("uuid-1", str(body["visit_uuid"]))
        assertEquals("enrol", str(body["part"]))
        assertTrue("name" !in body["crf"]!!.jsonObject)

        server.enqueue(MockResponse().setResponseCode(409).setBody("""{"code":"23505","message":"duplicate key value violates unique constraint \"visits_pid_part_key\""}"""))
        assertEquals(SyncResult.DuplicatePid("SWHT-PP-003-0002", """{"code":"23505","message":"duplicate key value violates unique constraint \"visits_pid_part_key\""}"""),
            client.upsertVisit("jwt", payload("SWHT-PP-003-0002", "scan")))
        server.enqueue(MockResponse().setResponseCode(401).setBody("""{"message":"JWT expired"}"""))
        assertTrue(client.upsertVisit("jwt", payload()) is SyncResult.AuthExpired)
        server.enqueue(MockResponse().setResponseCode(503))
        assertTrue(client.upsertVisit("jwt", payload()) is SyncResult.Retry)
        server.enqueue(MockResponse().setResponseCode(400).setBody("""{"message":"bad"}"""))
        assertTrue(client.upsertVisit("jwt", payload()) is SyncResult.Rejected)
    }

    @Test fun identityGoesThroughTheRpcAndPidHelpersWork() {
        server.enqueue(MockResponse().setResponseCode(204))
        val ident = JsonObject(mapOf("pid" to JsonPrimitive("SWHT-PP-003-0001"), "name" to JsonPrimitive("A B")))
        assertEquals(SyncResult.Ok, client.submitIdentity("jwt", ident))
        val r = server.takeRequest()
        assertEquals("/rest/v1/rpc/submit_identity", r.path)
        assertEquals("A B", str(CrfJson.parseToJsonElement(r.body.readUtf8()).jsonObject["p_name"]))
        server.enqueue(MockResponse().setBody("\"SWHT-PP-003-1001\""))
        assertEquals("SWHT-PP-003-1001", client.allocatePid("jwt", "tab-B"))
        server.takeRequest()
    }

    @Test fun pidTakenElsewhereComparesPidAndPart() {
        val pid = "SWHT-PP-003-0001"
        fun taken(rows: String, part: String): Boolean {
            server.enqueue(MockResponse().setBody(rows))
            val r = client.pidTakenElsewhere("jwt", pid, part, "uuid-1")
            assertEquals("/rest/v1/visits?select=visit_uuid,part&pid=eq.SWHT-PP-003-0001", server.takeRequest().path)
            return r
        }
        assertTrue(taken("""[{"visit_uuid":"other","part":"enrol"}]""", "enrol"))          // same PID and part: clash
        assertFalse(taken("""[{"visit_uuid":"other","part":"enrol"}]""", "scan"))          // the other station's part
        assertFalse(taken("""[{"visit_uuid":"uuid-1","part":"scan"}]""", "scan"))          // our own earlier upload
        assertTrue(taken("""[{"visit_uuid":"other","part":"full"}]""", "scan"))            // a v1 record holds the PID
        assertFalse(taken("[]", "enrol"))
    }

    @Test fun refreshTellsAuthFailureFromNetworkTrouble() {
        server.enqueue(MockResponse().setBody("""{"access_token":"jwt2","refresh_token":"r2","expires_at":1800000000,"user":{"id":"u1"}}"""))
        val s = client.refresh("r1")
        assertEquals("jwt2", s.accessToken); assertEquals(1800000000L, s.expiresAtEpochS)
        val req = server.takeRequest()
        assertEquals("/auth/v1/token?grant_type=refresh_token", req.path)
        assertEquals("r1", str(CrfJson.parseToJsonElement(req.body.readUtf8()).jsonObject["refresh_token"]))

        server.enqueue(MockResponse().setResponseCode(400).setBody("""{"error":"invalid_grant","error_description":"Invalid Refresh Token: Already Used"}"""))
        val e = assertFailsWith<AuthFailedException> { client.refresh("r1") }
        assertEquals(400, e.code)
        assertFalse((e as Exception) is IOException)
        server.enqueue(MockResponse().setResponseCode(401).setBody("""{"code":401,"error_code":"session_expired"}"""))
        assertFailsWith<AuthFailedException> { client.refresh("r1") }
        server.enqueue(MockResponse().setResponseCode(503))
        assertEquals(503, assertFailsWith<SupabaseException> { client.refresh("r1") }.code)
        server.enqueue(MockResponse().setBody("<html>portal</html>"))
        assertFailsWith<SupabaseException> { client.refresh("r1") }
        val noRetry = SupabaseClient(SupabaseConfig(server.url("/").toString(), "anon-key"),
            SupabaseClient.defaultHttp().newBuilder().retryOnConnectionFailure(false).build())
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AT_START))
        assertFailsWith<IOException> { noRetry.refresh("r1") }
    }

    @Test fun strataCountsAndScanQueueCallTheRpcs() {
        server.enqueue(MockResponse().setBody("""[{"key":"sex:F","n":412},{"key":"rhythm:af","n":3}]"""))
        assertEquals(mapOf("sex:F" to 412, "rhythm:af" to 3), client.strataCounts("jwt", "development"))
        var r = server.takeRequest()
        assertEquals("/rest/v1/rpc/strata_counts", r.path); assertEquals("POST", r.method)
        assertEquals("development", str(CrfJson.parseToJsonElement(r.body.readUtf8()).jsonObject["p_stream"]))
        server.enqueue(MockResponse().setBody("[]"))
        assertEquals(emptyMap(), client.strataCounts("jwt", null))
        assertEquals("""{"p_stream":null}""", server.takeRequest().body.readUtf8())

        server.enqueue(MockResponse().setBody("""[{"pid":"SWHT-PP-003-0042","enrolled_at":"2026-10-24T04:30:00+00:00","sex":"F","age":58,
            "mst_band":8,"conditions":["htn","diabetes"]},{"pid":"SWHT-PP-003-0043","enrolled_at":"2026-10-24T04:10:00+00:00","sex":null,
            "age":null,"mst_band":null,"conditions":null}]"""))
        assertEquals(listOf(ScanQueueItem("SWHT-PP-003-0042", "2026-10-24T04:30:00+00:00", "F", 58, 8, listOf("htn", "diabetes")),
            ScanQueueItem("SWHT-PP-003-0043", "2026-10-24T04:10:00+00:00", null, null, null, emptyList())), client.scanQueue("jwt", 2))
        r = server.takeRequest()
        assertEquals("/rest/v1/rpc/scan_queue", r.path)
        assertEquals("""{"p_days":2}""", r.body.readUtf8())
        server.enqueue(MockResponse().setResponseCode(403).setBody("""{"code":"42501","message":"not allowed"}"""))
        assertEquals(403, assertFailsWith<SupabaseException> { client.scanQueue("jwt", 2) }.code)
    }

    @Test fun targetsReturnsTheRawRows() {
        val rows = """[{"key":"sex:F","group_id":"sex","group_label":"Sex","label":"Female","target":1000,"weight":1.0,"sort_order":1,"active":true}]"""
        server.enqueue(MockResponse().setBody(rows))
        assertEquals(rows, client.targets("jwt"))
        assertEquals("/rest/v1/recruitment_targets?select=*&active=eq.true&order=sort_order.asc,key.asc", server.takeRequest().path)
        server.enqueue(MockResponse().setBody("[]"))
        assertNull(client.targets("jwt"))
        server.enqueue(MockResponse().setResponseCode(404).setBody("""{"code":"PGRST205"}"""))
        assertNull(client.targets("jwt"))
    }

    @Test fun operatorProfileReadsCodeAndRole() {
        server.enqueue(MockResponse().setBody("""[{"operator_code":"op7","role":"operator","active":true}]"""))
        assertEquals("op7" to "operator", client.operatorProfile("jwt", "u-7"))
        assertEquals("/rest/v1/operators?select=operator_code,role,active&user_id=eq.u-7", server.takeRequest().path)
        server.enqueue(MockResponse().setBody("[]"))
        assertEquals(null, client.operatorProfile("jwt", "u-8"))
    }
}
