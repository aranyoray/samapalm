package org.samahealth.crf

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class SupabaseClientTest {
    private lateinit var server: MockWebServer
    private lateinit var client: SupabaseClient

    @BeforeTest fun up() { server = MockWebServer(); server.start(); client = SupabaseClient(SupabaseConfig(server.url("/").toString(), "anon-key")) }
    @AfterTest fun down() { server.shutdown() }

    private fun payload(pid: String = "SWHT-PP-003-0001") = VisitPayload("uuid-1", pid, "submitted", JsonObject(mapOf("study_id" to JsonPrimitive(pid))),
        "v1", "1.0", "tab-A", "op1", "pilot", "2026-10-20T10:00:00+05:30", "2026-10-20T10:20:00+05:30", "2026-10-20T10:20:00+05:30", null)

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
        assertTrue("name" !in body["crf"]!!.jsonObject)

        server.enqueue(MockResponse().setResponseCode(409).setBody("""{"code":"23505","message":"duplicate key value violates unique constraint \"visits_pid_key\""}"""))
        assertTrue(client.upsertVisit("jwt", payload()) is SyncResult.DuplicatePid)
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
        server.enqueue(MockResponse().setBody("""[{"visit_uuid":"other"}]"""))
        assertTrue(client.pidTakenElsewhere("jwt", "SWHT-PP-003-0001", "uuid-1"))
        assertEquals("/rest/v1/visits?select=visit_uuid&pid=eq.SWHT-PP-003-0001", server.takeRequest().path)
    }

    @Test fun operatorProfileReadsCodeAndRole() {
        server.enqueue(MockResponse().setBody("""[{"operator_code":"op7","role":"operator","active":true}]"""))
        assertEquals("op7" to "operator", client.operatorProfile("jwt", "u-7"))
        assertEquals("/rest/v1/operators?select=operator_code,role,active&user_id=eq.u-7", server.takeRequest().path)
        server.enqueue(MockResponse().setBody("[]"))
        assertEquals(null, client.operatorProfile("jwt", "u-8"))
    }
}
