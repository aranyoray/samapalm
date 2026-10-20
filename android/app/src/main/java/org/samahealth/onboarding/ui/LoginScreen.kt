package org.samahealth.onboarding.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.samahealth.onboarding.container

/** Operator sign-in (one Supabase account per operator). The session is kept, so the app works offline afterwards. */
@Composable
fun LoginScreen(onSignedIn: () -> Unit, onSettings: () -> Unit) {
    val c = LocalContext.current.container
    var email by remember { mutableStateOf(c.prefs.session?.email ?: "") }
    var password by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    Column(Modifier.padding(24.dp).fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("SamaHealth onboarding", style = MaterialTheme.typography.headlineSmall)
        Text("Device ${c.prefs.deviceCode} · PIDs ${c.prefs.pidBlockStart}-${c.prefs.pidBlockEnd}", style = MaterialTheme.typography.bodySmall)
        OutlinedTextField(email, { email = it }, label = { Text("Operator email") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email), modifier = Modifier.fillMaxWidth())
        OutlinedTextField(password, { password = it }, label = { Text("Password") }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password), modifier = Modifier.fillMaxWidth())
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(enabled = !busy && email.isNotBlank() && password.isNotBlank(), onClick = {
            busy = true; error = null
            scope.launch {
                val msg = withContext(Dispatchers.IO) {
                    try {
                        val client = c.client() ?: return@withContext "Set the Supabase project in Settings first."
                        val s = client.signIn(email.trim(), password)
                        val profile = client.operatorProfile(s.accessToken, s.userId)
                            ?: return@withContext "This account has no active operator profile. Ask the study admin."
                        c.prefs.session = s
                        c.prefs.operatorCode = profile.first
                        c.prefs.operatorRole = profile.second
                        null
                    } catch (e: Exception) {
                        "Sign-in failed: ${e.message?.take(160)}"
                    }
                }
                busy = false
                if (msg == null) onSignedIn() else error = msg
            }
        }) { Text(if (busy) "Signing in..." else "Sign in") }
        TextButton(onClick = onSettings) { Text("Tablet settings") }
    }
}
